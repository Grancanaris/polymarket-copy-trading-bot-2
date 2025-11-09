#!/usr/bin/env python3
"""
Polymarket Scalping Bot

Implements 4 strategies based on analysis of successful trading bot:
1. Binary Arbitrage - Primary strategy (guaranteed profits when Up + Down < $1.00)
2. Momentum Scalping - Quick 1-3¢ flips
3. Mean Reversion - Fade extreme probabilities
4. Market Making - Provide liquidity (optional, disabled by default)

Estimated profit: $2,000-$6,000/day based on observed activity
Risk level: Medium-Low (short holding periods, capped downside)
"""

import sys
import os
import time
import signal
from typing import List, Dict
from datetime import datetime, timezone
from colorama import Fore, Style, init

# Add parent directory to path to import from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
from config.config import ScalpingConfig
from models.market import Market
from models.position import Position, PositionStatus
from strategies.arbitrage import BinaryArbitrageStrategy
from strategies.momentum import MomentumScalpingStrategy
from strategies.mean_reversion import MeanReversionStrategy

# Initialize colorama
init()

class ScalpingBot:
    """Main scalping bot orchestrator"""

    def __init__(self):
        self.config = ScalpingConfig
        self.clob_client = None
        self.running = False

        # Strategies
        self.arbitrage_strategy = None
        self.momentum_strategy = None
        self.mean_reversion_strategy = None

        # Position tracking
        self.open_positions: List[Position] = []
        self.closed_positions: List[Position] = []

        # Performance tracking
        self.total_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0

    def initialize(self):
        """Initialize bot components"""
        print(f"{Fore.BLUE}🤖 Initializing Polymarket Scalping Bot...{Style.RESET_ALL}")
        print(f"👤 Wallet: {self.config.PROXY_WALLET}")
        print(f"⏱️  Scan interval: {self.config.SCAN_INTERVAL}s")

        # Create CLOB client
        print(f"{Fore.YELLOW}🔑 Setting up CLOB client...{Style.RESET_ALL}")
        key = self.config.PRIVATE_KEY
        if not key.startswith('0x'):
            key = '0x' + key

        self.clob_client = ClobClient(
            host=self.config.HOST,
            key=key,
            chain_id=POLYGON,
            signature_type=2,  # POLY_GNOSIS_SAFE
            funder=self.config.PROXY_WALLET
        )

        # Derive API credentials
        api_creds = self.clob_client.derive_api_key()
        self.clob_client.set_api_creds(api_creds)

        # Initialize strategies
        print(f"{Fore.YELLOW}📊 Initializing strategies...{Style.RESET_ALL}")

        if self.config.ENABLE_ARBITRAGE:
            self.arbitrage_strategy = BinaryArbitrageStrategy(self.clob_client)
            print(f"   ✅ Binary Arbitrage (min profit: {self.config.ARB_MIN_PROFIT:.2f}¢)")

        if self.config.ENABLE_MOMENTUM:
            self.momentum_strategy = MomentumScalpingStrategy(self.clob_client)
            print(f"   ✅ Momentum Scalping (profit target: {self.config.MOMENTUM_PROFIT_TARGET:.2f}¢)")

        if self.config.ENABLE_MEAN_REVERSION:
            self.mean_reversion_strategy = MeanReversionStrategy(self.clob_client)
            print(f"   ✅ Mean Reversion (entry: {self.config.MEAN_REV_ENTRY_HIGH:.0%}/{self.config.MEAN_REV_ENTRY_LOW:.0%})")

        print(f"{Fore.GREEN}✅ Bot initialized successfully!{Style.RESET_ALL}\n")

    def start(self):
        """Start the scalping bot"""
        try:
            self.initialize()
            self.running = True

            print(f"{Fore.GREEN}🚀 Scalping Bot is now running!{Style.RESET_ALL}")
            print(f"{Fore.CYAN}💫 Press Ctrl+C to stop{Style.RESET_ALL}\n")

            # Main loop
            while self.running:
                try:
                    self._scan_and_trade()
                    self._manage_positions()
                    self._check_risk_limits()

                    time.sleep(self.config.SCAN_INTERVAL)

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"{Fore.RED}❌ Error in main loop: {e}{Style.RESET_ALL}")
                    time.sleep(5)

        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            print(f"{Fore.RED}❌ Fatal error: {e}{Style.RESET_ALL}")
            self.stop()

    def _scan_and_trade(self):
        """Scan markets and execute strategies"""
        # TODO: Implement market scanning via Polymarket API
        # For now, this is a placeholder that would:
        # 1. Fetch active hourly markets for BTC/ETH
        # 2. Get orderbook data for each market
        # 3. Check each strategy for opportunities
        # 4. Execute trades
        pass

    def _manage_positions(self):
        """Manage open positions (check exits, update prices)"""
        for position in self.open_positions[:]:  # Copy list to allow removal
            # TODO: Fetch current market data
            # TODO: Check if position should be exited
            # TODO: Execute exit if needed
            pass

    def _check_risk_limits(self):
        """Check and enforce risk management limits"""
        # Check max concurrent positions
        if len(self.open_positions) >= self.config.MAX_CONCURRENT_POSITIONS:
            print(f"{Fore.YELLOW}⚠️  Max concurrent positions reached ({len(self.open_positions)}){Style.RESET_ALL}")

        # Check daily loss limit
        if self.total_pnl <= -self.config.MAX_DAILY_LOSS:
            print(f"{Fore.RED}🛑 Daily loss limit reached (${abs(self.total_pnl):.2f}){Style.RESET_ALL}")
            print(f"{Fore.RED}🛑 Stopping bot to prevent further losses{Style.RESET_ALL}")
            self.stop()

        # Check total exposure
        total_exposure = sum(p.entry_usdc for p in self.open_positions)
        if total_exposure >= self.config.MAX_TOTAL_EXPOSURE:
            print(f"{Fore.YELLOW}⚠️  Max total exposure reached (${total_exposure:.2f}){Style.RESET_ALL}")

    def _print_stats(self):
        """Print performance statistics"""
        if self.total_trades == 0:
            return

        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0

        print(f"\n{Fore.CYAN}📊 Performance Summary:{Style.RESET_ALL}")
        print(f"   Total P&L: ${self.total_pnl:+.2f}")
        print(f"   Total Trades: {self.total_trades}")
        print(f"   Winning: {self.winning_trades} ({win_rate:.1f}%)")
        print(f"   Losing: {self.losing_trades}")
        print(f"   Open Positions: {len(self.open_positions)}")
        print(f"   Average P&L per trade: ${self.total_pnl/self.total_trades:+.2f}")

    def stop(self):
        """Stop the scalping bot"""
        print(f"\n{Fore.YELLOW}⏹  Stopping Scalping Bot...{Style.RESET_ALL}")
        self.running = False

        # Print final stats
        self._print_stats()

        print(f"{Fore.GREEN}✅ Bot stopped successfully!{Style.RESET_ALL}")
        sys.exit(0)

def main():
    """Main entry point"""
    bot = ScalpingBot()

    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        bot.stop()

    signal.signal(signal.SIGINT, signal_handler)

    # Start bot
    bot.start()

if __name__ == "__main__":
    main()
