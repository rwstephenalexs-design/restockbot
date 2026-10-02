from __future__ import annotations

from playwright.sync_api import Page

from .base import Retailer, Snapshot


class Target(Retailer):
    name = "target"
    cart_url = "https://www.target.com/cart"
    login_url = "https://www.target.com/login"

    SHIP_BTN = 'button[data-test="shippingButton"]'
    PICKUP_BTN = 'button[data-test="orderPickupButton"]'
    PRICE = ['[data-test="product-price"]', 'span[data-test="product-price"]']

    def _btn(self, page: Page):
        for sel in (self.SHIP_BTN, self.PICKUP_BTN):
            loc = page.locator(sel).first
            try:
                if loc.count() and loc.is_visible() and loc.is_enabled():
                    return loc
            except Exception:
                continue
        return self._enabled_button(page)

    def snapshot(self, page: Page) -> Snapshot:
        body = self._body_text(page)
        if self._challenge(page, body):
            return Snapshot(False, challenge=True, note="Target bot check")
        price = self.price(page)
        if self._btn(page) is not None:
            return Snapshot(True, price, note="Target add-to-cart enabled")
        if "out of stock" in body or "sold out" in body:
            return Snapshot(False, price, note="Target out of stock")
        return Snapshot(False, price, note="Target: no enabled button")

    def price(self, page: Page):
        return self._parse_price(self._first_text(page, self.PRICE))

    def add_to_cart(self, page: Page) -> bool:
        btn = self._btn(page)
        if btn is None:
            return False
        btn.click()
        # Target sometimes asks which fulfillment option; click Add to cart in the dialog if present.
        try:
            dlg = page.get_by_role("button", name="Add to cart").first
            if dlg.is_visible(timeout=3000):
                dlg.click()
        except Exception:
            pass
        return self._confirm_added(page)
