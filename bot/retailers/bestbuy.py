from __future__ import annotations

import logging
import random
import time

from playwright.sync_api import Page

from .base import Retailer, Snapshot

log = logging.getLogger("retailer.bestbuy")


class BestBuy(Retailer):
    name = "bestbuy"
    cart_url = "https://www.bestbuy.com/cart"
    login_url = "https://www.bestbuy.com/identity/signin"

    BTN = "button.add-to-cart-button"
    PRICE = [
        '[data-testid="customer-price"] span',
        ".priceView-customer-price > span",
        ".priceView-hero-price span",
    ]
    # data-button-state values seen on Best Buy product pages
    IN_STOCK_STATES = {"ADD_TO_CART", "PRE_ORDER"}
    WAIT_STATES = {"PLEASE_WAIT", "LOADING"}

    def _state(self, page: Page) -> str:
        try:
            loc = page.locator(self.BTN).first
            if loc.count():
                return (loc.get_attribute("data-button-state") or "").upper()
        except Exception:
            pass
        return ""

    def snapshot(self, page: Page) -> Snapshot:
        body = self._body_text(page)
        if self._challenge(page, body):
            return Snapshot(False, challenge=True, note="Best Buy bot check")
        price = self.price(page)
        st = self._state(page)
        if st in self.IN_STOCK_STATES:
            return Snapshot(True, price, note=f"Best Buy state={st}")
        if st in self.WAIT_STATES:
            # The drop-day "Please Wait" button: item is live, button re-enables on its own.
            return Snapshot(True, price, note=f"Best Buy state={st} (please-wait queue)")
        if st:
            return Snapshot(False, price, note=f"Best Buy state={st}")
        # No data-button-state attribute: fall back to text heuristics.
        if self._enabled_button(page) is not None:
            return Snapshot(True, price, note="Best Buy add-to-cart enabled (text)")
        return Snapshot(False, price, note="Best Buy: no add-to-cart button")

    def price(self, page: Page):
        return self._parse_price(self._first_text(page, self.PRICE))

    def add_to_cart(self, page: Page, max_minutes: float = 5.0) -> bool:
        """Click Add to Cart; if Best Buy shows the Please Wait button, keep
        trying for a few minutes. The button re-enables by itself, no reload needed."""
        deadline = time.time() + max_minutes * 60
        clicks = 0
        while time.time() < deadline:
            loc = page.locator(self.BTN).first
            try:
                if not loc.count():
                    btn = self._enabled_button(page)
                    if btn is None:
                        return False
                    btn.click()
                    return self._confirm_added(page)
                st = (loc.get_attribute("data-button-state") or "").upper()
                if st in self.IN_STOCK_STATES and loc.is_enabled():
                    loc.click()
                    clicks += 1
                    time.sleep(1.5)
                    body = self._body_text(page)
                    if "added to cart" in body or "go to cart" in body or "view cart" in body:
                        return True
                    if clicks >= 3 and st in self.IN_STOCK_STATES:
                        return True  # assume added; the cart page will tell the truth
                elif st in self.WAIT_STATES:
                    log.info("Best Buy please-wait; retrying")
                else:
                    log.info("Best Buy button state %s; giving up", st)
                    return False
            except Exception as e:
                log.warning("Best Buy add_to_cart error: %s", e)
            time.sleep(random.uniform(2.0, 4.0))
        return False
