from __future__ import annotations

import logging

from playwright.sync_api import Page

from .base import Retailer, Snapshot

log = logging.getLogger("retailer.pokemoncenter")


class PokemonCenter(Retailer):
    name = "pokemoncenter"
    cart_url = "https://www.pokemoncenter.com/cart"
    login_url = "https://www.pokemoncenter.com/login"

    PRICE = ['[class*="product-price" i]', '[class*="price" i]']

    @staticmethod
    def in_queue(page: Page) -> bool:
        url = page.url.lower()
        return "queue-it" in url or "queue.pokemoncenter" in url

    def snapshot(self, page: Page) -> Snapshot:
        if self.in_queue(page):
            return Snapshot(False, queued=True, note="Pokemon Center waiting room (do not reload)")
        body = self._body_text(page)
        if self._challenge(page, body):
            return Snapshot(False, challenge=True, note="Pokemon Center bot check")
        price = self.price(page)
        btn = self._enabled_button(page, ("add to cart",))
        if btn is not None:
            return Snapshot(True, price, note="Pokemon Center add-to-cart enabled")
        if "sold out" in body or "out of stock" in body:
            return Snapshot(False, price, note="Pokemon Center sold out")
        return Snapshot(False, price, note="Pokemon Center: no enabled button")

    def price(self, page: Page):
        return self._parse_price(self._first_text(page, self.PRICE))
