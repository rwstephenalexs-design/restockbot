from __future__ import annotations

import logging

import requests

from .config import Config

log = logging.getLogger("notify")


class Notifier:
    """Pushes to your phone through ntfy, and optionally to a Discord webhook."""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    def send(
        self,
        title: str,
        body: str,
        click: str | None = None,
        urgent: bool = False,
        tags: str = "",
    ) -> None:
        log.info("NOTIFY %s | %s", title, body)
        self._ntfy(title, body, click, urgent, tags)
        self._discord(title, body, click)

    def _ntfy(self, title, body, click, urgent, tags):
        if not self.cfg.ntfy_topic or "CHANGE-ME" in self.cfg.ntfy_topic:
            log.warning("ntfy topic not set in config.json; skipping phone push")
            return
        headers = {
            "Title": title.encode("ascii", "ignore").decode(),
            "Priority": "urgent" if urgent else "default",
        }
        if tags:
            headers["Tags"] = tags
        if click:
            headers["Click"] = click
            headers["Actions"] = f"view, Open, {click}, clear=true"
        try:
            r = requests.post(
                f"{self.cfg.ntfy_server}/{self.cfg.ntfy_topic}",
                data=body.encode("utf-8"),
                headers=headers,
                timeout=10,
            )
            r.raise_for_status()
        except requests.RequestException as e:
            log.error("ntfy failed: %s", e)

    def _discord(self, title, body, click):
        if not self.cfg.discord_webhook:
            return
        content = f"**{title}**\n{body}"
        if click:
            content += f"\n{click}"
        try:
            requests.post(self.cfg.discord_webhook, json={"content": content}, timeout=10)
        except requests.RequestException as e:
            log.error("discord failed: %s", e)
