"""CLI entry point.

  python -m bot login            open Chrome so you can sign in to each retailer once
  python -m bot test-notify      send a test push to your phone
  python -m bot probe <url>      open one product page and print what the bot sees
  python -m bot run [--dry-run]  watch the list; auto-cart and push when in stock
  python -m bot reset [<url>]    forget that a product was already carted
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from . import config as cfgmod
from .config import ROOT, Product


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(ROOT / "bot.log", encoding="utf-8"),
        ],
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def cmd_login(cfg) -> None:
    from .browser import Browser
    from .retailers import build_registry

    reg = build_registry(cfg)
    wanted = sorted({p.retailer for p in cfg.products if p.retailer != "generic"}) or list(reg)
    with Browser(cfg) as br:
        for name in wanted:
            url = reg[name].login_url
            if url:
                br.new_page(url)
        print("\nSign in to every tab, then save your address and card in each account.")
        print("Also open the retailer apps on your phone and sign in there.")
        input("When done, press Enter here to close the browser... ")


def cmd_test_notify(cfg) -> None:
    from .notify import Notifier

    Notifier(cfg).send(
        "Restock bot test",
        f"If you can read this on your phone, pushes work. {datetime.now():%H:%M:%S}",
        click="https://www.pokemoncenter.com",
        urgent=True,
        tags="tada",
    )
    print("Sent. Check your phone.")


def cmd_probe(cfg, url: str) -> None:
    from .browser import Browser
    from .retailers import build_registry

    p = Product(name="probe", url=url)
    r = build_registry(cfg)[p.retailer]
    with Browser(cfg) as br:
        page = br.new_page(url)
        page.wait_for_timeout(2500)
        snap = r.snapshot(page)
        out = ROOT / "probes" / f"{p.retailer}-{datetime.now():%Y%m%d-%H%M%S}.png"
        out.parent.mkdir(exist_ok=True)
        page.screenshot(path=str(out), full_page=False)
        print(f"\nretailer : {p.retailer}")
        print(f"title    : {page.title()[:90]}")
        print(f"in_stock : {snap.in_stock}")
        print(f"price    : {snap.price}")
        print(f"seller_ok: {snap.seller_ok}")
        print(f"challenge: {snap.challenge}   queued: {snap.queued}")
        print(f"note     : {snap.note}")
        print(f"shot     : {out}")
        input("\nBrowser stays open so you can look. Press Enter to close... ")


def cmd_reset(cfg, url: str | None) -> None:
    from .state import State

    st = State.load()
    if url:
        st.reset_product(Product(name="x", url=url).id)
        print("Reset", url)
    else:
        for p in cfg.products:
            st.reset_product(p.id)
        print("Reset all products")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="bot", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--config", default=None, help="path to config.json")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login")
    sub.add_parser("test-notify")
    pr = sub.add_parser("probe")
    pr.add_argument("url")
    rn = sub.add_parser("run")
    rn.add_argument("--dry-run", action="store_true", help="notify but never click Add to Cart")
    rs = sub.add_parser("reset")
    rs.add_argument("url", nargs="?")
    args = ap.parse_args(argv)

    setup_logging(args.verbose)
    cfg = cfgmod.load(args.config)

    if args.cmd == "login":
        cmd_login(cfg)
    elif args.cmd == "test-notify":
        cmd_test_notify(cfg)
    elif args.cmd == "probe":
        cmd_probe(cfg, args.url)
    elif args.cmd == "reset":
        cmd_reset(cfg, args.url)
    elif args.cmd == "run":
        from .monitor import Monitor

        try:
            Monitor(cfg, dry_run=args.dry_run).run()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
