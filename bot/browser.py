from __future__ import annotations

import logging

from playwright.sync_api import BrowserContext, Page, sync_playwright

from .config import Config

log = logging.getLogger("browser")


class Browser:
    """One real, visible Chrome window with a persistent profile.

    The profile lives in chrome_profile_dir, so logins, cookies, and saved
    addresses survive restarts. You sign in once with `python -m bot login`.
    No stealth patches, no proxies: this is just your browser on your IP.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._pw = None
        self.context: BrowserContext | None = None

    def __enter__(self) -> "Browser":
        self._pw = sync_playwright().start()
        self.cfg.chrome_profile_dir.mkdir(parents=True, exist_ok=True)
        common = dict(
            user_data_dir=str(self.cfg.chrome_profile_dir),
            headless=False,
            viewport=None,
            args=["--start-maximized"],
        )
        try:
            self.context = self._pw.chromium.launch_persistent_context(channel="chrome", **common)
            log.info("Using installed Google Chrome")
        except Exception as e:  # Chrome not installed; fall back to bundled Chromium
            log.warning("Google Chrome not available (%s); using Playwright Chromium", e)
            self.context = self._pw.chromium.launch_persistent_context(**common)
        self.context.set_default_timeout(15000)
        return self

    def __exit__(self, *exc):
        try:
            if self.context:
                self.context.close()
        finally:
            if self._pw:
                self._pw.stop()

    def new_page(self, url: str | None = None) -> Page:
        assert self.context is not None
        page = self.context.new_page()
        if url:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
        return page
