from __future__ import annotations

import logging

from playwright.sync_api import Page

from .base import Retailer, Snapshot

log = logging.getLogger("retailer.walmart")


class Walmart(Retailer):
    name = "walmart"
    cart_url = "https://www.walmart.com/cart"
    login_url = "https://www.walmart.com/account/login"

    ATC = ['button[data-automation-id="atc"]', 'button[data-testid="add-to-cart"]']
    PRICE = ['[itemprop="price"]', '[data-testid="price-wrap"] span', '[data-seo-id="hero-price"]']
    SELLER = ['[data-testid="product-seller-info"]', '[data-testid="seller-name"]', '[class*="seller" i]']

    def __init__(self, require_walmart_seller: bool = True):
        self.require_walmart_seller = require_walmart_seller

    def _btn(self, page: Page):
        for sel in self.ATC:
            try:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible() and loc.is_enabled():
                    return loc
            except Exception:
                continue
        return self._enabled_button(page, ("add to cart",))

    def snapshot(self, page: Page) -> Snapshot:
        body = self._body_text(page)
        if self._challenge(page, body):
            return Snapshot(False, challenge=True, note="Walmart robot-or-human check")
        price = self.price(page)
        if self._btn(page) is not None:
            ok = self.seller_ok(page)
            return Snapshot(True, price, ok, note="Walmart add-to-cart enabled" + ("" if ok else " (marketplace seller)"))
        if "out of stock" in body or "sold out" in body:
            return Snapshot(False, price, note="Walmart out of stock")
        return Snapshot(False, price, note="Walmart: no enabled button")

    def price(self, page: Page):
        return self._parse_price(self._first_text(page, self.PRICE))

    def seller_ok(self, page: Page) -> bool:
        if not self.require_walmart_seller:
            return True
        txt = self._first_text(page, self.SELLER).lower()
        if not txt:
            body = self._body_text(page)
            txt = body[body.find("sold") : body.find("sold") + 120] if "sold" in body else ""
        return "walmart.com" in txt or "sold and shipped by walmart" in txt

    def add_to_cart(self, page: Page) -> bool:
        btn = self._btn(page)
        if btn is None:
            return False
        btn.click()
        return self._confirm_added(page)
