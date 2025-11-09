from typing import Optional
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from models.market import Market
from models.position import Position, PositionSide, StrategyType, PositionStatus
from config.config import ScalpingConfig
from datetime import datetime, timezone
import uuid

class MeanReversionStrategy:
    """
    Mean Reversion Trading Strategy

    Buys extreme outcomes (very high or very low probabilities) expecting reversion to 50/50.

    Logic: Hourly crypto price movements are hard to predict. Extreme probabilities (80%+ or 20%-)
    often overcorrect, creating opportunities when they revert toward 50/50.

    Examples from analysis:
    - 82 trades buying "Down" at >65¢ (betting unlikely outcomes become more likely)
    - 23 trades buying "Up" at <35¢ (same logic)
    - 23 trades selling near 50¢ (taking profit when price normalizes)
    """

    def __init__(self, clob_client: ClobClient):
        self.clob_client = clob_client
        self.entry_high = ScalpingConfig.MEAN_REV_ENTRY_HIGH  # >70% is extreme
        self.entry_low = ScalpingConfig.MEAN_REV_ENTRY_LOW    # <30% is extreme
        self.exit_target = ScalpingConfig.MEAN_REV_EXIT_TARGET  # Exit near 50%
        self.profit_target = ScalpingConfig.MEAN_REV_PROFIT_TARGET

    def detect_entry(self, market: Market) -> Optional[PositionSide]:
        """
        Detect mean reversion entry opportunity

        Returns: PositionSide to enter, or None
        """
        # Only trade hourly markets for mean reversion
        if not market.is_hourly_market:
            return None

        # Buy DOWN when Up price is extremely high (>70%)
        # Betting that the high probability will revert
        if market.price_up > self.entry_high:
            return PositionSide.DOWN

        # Buy UP when Up price is extremely low (<30%)
        # Betting that the low probability will increase
        if market.price_up < self.entry_low:
            return PositionSide.UP

        return None

    def execute_entry(self, market: Market, side: PositionSide) -> Optional[Position]:
        """Execute mean reversion entry"""
        try:
            # Use medium position size for mean reversion
            shares = 37  # Standard medium position

            # Determine token and price
            if side == PositionSide.UP:
                token_id = market.token_id_up
                entry_price = market.price_up
                print(f"🎲 MEAN REVERSION: Buying UP (currently undervalued at {market.price_up:.1%})")
            else:
                token_id = market.token_id_down
                entry_price = market.price_down
                print(f"🎲 MEAN REVERSION: Buying DOWN (UP overvalued at {market.price_up:.1%})")

            print(f"   Market: {market.question[:60]}")

            # Add buffer
            buy_price = round(entry_price * 1.005, 4)
            shares = round(float(shares), 2)

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

            # Calculate target exit price (toward 50/50)
            if side == PositionSide.UP:
                # If buying UP low, exit when it rises toward 50%
                take_profit_price = round(min(buy_price + self.profit_target, self.exit_target), 4)
            else:
                # If buying DOWN (when UP is high), exit when UP drops toward 50%
                # DOWN price will increase as UP price decreases
                take_profit_price = round(min(buy_price + self.profit_target, 1.0 - self.exit_target), 4)

            # Create position
            entry_usdc = shares * buy_price
            position = Position(
                position_id=str(uuid.uuid4()),
                condition_id=market.condition_id,
                token_id=token_id,
                side=side,
                strategy=StrategyType.MEAN_REVERSION,
                entry_price=buy_price,
                entry_size=shares,
                entry_time=datetime.now(timezone.utc),
                entry_usdc=entry_usdc,
                current_price=buy_price,
                status=PositionStatus.OPEN,
                stop_loss_price=round(buy_price * 0.80, 4),  # 20% stop loss
                take_profit_price=take_profit_price
            )

            print(f"   ✅ Position opened | Entry: ${buy_price:.4f} | Target: ${take_profit_price:.4f}")
            return position

        except Exception as e:
            print(f"   ❌ Error in mean reversion entry: {e}")
            return None

    def should_exit(self, position: Position, current_market: Market) -> bool:
        """Check if position should be exited"""
        # Update current price
        if position.side == PositionSide.UP:
            position.update_price(current_market.price_up)
        else:
            position.update_price(current_market.price_down)

        # Check if price has reverted toward 50/50
        if position.side == PositionSide.UP:
            # Exit if Up price approaches 50%
            if current_market.price_up >= self.exit_target:
                print(f"   📊 Mean reversion complete: UP now at {current_market.price_up:.1%} (target {self.exit_target:.1%})")
                return True
        else:
            # Exit if Up price dropped toward 50% (DOWN increased)
            if current_market.price_up <= self.exit_target:
                print(f"   📊 Mean reversion complete: UP now at {current_market.price_up:.1%} (target {self.exit_target:.1%})")
                return True

        # Check take profit
        if position.should_take_profit:
            print(f"   💰 Take profit triggered at ${position.current_price:.4f}")
            return True

        # Check stop loss
        if position.should_stop_loss:
            print(f"   🛑 Stop loss triggered at ${position.current_price:.4f}")
            return True

        # Exit if approaching market expiration
        if current_market.hours_to_expiry < 0.25:  # 15 minutes
            print(f"   ⏰ Market expiring soon ({current_market.hours_to_expiry*60:.0f} min)")
            return True

        return False

    def execute_exit(self, position: Position, current_market: Market) -> bool:
        """Execute exit for mean reversion position"""
        try:
            # Determine current price
            if position.side == PositionSide.UP:
                current_price = current_market.price_up
            else:
                current_price = current_market.price_down

            # Sell at current price
            sell_price = round(current_price * 0.998, 4)
            shares = round(position.entry_size, 2)

            print(f"📉 MEAN REV EXIT: {position.side.value} | P&L: ${position.unrealized_pnl:+.2f}")

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
            print(f"   ❌ Error in mean reversion exit: {e}")
            return False

    def get_stats(self) -> dict:
        """Return strategy statistics"""
        return {
            "strategy": "Mean Reversion",
            "entry_high_threshold": self.entry_high,
            "entry_low_threshold": self.entry_low,
            "exit_target": self.exit_target,
            "profit_target": self.profit_target,
            "enabled": ScalpingConfig.ENABLE_MEAN_REVERSION
        }
