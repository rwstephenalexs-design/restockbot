from __future__ import annotations

from ..config import Config
from .amazon import Amazon
from .base import Retailer, Snapshot
from .bestbuy import BestBuy
from .pokemoncenter import PokemonCenter
from .target import Target
from .walmart import Walmart

__all__ = ["Retailer", "Snapshot", "build_registry"]


def build_registry(cfg: Config) -> dict[str, Retailer]:
    return {
        "target": Target(),
        "bestbuy": BestBuy(),
        "amazon": Amazon(require_amazon_seller=cfg.amazon_require_amazon_seller),
        "pokemoncenter": PokemonCenter(),
        "walmart": Walmart(require_walmart_seller=cfg.walmart_require_walmart_seller),
        "generic": Retailer(),
    }
