import time
import threading
from typing import List, Optional, Tuple
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from config.env import Config
from services.data_fetcher import DataFetcher
from storage.local_storage import LocalStorage
from models.user_activity import UserActivity, UserPosition
from colorama import Fore, Style

class TradeExecutor:
    def __init__(self, clob_client: ClobClient, storage: LocalStorage, data_fetcher: DataFetcher):
        self.clob_client = clob_client
        self.storage = storage
        self.data_fetcher = data_fetcher
        self.target_wallet = Config.USER_ADDRESS
        self.my_wallet = Config.PROXY_WALLET
        self.running = False
        
    def start_executing(self):
        """Start trade execution in a separate thread"""
        self.running = True
        executor_thread = threading.Thread(target=self._execution_loop, daemon=True)
        executor_thread.start()
        print(f"{Fore.GREEN}✅ Trade executor started{Style.RESET_ALL}")
        
    def stop_executing(self):
        """Stop trade execution"""
        self.running = False
        print(f"{Fore.YELLOW}⏹ Trade executor stopped{Style.RESET_ALL}")
    
    def _execution_loop(self):
        """Main execution loop"""
        while self.running:
            try:
                pending_trades = self.storage.get_pending_trades(self.target_wallet)
                
                if pending_trades:
                    print(f"{Fore.CYAN}⚡ Processing {len(pending_trades)} pending trades{Style.RESET_ALL}")
                    
                    for trade in pending_trades:
                        try:
                            success = self._execute_trade(trade)
                            self.storage.mark_trade_executed(
                                self.target_wallet, 
                                trade.id, 
                                success
                            )
                        except Exception as e:
                            print(f"{Fore.RED}❌ Error executing trade {trade.id}: {e}{Style.RESET_ALL}")
                            self.storage.mark_trade_executed(
                                self.target_wallet, 
                                trade.id, 
                                False
                            )
                
                time.sleep(2)  # Check every 2 seconds for pending trades
                
            except Exception as e:
                print(f"{Fore.RED}❌ Error in execution loop: {e}{Style.RESET_ALL}")
                time.sleep(5)
    
    def _execute_trade(self, trade: UserActivity) -> bool:
        """Execute a single trade with sophisticated copy logic"""
        try:
            print(f"{Fore.BLUE}🔄 Executing copy trade for {trade.title}...{Style.RESET_ALL}")
            
            # Get current positions
            my_positions = self.data_fetcher.fetch_user_positions(self.my_wallet)
            target_positions = self.data_fetcher.fetch_user_positions(self.target_wallet)
            
            # Get current balances
            my_balance = self.data_fetcher.get_balance(self.my_wallet)
            target_balance = self.data_fetcher.get_balance(self.target_wallet)
            
            print(f"💰 My balance: ${my_balance:.2f} | Target balance: ${target_balance:.2f}")
            
            # Find relevant positions
            my_position = next(
                (pos for pos in my_positions if pos.condition_id == trade.condition_id), 
                None
            )
            target_position = next(
                (pos for pos in target_positions if pos.condition_id == trade.condition_id), 
                None
            )
            
            # Determine trading strategy
            strategy = self._determine_strategy(trade, my_position, target_position)
            
            # Execute based on strategy
            if strategy == 'buy':
                return self._execute_buy_strategy(trade, my_balance, target_balance)
            elif strategy == 'sell':
                return self._execute_sell_strategy(trade, my_position, target_position)
            elif strategy == 'merge':
                return self._execute_merge_strategy(trade, my_position)
            else:
                print(f"{Fore.YELLOW}⚠️ No strategy determined for trade{Style.RESET_ALL}")
                return True  # Mark as handled
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error in _execute_trade: {e}{Style.RESET_ALL}")
            return False
    
    def _determine_strategy(self, trade: UserActivity, my_position: Optional[UserPosition], 
                          target_position: Optional[UserPosition]) -> str:
        """Determine the appropriate trading strategy"""
        
        if trade.type == 'MERGE':
            return 'merge'
        
        if trade.side == 'BUY':
            return 'buy'
        elif trade.side == 'SELL':
            return 'sell'
        
        return 'skip'
    
    def _execute_buy_strategy(self, trade: UserActivity, my_balance: float,
                            target_balance: float) -> bool:
        """Execute buy strategy with proportional sizing"""
        try:
            if my_balance < 1.0:  # Minimum balance check
                print(f"{Fore.YELLOW}⚠️ Insufficient balance to copy buy trade{Style.RESET_ALL}")
                return True

            # Calculate proportional size based on balance ratio
            balance_ratio = min(my_balance / (target_balance + trade.usdc_size), 1.0)
            copy_amount_proportional = trade.usdc_size * balance_ratio

            # Use minimum of $1.00 or proportional amount (whichever is larger, but capped at balance)
            min_trade_size = 1.0
            copy_amount = max(min_trade_size, copy_amount_proportional)
            copy_amount = min(copy_amount, my_balance * 0.2)  # Max 20% of balance per trade

            # Final minimum check
            if copy_amount < 0.5:
                print(f"{Fore.YELLOW}⚠️ Copy amount too small: ${copy_amount:.2f} (would need at least $0.50){Style.RESET_ALL}")
                return True

            # Round to 2 decimals for Polymarket precision requirements
            # Taker amount (USDC amount) must have max 2 decimal places
            copy_amount = round(copy_amount, 2)

            print(f"📈 Buying ${copy_amount:.2f} worth of {trade.outcome}")

            # OPTIMIZATION: Skip price checking for fastest execution
            # In copy trading, speed is critical - we accept current market price
            # to ensure we get filled before price moves further

            # Create market buy order
            market_order_args = MarketOrderArgs(
                token_id=trade.asset,
                amount=copy_amount,
                side=BUY
            )

            signed_order = self.clob_client.create_market_order(market_order_args)
            # Use GTC (Good Till Cancel) instead of FOK for better fill rates in fast markets
            response = self.clob_client.post_order(signed_order, OrderType.GTC)
            
            if response.get('success', False):
                print(f"{Fore.GREEN}✅ Successfully bought ${copy_amount:.2f} worth{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Buy order failed: {response}{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error in buy strategy: {e}{Style.RESET_ALL}")
            return False
    
    def _execute_sell_strategy(self, trade: UserActivity, my_position: Optional[UserPosition], 
                         target_position: Optional[UserPosition]) -> bool:
        """Execute sell strategy using limit orders at market price"""
        try:
            # Check if we have a position to sell
            if not my_position or my_position.size <= 0:
                print(f"{Fore.YELLOW}⚠️ No position to sell for {trade.outcome}{Style.RESET_ALL}")
                return True
            
            print(f"📊 Current position: {my_position.size:.2f} shares of {trade.outcome}")
            print(f"📉 Target is selling: {trade.size:.2f} shares")
            
            # 1:1 copy selling with safety checks
            sell_amount = min(trade.size, my_position.size)
            
            # Add a small buffer to prevent rounding errors
            sell_amount = sell_amount * 0.999
            
            if trade.size > my_position.size:
                print(f"{Fore.YELLOW}⚠️ Target sold {trade.size:.2f} shares but you only have {my_position.size:.2f}. Selling {sell_amount:.2f}{Style.RESET_ALL}")
            
            # Minimum sell amount check
            if sell_amount < 0.01:
                print(f"{Fore.YELLOW}⚠️ Sell amount too small: {sell_amount:.3f} shares{Style.RESET_ALL}")
                return True
            
            print(f"💰 Attempting to sell {sell_amount:.2f} shares of {trade.outcome}")
            
            # Get orderbook to find best bid price
            try:
                orderbook = self.clob_client.get_order_book(trade.asset)
                
                if not orderbook.bids or len(orderbook.bids) == 0:
                    print(f"{Fore.RED}❌ No bids available in orderbook{Style.RESET_ALL}")
                    return False
                
                # Find best bid (highest price someone is willing to pay)
                best_bid_price = max(float(bid.price) for bid in orderbook.bids)
                print(f"💵 Best bid price: ${best_bid_price:.3f}")
                
            except Exception as e:
                print(f"{Fore.YELLOW}⚠️ Could not get orderbook, using trade price: {e}{Style.RESET_ALL}")
                best_bid_price = trade.price

            # Round to Polymarket precision requirements
            sell_amount_rounded = round(sell_amount, 2)  # Size: max 2 decimals
            best_bid_price = round(best_bid_price, 4)    # Price: max 4 decimals

            print(f"📝 Creating LIMIT sell order: {sell_amount_rounded} shares at ${best_bid_price:.4f}")
            
            # Import SELL constant
            from py_clob_client.order_builder.constants import SELL
            
            # Use OrderArgs (limit order) instead of MarketOrderArgs
            order_args = OrderArgs(
                token_id=trade.asset,
                price=best_bid_price,
                size=sell_amount_rounded,
                side=SELL
            )
            
            # Create and sign the order
            signed_order = self.clob_client.create_order(order_args)

            # Use GTC for better fill rates in fast-moving markets
            response = self.clob_client.post_order(signed_order, OrderType.GTC)
            
            if response.get('success', False):
                print(f"{Fore.GREEN}✅ Successfully sold {sell_amount_rounded:.2f} shares at ${best_bid_price:.3f}{Style.RESET_ALL}")
                return True
            else:
                error_msg = response.get('error', response)
                print(f"{Fore.RED}❌ Sell order failed: {error_msg}{Style.RESET_ALL}")
                
                # Try with a slightly lower amount if balance error
                if 'balance' in str(error_msg).lower():
                    retry_amount = round(sell_amount_rounded * 0.95, 2)  # Try 95%
                    print(f"{Fore.YELLOW}🔄 Retrying with {retry_amount:.2f} shares...{Style.RESET_ALL}")
                    
                    order_args_retry = OrderArgs(
                        token_id=trade.asset,
                        price=best_bid_price,
                        size=retry_amount,
                        side=SELL
                    )
                    
                    signed_order_retry = self.clob_client.create_order(order_args_retry)
                    response_retry = self.clob_client.post_order(signed_order_retry, OrderType.GTC)
                    
                    if response_retry.get('success', False):
                        print(f"{Fore.GREEN}✅ Successfully sold {retry_amount:.2f} shares on retry{Style.RESET_ALL}")
                        return True
                
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error in sell strategy: {e}{Style.RESET_ALL}")
            import traceback
            traceback.print_exc()
            return False
    
    def _execute_merge_strategy(self, trade: UserActivity, my_position: Optional[UserPosition]) -> bool:
        """Execute merge strategy (close position at best available price)"""
        try:
            if not my_position or my_position.size <= 0:
                print(f"{Fore.YELLOW}⚠️ No position to merge{Style.RESET_ALL}")
                return True
            
            print(f"🔄 Merging position: {my_position.size:.2f} shares")
            
            # Get orderbook to find best price
            orderbook = self.clob_client.get_order_book(trade.asset)
            
            if not orderbook.bids or len(orderbook.bids) == 0:
                print(f"{Fore.RED}❌ No bids available for merge{Style.RESET_ALL}")
                return False
            
            # Find best bid price and round to Polymarket precision
            best_bid_price = max(float(bid.price) for bid in orderbook.bids)
            best_bid_price = round(best_bid_price, 4)  # Price: max 4 decimals
            print(f"💰 Best bid price: ${best_bid_price:.4f}")

            # Import SELL constant
            from py_clob_client.order_builder.constants import SELL

            # Create limit sell order at best bid price
            order_args = OrderArgs(
                token_id=trade.asset,
                price=best_bid_price,
                size=round(my_position.size * 0.999, 2),  # Size: max 2 decimals
                side=SELL
            )
            
            signed_order = self.clob_client.create_order(order_args)
            response = self.clob_client.post_order(signed_order, OrderType.GTC)

            if response.get('success', False):
                print(f"{Fore.GREEN}✅ Successfully merged position{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.RED}❌ Merge failed: {response}{Style.RESET_ALL}")
                return False
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error in merge strategy: {e}{Style.RESET_ALL}")
            return False
