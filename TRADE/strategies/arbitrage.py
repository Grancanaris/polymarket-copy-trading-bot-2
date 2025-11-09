from typing import Optional, Tuple
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY
from models.market import Market
from models.position import Position, PositionSide, StrategyType, PositionStatus
from config.config import ScalpingConfig
from datetime import datetime, timezone
import uuid

class BinaryArbitrageStrategy:
    """
    Binary Arbitrage Strategy

    Exploits mispricing in binary markets where Up + Down should equal $1.00.
    When Up + Down < $1.00, buying both sides guarantees profit at market resolution.

    Example: Buy Up @ 21¢ + Buy Down @ 78¢ = 99¢ → 1¢ profit per pair
    """

    def __init__(self, clob_client: ClobClient):
        self.clob_client = clob_client
        self.min_profit = ScalpingConfig.ARB_MIN_PROFIT
        self.position_size = ScalpingConfig.ARB_POSITION_SIZE

    def detect_opportunity(self, market: Market) -> bool:
        """Check if there's an arbitrage opportunity"""
        if not market.is_arbitrage_opportunity:
            return False

        profit = market.arbitrage_profit
        return profit >= self.min_profit

    def execute(self, market: Market) -> Tuple[Optional[Position], Optional[Position]]:
        """
        Execute arbitrage by buying both Up and Down

        Returns: (position_up, position_down) or (None, None) if failed
        """
        if not self.detect_opportunity(market):
            return None, None

        profit = market.arbitrage_profit
        print(f"🎯 ARBITRAGE OPPORTUNITY: {market.question[:60]}")
        print(f"   Up: ${market.price_up:.4f} + Down: ${market.price_down:.4f} = ${market.price_up + market.price_down:.4f}")
        print(f"   Guaranteed profit: ${profit:.4f} per share ({profit * self.position_size:.2f} total)")

        # Execute both sides
        position_up = self._buy_side(market, market.token_id_up, market.price_up, PositionSide.UP)
        if not position_up:
            print(f"   ❌ Failed to buy Up side")
            return None, None

        position_down = self._buy_side(market, market.token_id_down, market.price_down, PositionSide.DOWN)
        if not position_down:
            print(f"   ❌ Failed to buy Down side - need to close Up position!")
            # TODO: Close the Up position we just opened
            return position_up, None

        # Link the positions as a pair
        position_up.paired_position_id = position_down.position_id
        position_down.paired_position_id = position_up.position_id

        print(f"   ✅ Arbitrage executed: {self.position_size} shares on both sides")
        return position_up, position_down

    def _buy_side(self, market: Market, token_id: str, price: float, side: PositionSide) -> Optional[Position]:
        """Buy one side of the arbitrage"""
        try:
            # Round price to 4 decimals, shares to 2 decimals
            buy_price = round(price * 1.002, 4)  # 0.2% buffer to ensure fill
            shares = round(float(self.position_size), 2)

            # Create limit buy order
            order_args = OrderArgs(
                token_id=token_id,
                price=buy_price,
                size=shares,
                side=BUY
            )

            signed_order = self.clob_client.create_order(order_args)
            response = self.clob_client.post_order(signed_order, OrderType.GTC)

            if not response.get('success', False):
                print(f"   ❌ Order failed: {response}")
                return None

            # Create position object
            entry_usdc = shares * buy_price
            position = Position(
                position_id=str(uuid.uuid4()),
                condition_id=market.condition_id,
                token_id=token_id,
                side=side,
                strategy=StrategyType.ARBITRAGE,
                entry_price=buy_price,
                entry_size=shares,
                entry_time=datetime.now(timezone.utc),
                entry_usdc=entry_usdc,
                current_price=buy_price,
                status=PositionStatus.OPEN,
                stop_loss_price=None,  # No stop loss for arbitrage
                take_profit_price=None  # Will profit at market resolution
            )

            return position

        except Exception as e:
            print(f"   ❌ Error buying {side.value}: {e}")
            return None

    def should_close(self, position: Position) -> bool:
        """
        Arbitrage positions should typically be held until market resolution
        However, we can close early if:
        1. We can sell both sides for more than we paid
        2. Market is about to expire
        """
        # For now, hold until resolution
        return False

    def get_stats(self) -> dict:
        """Return strategy statistics"""
        return {
            "strategy": "Binary Arbitrage",
            "min_profit_threshold": self.min_profit,
            "position_size": self.position_size,
            "enabled": ScalpingConfig.ENABLE_ARBITRAGE
        }
