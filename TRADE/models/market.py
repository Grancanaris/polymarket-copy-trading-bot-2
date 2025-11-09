from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Market:
    """Represents a Polymarket binary market"""
    condition_id: str
    question: str
    end_date: datetime

    # Token IDs for binary outcomes
    token_id_up: str  # "Yes" or "Up" token
    token_id_down: str  # "No" or "Down" token

    # Current prices
    price_up: float  # Price of Up outcome (0.0 to 1.0)
    price_down: float  # Price of Down outcome (0.0 to 1.0)

    # Orderbook depth
    best_bid_up: Optional[float] = None
    best_ask_up: Optional[float] = None
    best_bid_down: Optional[float] = None
    best_ask_down: Optional[float] = None

    # Market metadata
    slug: Optional[str] = None
    volume_24h: float = 0.0
    liquidity: float = 0.0

    @property
    def is_arbitrage_opportunity(self) -> bool:
        """Check if Up + Down < 1.00 (arbitrage opportunity)"""
        return (self.price_up + self.price_down) < 1.00

    @property
    def arbitrage_profit(self) -> float:
        """Calculate profit from buying both sides"""
        return 1.00 - (self.price_up + self.price_down)

    @property
    def is_extreme_up(self) -> bool:
        """Check if Up is extremely high (>70%)"""
        return self.price_up > 0.70

    @property
    def is_extreme_down(self) -> bool:
        """Check if Up is extremely low (<30%)"""
        return self.price_up < 0.30

    @property
    def hours_to_expiry(self) -> float:
        """Hours until market expires"""
        delta = self.end_date - datetime.now(self.end_date.tzinfo)
        return delta.total_seconds() / 3600

    @property
    def is_hourly_market(self) -> bool:
        """Check if this is an hourly market"""
        return self.hours_to_expiry <= 1.5  # Within 1.5 hours

    def __str__(self) -> str:
        return (f"{self.question[:50]}... | "
                f"Up: ${self.price_up:.3f} | Down: ${self.price_down:.3f} | "
                f"Expires in {self.hours_to_expiry:.1f}h")
