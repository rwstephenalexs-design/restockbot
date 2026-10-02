from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

from playwright.sync_api import Page

log = logging.getLogger("retailer")

PRICE_RE = re.compile(r"\$\s*([0-9]{1,4}(?:,[0-9]{3})*(?:\.[0-9]{2})?)")


@dataclass
class Snapshot:
    in_stock: bool
    price: float | None = None
    seller_ok: bool = True
    note: str = ""
    challenge: bool = False  # bot check / access denied / captcha wall
    queued: bool = False     # sitting in a Queue-it style waiting room


class Retailer:
    """Base class. Subclasses override the selectors; the generic text
    heuristics here are the fallback for any site that is not special-cased."""

    name = "generic"
    cart_url = ""
    login_url = ""
    # Text that means a bot wall or captcha page rather than the product page.
    challenge_markers = (
        "access denied",
        "press & hold",
        "press and hold",
        "robot or human",
        "are you a human",
        "verify you are human",
        "unusual traffic",
        "enter the characters you see",
        "reference #",
    )
    in_stock_button_texts = ("add to cart", "add to bag", "buy now")
    out_of_stock_texts = ("sold out", "out of stock", "currently unavailable", "coming soon", "notify me")

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _body_text(page: Page) -> str:
        try:
            return page.inner_text("body", timeout=5000).lower()
        except Exception:
            return ""

    @classmethod
    def _first_text(cls, page: Page, selectors: list[str]) -> str:
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    return loc.inner_text(timeout=3000).strip()
            except Exception:
                continue
        return ""

    @classmethod
    def _parse_price(cls, text: str) -> float | None:
        m = PRICE_RE.search(text or "")
        if not m:
            return None
        return float(m.group(1).replace(",", ""))

    def _challenge(self, page: Page, body: str) -> bool:
        title = (page.title() or "").lower()
        hay = title + " " + body[:4000]
        return any(m in hay for m in self.challenge_markers)

    def _enabled_button(self, page: Page, texts=None):
        """Return the first visible, enabled button whose text matches."""
        texts = texts or self.in_stock_button_texts
        for t in texts:
            try:
                loc = page.get_by_role("button", name=re.compile(t, re.I))
                n = loc.count()
                for i in range(min(n, 5)):
                    b = loc.nth(i)
                    if b.is_visible() and b.is_enabled():
                        return b
            except Exception:
                continue
        return None

    # ------------------------------------------------------------ API
    def snapshot(self, page: Page) -> Snapshot:
        body = self._body_text(page)
        if self._challenge(page, body):
            return Snapshot(False, challenge=True, note="bot check / access denied page")
        price = self.price(page)
        btn = self._enabled_button(page)
        if btn is not None:
            return Snapshot(True, price, self.seller_ok(page), note="add-to-cart button enabled")
        if any(t in body for t in self.out_of_stock_texts):
            return Snapshot(False, price, note="out of stock text present")
        return Snapshot(False, price, note="no enabled add-to-cart button")

    def price(self, page: Page) -> float | None:
        txt = self._first_text(page, ['[class*="price" i]', '[data-test*="price" i]', '[itemprop="price"]'])
        return self._parse_price(txt)

    def seller_ok(self, page: Page) -> bool:
        return True

    def add_to_cart(self, page: Page) -> bool:
        btn = self._enabled_button(page)
        if btn is None:
            return False
        btn.click()
        return self._confirm_added(page)

    def _confirm_added(self, page: Page, timeout_s: float = 8.0) -> bool:
        """Best-effort check that something acknowledged the add."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            body = self._body_text(page)
            if any(t in body for t in ("added to cart", "added to your cart", "added to bag", "view cart", "go to cart", "checkout")):
                return True
            time.sleep(0.5)
        log.warning("%s: no add-to-cart confirmation seen; treating as added anyway", self.name)
        return True
