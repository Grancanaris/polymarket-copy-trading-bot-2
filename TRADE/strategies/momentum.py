from typing import Optional
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from models.market import Market
from models.position import Position, PositionSide, StrategyType, PositionStatus
from config.config import ScalpingConfig
from datetime import datetime, timezone
import uuid
import random

class MomentumScalpingStrategy:
    """
    Momentum Scalping Strategy

    Buys positions and quickly flips them for 1-3¢ profit per share.
    Holding period: Typically 1-20 trades (seconds to minutes)

    Strategy: Enter when price moves against the trend, exit when it reverts or momentum continues

    Examples from analysis:
    - Buy BTC Up @ 47¢ → Sell @ 48¢ = +1¢/share
    - Buy BTC Up @ 75¢ → Sell @ 90¢ = +15¢/share
    - Buy ETH Down @ 39¢ → Sell @ 60¢ = +21¢/share
    """

    def __init__(self, clob_client: ClobClient):
        self.clob_client = clob_client
        self.profit_target = ScalpingConfig.MOMENTUM_PROFIT_TARGET
        self.stop_loss = ScalpingConfig.MOMENTUM_STOP_LOSS
        self.price_change_threshold = ScalpingConfig.MOMENTUM_PRICE_CHANGE_THRESHOLD
        self.position_sizes = ScalpingConfig.MOMENTUM_POSITION_SIZES

        # Track recent prices for momentum detection
        self.price_history = {}  # condition_id -> list of recent prices

    def detect_entry(self, market: Market) -> Optional[PositionSide]:
        """
        Detect if there's a momentum entry opportunity

        Returns: PositionSide to enter, or None
        """
        condition_id = market.condition_id

        # Track price history
        if condition_id not in self.price_history:
            self.price_history[condition_id] = []

        history = self.price_history[condition_id]
        history.append((market.price_up, datetime.now(timezone.utc)))

        # Keep only last 20 price points
        if len(history) > 20:
            history = history[-20:]
            self.price_history[condition_id] = history

        # Need at least 3 data points for momentum
        if len(history) < 3:
            return None

        # Calculate price change from 3 trades ago
        old_price = history[-3][0]
        current_price = market.price_up
        price_change = current_price - old_price

        # Detect momentum opportunities
        # Buy UP if price dropped significantly (expect reversion/continuation)
        if price_change < -self.price_change_threshold and current_price > 0.20:
            return PositionSide.UP

        # Buy DOWN if price rose significantly (expect reversion)
        if price_change > self.price_change_threshold and current_price < 0.80:
            return PositionSide.DOWN

        return None

    def execute_entry(self, market: Market, side: PositionSide) -> Optional[Position]:
        """Execute momentum entry"""
        try:
            # Choose position size (use random from standard sizes)
            shares = random.choice(self.position_sizes)

            # Determine token and price
            if side == PositionSide.UP:
                token_id = market.token_id_up
                entry_price = market.price_up
            else:
                token_id = market.token_id_down
                entry_price = market.price_down

            # Add buffer to ensure fill
            buy_price = round(entry_price * 1.005, 4)  # 0.5% buffer
            shares = round(float(shares), 2)

            print(f"📈 MOMENTUM ENTRY: {side.value} on {market.question[:50]}")
            print(f"   Entry price: ${buy_price:.4f} | Size: {shares} shares")

            # Create order
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

            # Calculate stop loss and take profit
            stop_loss_price = round(buy_price - self.stop_loss, 4)
            take_profit_price = round(buy_price + self.profit_target, 4)

            # Create position
            entry_usdc = shares * buy_price
            position = Position(
                position_id=str(uuid.uuid4()),
                condition_id=market.condition_id,
                token_id=token_id,
                side=side,
                strategy=StrategyType.MOMENTUM,
                entry_price=buy_price,
                entry_size=shares,
                entry_time=datetime.now(timezone.utc),
                entry_usdc=entry_usdc,
                current_price=buy_price,
                status=PositionStatus.OPEN,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price
            )

            print(f"   ✅ Position opened | Target: ${take_profit_price:.4f} (+{self.profit_target:.2f}) | Stop: ${stop_loss_price:.4f} (-{self.stop_loss:.2f})")
            return position

        except Exception as e:
            print(f"   ❌ Error in momentum entry: {e}")
            return None

    def should_exit(self, position: Position, current_market: Market) -> bool:
        """Check if position should be exited"""
        # Update current price
        if position.side == PositionSide.UP:
            position.update_price(current_market.price_up)
        else:
            position.update_price(current_market.price_down)

        # Check stop loss
        if position.should_stop_loss:
            print(f"   🛑 Stop loss triggered: ${position.current_price:.4f} <= ${position.stop_loss_price:.4f}")
            return True

        # Check take profit
        if position.should_take_profit:
            print(f"   💰 Take profit triggered: ${position.current_price:.4f} >= ${position.take_profit_price:.4f}")
            return True

        return False

    def execute_exit(self, position: Position, current_market: Market) -> bool:
        """Execute exit for momentum position"""
        try:
            # Determine current price
            if position.side == PositionSide.UP:
                current_price = current_market.price_up
            else:
                current_price = current_market.price_down

            # Sell at current price
            sell_price = round(current_price * 0.998, 4)  # 0.2% below to ensure fill
            shares = round(position.entry_size, 2)

            print(f"📉 MOMENTUM EXIT: {position.side.value} | P&L: ${position.unrealized_pnl:+.2f}")

            order_args = OrderArgs(
                token_id=position.token_id,
                price=sell_price,
                size=shares,
                side=SELL
            )

            signed_order = self.clob_client.create_order(order_args)
            response = self.clob_client.post_order(signed_order, OrderType.GTC)

            if not response.get('success', False):
                print(f"   ❌ Exit order failed: {response}")
                return False

            # Close position
            exit_usdc = shares * sell_price
            position.close_position(sell_price, exit_usdc)

            print(f"   ✅ Position closed | Realized P&L: ${position.realized_pnl:+.2f}")
            return True

        except Exception as e:
            print(f"   ❌ Error in momentum exit: {e}")
            return False

    def get_stats(self) -> dict:
        """Return strategy statistics"""
        return {
            "strategy": "Momentum Scalping",
            "profit_target": self.profit_target,
            "stop_loss": self.stop_loss,
            "price_change_threshold": self.price_change_threshold,
            "position_sizes": self.position_sizes,
            "enabled": ScalpingConfig.ENABLE_MOMENTUM
        }
