from __future__ import annotations

import logging
import random
import time
from datetime import datetime

from playwright.sync_api import Page

from .browser import Browser
from .config import Config, Product
from .notify import Notifier
from .retailers import Snapshot, build_registry
from .state import State

log = logging.getLogger("monitor")

CHALLENGE_RENOTIFY_SECONDS = 3600
QUEUE_RENOTIFY_SECONDS = 1800


class Monitor:
    def __init__(self, cfg: Config, dry_run: bool = False):
        self.cfg = cfg
        self.dry_run = dry_run
        self.state = State.load()
        self.notify = Notifier(cfg)
        self.retailers = build_registry(cfg)
        self.pages: dict[str, Page] = {}
        self._last_challenge_notice: dict[str, float] = {}
        self._last_queue_notice: dict[str, float] = {}

    # ------------------------------------------------------------ lifecycle
    def run(self) -> None:
        if not self.cfg.products:
            raise SystemExit("No products in config.json")
        with Browser(self.cfg) as br:
            for p in self.cfg.products:
                log.info("Opening %-12s %s", p.retailer, p.name)
                try:
                    self.pages[p.id] = br.new_page(p.url)
                except Exception as e:
                    log.error("Could not open %s: %s", p.name, e)
                    self.pages[p.id] = br.new_page()
                time.sleep(random.uniform(1.0, 2.5))
            self.notify.send(
                "Restock bot started",
                f"Watching {len(self.cfg.products)} product(s). Dry run: {self.dry_run}",
            )
            while True:
                self.cycle()
                wait = random.uniform(self.cfg.poll_seconds_min, self.cfg.poll_seconds_max)
                log.debug("sleeping %.0fs", wait)
                time.sleep(wait)

    def cycle(self) -> None:
        for p in self.cfg.products:
            try:
                self.check_product(p)
            except Exception as e:
                log.exception("Unhandled error on %s: %s", p.name, e)
            time.sleep(random.uniform(1.0, 3.0))

    # ------------------------------------------------------------ one product
    def check_product(self, p: Product) -> None:
        if self.state.buys(p.id) >= self.cfg.max_buys_per_product:
            return
        if self.state.in_cooldown(p.id):
            return
        page = self.pages[p.id]
        r = self.retailers.get(p.retailer, self.retailers["generic"])

        # Never reload a page that is sitting in a waiting room.
        if p.retailer == "pokemoncenter" and self.retailers["pokemoncenter"].in_queue(page):
            self._queue_notice(p, page)
            return

        try:
            if page.url.startswith("http"):
                page.reload(wait_until="domcontentloaded", timeout=40000)
            else:
                page.goto(p.url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1500)  # let client-side stock state render
        except Exception as e:
            log.warning("%s: reload failed: %s", p.name, e)
            return

        snap: Snapshot = r.snapshot(page)
        stamp = datetime.now().strftime("%H:%M:%S")
        price_s = f"${snap.price:.2f}" if snap.price is not None else "price?"
        log.info("%s %-12s %-35s %s %s | %s", stamp, p.retailer, p.name[:35],
                 "IN STOCK" if snap.in_stock else "--------", price_s, snap.note)

        if snap.queued:
            self._queue_notice(p, page)
            return
        if snap.challenge:
            self._challenge_notice(p, page)
            return
        if not snap.in_stock:
            return

        # In stock. Apply the two guards that keep this "retail only".
        if p.max_price is not None and snap.price is not None and snap.price > p.max_price:
            log.info("%s: in stock but %s is above max %.2f; ignoring", p.name, price_s, p.max_price)
            return
        if not snap.seller_ok:
            log.info("%s: in stock but third-party seller; ignoring", p.name)
            return
        if self.state.buys_last_24h() >= self.cfg.daily_buy_limit:
            self.notify.send("Daily cap reached", f"{p.name} is in stock at {price_s} but daily_buy_limit hit.", click=p.url, urgent=True)
            self.state.set_cooldown(p.id, self.cfg.cooldown_after_cart_minutes)
            return

        self.handle_in_stock(p, page, r, snap, price_s)

    def handle_in_stock(self, p: Product, page: Page, r, snap: Snapshot, price_s: str) -> None:
        # First ping goes out immediately, before carting, in case carting fails.
        self.notify.send(
            f"IN STOCK: {p.name}",
            f"{p.retailer} at {price_s}. Carting now, open the app.",
            click=p.url,
            urgent=True,
            tags="rotating_light",
        )
        if self.dry_run:
            log.info("DRY RUN: would add %s to cart", p.name)
            self.state.set_cooldown(p.id, self.cfg.cooldown_after_cart_minutes)
            return

        ok = False
        try:
            ok = r.add_to_cart(page)
        except Exception as e:
            log.exception("add_to_cart failed on %s: %s", p.name, e)

        if ok:
            try:
                page.goto(r.cart_url or p.url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                pass
            self.state.record_buy(p.id)
            self.notify.send(
                f"CARTED: {p.name}",
                f"In your {p.retailer} cart at {price_s}. Open the app and check out now.",
                click=r.cart_url or p.url,
                urgent=True,
                tags="shopping_cart,white_check_mark",
            )
        else:
            self.notify.send(
                f"Cart failed: {p.name}",
                f"In stock at {p.retailer} but auto-cart did not work. Go manual now.",
                click=p.url,
                urgent=True,
                tags="warning",
            )
        self.state.set_cooldown(p.id, self.cfg.cooldown_after_cart_minutes)

    # ------------------------------------------------------------ notices
    def _challenge_notice(self, p: Product, page: Page) -> None:
        now = time.time()
        if now - self._last_challenge_notice.get(p.retailer, 0) < CHALLENGE_RENOTIFY_SECONDS:
            return
        self._last_challenge_notice[p.retailer] = now
        self.notify.send(
            f"{p.retailer}: bot check",
            "The site is showing a verification page in the bot's Chrome window. "
            "Solve it on the PC (or via Chrome Remote Desktop) and the bot will carry on.",
            click=page.url,
            tags="shield",
        )

    def _queue_notice(self, p: Product, page: Page) -> None:
        now = time.time()
        if now - self._last_queue_notice.get(p.id, 0) < QUEUE_RENOTIFY_SECONDS:
            return
        self._last_queue_notice[p.id] = now
        self.notify.send(
            f"Waiting room: {p.name}",
            "Pokemon Center has a queue up. The bot is holding its place and will not reload.",
            click=page.url,
            tags="hourglass",
        )
