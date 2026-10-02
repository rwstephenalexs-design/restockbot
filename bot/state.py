from __future__ import annotations

import json
import time

from .config import ROOT

STATE_PATH = ROOT / "state.json"


class State:
    """Tiny JSON-backed record of what has already been carted, so the bot
    never carts the same product twice and never exceeds the daily cap."""

    def __init__(self, data: dict):
        self.data = data

    @classmethod
    def load(cls) -> "State":
        if STATE_PATH.exists():
            try:
                return cls(json.loads(STATE_PATH.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                pass
        return cls({"products": {}, "buys": []})

    def save(self) -> None:
        STATE_PATH.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def _p(self, pid: str) -> dict:
        return self.data["products"].setdefault(pid, {"buys": 0, "cooldown_until": 0})

    def buys(self, pid: str) -> int:
        return self._p(pid)["buys"]

    def in_cooldown(self, pid: str) -> bool:
        return time.time() < self._p(pid)["cooldown_until"]

    def set_cooldown(self, pid: str, minutes: int) -> None:
        self._p(pid)["cooldown_until"] = time.time() + minutes * 60
        self.save()

    def record_buy(self, pid: str) -> None:
        self._p(pid)["buys"] += 1
        self.data["buys"].append(time.time())
        self.save()

    def buys_last_24h(self) -> int:
        cutoff = time.time() - 86400
        return sum(1 for t in self.data["buys"] if t > cutoff)

    def reset_product(self, pid: str) -> None:
        self.data["products"].pop(pid, None)
        self.save()
