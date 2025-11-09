import time
import threading
from py_clob_client.client import ClobClient
from colorama import Fore, Style

class RewardsClaimer:
    def __init__(self, clob_client: ClobClient):
        self.clob_client = clob_client
        self.running = False
        self.claim_interval = 300  # 5 minutes in seconds

    def start_claiming(self):
        """Start rewards claiming in a separate thread"""
        self.running = True
        claimer_thread = threading.Thread(target=self._claiming_loop, daemon=True)
        claimer_thread.start()
        print(f"{Fore.GREEN}✅ Rewards claimer started (every 5 minutes){Style.RESET_ALL}")

    def stop_claiming(self):
        """Stop rewards claiming"""
        self.running = False
        print(f"{Fore.YELLOW}⏹ Rewards claimer stopped{Style.RESET_ALL}")

    def _claiming_loop(self):
        """Main claiming loop"""
        while self.running:
            try:
                self._claim_rewards()
                time.sleep(self.claim_interval)
            except Exception as e:
                print(f"{Fore.RED}❌ Error in claiming loop: {e}{Style.RESET_ALL}")
                time.sleep(self.claim_interval)

    def _claim_rewards(self):
        """Claim available rewards from resolved positions"""
        try:
            # Try to get earnings/rewards using available client methods
            # Check for redeemable positions
            try:
                # Get all positions
                import requests
                from config.env import Config

                response = requests.get(
                    f"{Config.POLYMARKET_API_URL}/positions",
                    params={'user': Config.PROXY_WALLET},
                    timeout=10
                )

                if response.status_code == 200:
                    positions = response.json()
                    redeemable_positions = [p for p in positions if p.get('redeemable', False)]

                    if redeemable_positions:
                        total_value = sum(float(p.get('currentValue', 0)) for p in redeemable_positions)
                        print(f"{Fore.CYAN}💰 Found {len(redeemable_positions)} redeemable position(s) worth ${total_value:.2f}{Style.RESET_ALL}")

                        # Try to redeem each position automatically
                        for position in redeemable_positions:
                            try:
                                title = position.get('title', 'Unknown')
                                value = float(position.get('currentValue', 0))

                                # Skip positions with 0 value
                                if value < 0.01:
                                    print(f"{Fore.BLUE}  ⏭️ Skipping {title}: $0.00{Style.RESET_ALL}")
                                    continue

                                print(f"{Fore.YELLOW}  🔄 Attempting to redeem: {title} (${value:.2f}){Style.RESET_ALL}")

                                # Get the token ID from the position
                                token_id = position.get('asset') or position.get('assetId')
                                if not token_id:
                                    print(f"{Fore.RED}  ❌ No token ID found for position{Style.RESET_ALL}")
                                    continue

                                # Try to sell the entire position at market price to close it out
                                # This effectively "redeems" by converting to USDC
                                try:
                                    # Get current size
                                    size = float(position.get('size', 0))
                                    if size <= 0:
                                        continue

                                    # Get orderbook to find best bid
                                    orderbook = self.clob_client.get_order_book(token_id)

                                    if not orderbook.bids or len(orderbook.bids) == 0:
                                        print(f"{Fore.YELLOW}  ⚠️ No market liquidity to redeem{Style.RESET_ALL}")
                                        continue

                                    # For redeemable positions, they should be worth ~$1.00
                                    # We can sell at any reasonable price since they're resolved
                                    best_bid_price = max(float(bid.price) for bid in orderbook.bids)

                                    # Only redeem if price is reasonable (>0.95 for winning positions)
                                    if best_bid_price < 0.95:
                                        print(f"{Fore.YELLOW}  ⚠️ Price too low (${best_bid_price:.3f}), waiting for better liquidity{Style.RESET_ALL}")
                                        continue

                                    # Create sell order
                                    from py_clob_client.clob_types import OrderArgs, OrderType
                                    from py_clob_client.order_builder.constants import SELL

                                    order_args = OrderArgs(
                                        token_id=token_id,
                                        price=best_bid_price,
                                        size=round(size, 2),
                                        side=SELL
                                    )

                                    signed_order = self.clob_client.create_order(order_args)
                                    response = self.clob_client.post_order(signed_order, OrderType.FOK)

                                    if response.get('success', False):
                                        actual_value = size * best_bid_price
                                        print(f"{Fore.GREEN}  ✅ Successfully redeemed ${actual_value:.2f} from {title}!{Style.RESET_ALL}")
                                    else:
                                        error = response.get('error', response)
                                        print(f"{Fore.YELLOW}  ⚠️ Could not auto-redeem: {error}{Style.RESET_ALL}")

                                except Exception as e:
                                    print(f"{Fore.YELLOW}  ⚠️ Error redeeming via market: {e}{Style.RESET_ALL}")

                            except Exception as e:
                                print(f"{Fore.YELLOW}  ⚠️ Could not process position: {e}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.BLUE}ℹ️  No redeemable positions found{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}⚠️ Could not fetch positions for claiming{Style.RESET_ALL}")

            except Exception as e:
                print(f"{Fore.YELLOW}⚠️ Could not check for redeemable positions: {e}{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ Error in rewards claiming: {e}{Style.RESET_ALL}")

