from __future__ import annotations

import logging

from playwright.sync_api import Page

from .base import Retailer, Snapshot

log = logging.getLogger("retailer.amazon")


class Amazon(Retailer):
    name = "amazon"
    cart_url = "https://www.amazon.com/gp/cart/view.html"
    login_url = "https://www.amazon.com/ap/signin?openid.return_to=https%3A%2F%2Fwww.amazon.com%2F&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=usflex&openid.mode=checkid_setup&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"

    ATC = "#add-to-cart-button"
    OOS = "#outOfStock"
    PRICE = [
        "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
        "#corePrice_feature_div .a-price .a-offscreen",
        "#apex_desktop .a-price .a-offscreen",
        ".a-price .a-offscreen",
    ]
    SELLER = ["#merchant-info", "#sellerProfileTriggerId", '[offer-display-feature-name="desktop-merchant-info"]']

    def __init__(self, require_amazon_seller: bool = True):
        self.require_amazon_seller = require_amazon_seller

    def snapshot(self, page: Page) -> Snapshot:
        body = self._body_text(page)
        if self._challenge(page, body) or page.locator("#captchacharacters").count():
            return Snapshot(False, challenge=True, note="Amazon captcha / robot check")
        price = self.price(page)
        atc = page.locator(self.ATC).first
        try:
            live = atc.count() and atc.is_visible() and atc.is_enabled()
        except Exception:
            live = False
        if live:
            ok = self.seller_ok(page)
            return Snapshot(True, price, ok, note="Amazon add-to-cart live" + ("" if ok else " (third-party seller)"))
        if page.locator(self.OOS).count() or "currently unavailable" in body:
            return Snapshot(False, price, note="Amazon unavailable")
        return Snapshot(False, price, note="Amazon: no buy box (see all buying options?)")

    def price(self, page: Page):
        for sel in self.PRICE:
            try:
                loc = page.locator(sel).first
                if loc.count():
                    p = self._parse_price(loc.text_content(timeout=2000) or "")
                    if p is not None:
                        return p
            except Exception:
                continue
        return None

    def seller_ok(self, page: Page) -> bool:
        if not self.require_amazon_seller:
            return True
        txt = self._first_text(page, self.SELLER).lower()
        if not txt:
            # Try the buy-box merchant line on newer layouts
            try:
                txt = page.locator("#tabular-buybox").inner_text(timeout=2000).lower()
            except Exception:
                txt = ""
        # Only first-party. "Ships from Amazon" alone is FBA, which is where the scalper listings live.
        return "sold by amazon" in txt or "sold by: amazon" in txt

    def add_to_cart(self, page: Page) -> bool:
        atc = page.locator(self.ATC).first
        if not atc.count():
            return False
        atc.click()
        # Decline the protection-plan side sheet if it pops up.
        try:
            no_thanks = page.locator("#attachSiNoCoverage, #attach-sidesheet-checkout-button, input[aria-labelledby='attachSiNoCoverage-announce']").first
            if no_thanks.is_visible(timeout=3000):
                no_thanks.click()
        except Exception:
            pass
        return self._confirm_added(page)
