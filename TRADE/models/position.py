from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum

class PositionSide(Enum):
    UP = "UP"
    DOWN = "DOWN"

class PositionStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"

class StrategyType(Enum):
    ARBITRAGE = "ARBITRAGE"
    MOMENTUM = "MOMENTUM"
    MEAN_REVERSION = "MEAN_REVERSION"
    MARKET_MAKING = "MARKET_MAKING"

@dataclass
class Position:
    """Represents an open trading position"""
    position_id: str
    condition_id: str
    token_id: str
    side: PositionSide
    strategy: StrategyType

    # Entry details
    entry_price: float  # Price paid per share
    entry_size: float  # Number of shares
    entry_time: datetime
    entry_usdc: float  # Total USDC spent

    # Current state
    current_price: float
    status: PositionStatus = PositionStatus.OPEN

    # Exit details (if closed)
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    exit_usdc: Optional[float] = None

    # Risk management
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None

    # Paired position (for arbitrage)
    paired_position_id: Optional[str] = None

    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized P&L"""
        if self.status == PositionStatus.CLOSED:
            return self.realized_pnl

        current_value = self.current_price * self.entry_size
        return current_value - self.entry_usdc

    @property
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized P&L percentage"""
        if self.entry_usdc == 0:
            return 0.0
        return (self.unrealized_pnl / self.entry_usdc) * 100

    @property
    def realized_pnl(self) -> float:
        """Calculate realized P&L (for closed positions)"""
        if not self.exit_usdc:
            return 0.0
        return self.exit_usdc - self.entry_usdc

    @property
    def hold_time_seconds(self) -> float:
        """Time position has been held (seconds)"""
        if self.status == PositionStatus.CLOSED and self.exit_time:
            delta = self.exit_time - self.entry_time
        else:
            delta = datetime.now(self.entry_time.tzinfo) - self.entry_time
        return delta.total_seconds()

    @property
    def should_stop_loss(self) -> bool:
        """Check if stop loss should be triggered"""
        if not self.stop_loss_price:
            return False
        return self.current_price <= self.stop_loss_price

    @property
    def should_take_profit(self) -> bool:
        """Check if take profit should be triggered"""
        if not self.take_profit_price:
            return False
        return self.current_price >= self.take_profit_price

    def update_price(self, new_price: float):
        """Update current price"""
        self.current_price = new_price

    def close_position(self, exit_price: float, exit_usdc: float):
        """Close the position"""
        self.exit_price = exit_price
        self.exit_time = datetime.now(self.entry_time.tzinfo)
        self.exit_usdc = exit_usdc
        self.status = PositionStatus.CLOSED

    def __str__(self) -> str:
        pnl_str = f"${self.unrealized_pnl:+.2f} ({self.unrealized_pnl_pct:+.1f}%)"
        return (f"{self.strategy.value} | {self.side.value} | "
                f"Entry: ${self.entry_price:.3f} | Current: ${self.current_price:.3f} | "
                f"P&L: {pnl_str}")
