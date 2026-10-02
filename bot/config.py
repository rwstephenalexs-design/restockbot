from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent

RETAILER_DOMAINS = {
    "target.com": "target",
    "bestbuy.com": "bestbuy",
    "amazon.com": "amazon",
    "pokemoncenter.com": "pokemoncenter",
    "walmart.com": "walmart",
}


def detect_retailer(url: str) -> str:
    host = urlparse(url).hostname or ""
    for domain, name in RETAILER_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return name
    return "generic"


@dataclass
class Product:
    name: str
    url: str
    max_price: float | None = None
    retailer: str = ""

    def __post_init__(self):
        if not self.retailer:
            self.retailer = detect_retailer(self.url)

    @property
    def id(self) -> str:
        return hashlib.sha1(self.url.encode()).hexdigest()[:10]


@dataclass
class Config:
    ntfy_server: str
    ntfy_topic: str
    discord_webhook: str
    poll_seconds_min: int
    poll_seconds_max: int
    cooldown_after_cart_minutes: int
    max_buys_per_product: int
    daily_buy_limit: int
    amazon_require_amazon_seller: bool
    walmart_require_walmart_seller: bool
    chrome_profile_dir: Path
    products: list[Product] = field(default_factory=list)


def load(path: str | Path | None = None) -> Config:
    path = Path(path) if path else ROOT / "config.json"
    if not path.exists():
        raise SystemExit(
            f"No config at {path}. Copy config.example.json to config.json and edit it."
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    ntfy = raw.get("ntfy", {})
    products = [
        Product(
            name=p["name"],
            url=p["url"],
            max_price=p.get("max_price"),
            retailer=p.get("retailer", ""),
        )
        for p in raw.get("products", [])
    ]
    profile = Path(raw.get("chrome_profile_dir", "chrome-profile"))
    if not profile.is_absolute():
        profile = ROOT / profile
    return Config(
        ntfy_server=ntfy.get("server", "https://ntfy.sh").rstrip("/"),
        ntfy_topic=ntfy.get("topic", ""),
        discord_webhook=raw.get("discord_webhook", ""),
        poll_seconds_min=int(raw.get("poll_seconds_min", 30)),
        poll_seconds_max=int(raw.get("poll_seconds_max", 60)),
        cooldown_after_cart_minutes=int(raw.get("cooldown_after_cart_minutes", 30)),
        max_buys_per_product=int(raw.get("max_buys_per_product", 1)),
        daily_buy_limit=int(raw.get("daily_buy_limit", 3)),
        amazon_require_amazon_seller=bool(raw.get("amazon_require_amazon_seller", True)),
        walmart_require_walmart_seller=bool(raw.get("walmart_require_walmart_seller", True)),
        chrome_profile_dir=profile,
        products=products,
    )
