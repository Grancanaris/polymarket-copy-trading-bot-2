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

                        # Try to redeem each position through CTF contract
                        for position in redeemable_positions:
                            try:
                                title = position.get('title', 'Unknown')
                                value = float(position.get('currentValue', 0))

                                # Skip positions with 0 value
                                if value < 0.01:
                                    print(f"{Fore.BLUE}  ⏭️ Skipping {title}: $0.00{Style.RESET_ALL}")
                                    continue

                                print(f"{Fore.YELLOW}  🔄 Attempting to redeem: {title} (${value:.2f}){Style.RESET_ALL}")

                                condition_id = position.get('conditionId')
                                if not condition_id:
                                    print(f"{Fore.RED}  ❌ No condition ID found{Style.RESET_ALL}")
                                    continue

                                # Try using the CLOB client's built-in redemption if available
                                try:
                                    # Check if the client has a redeem method
                                    if hasattr(self.clob_client, 'redeem_position'):
                                        result = self.clob_client.redeem_position(condition_id)
                                        if result.get('success', False):
                                            print(f"{Fore.GREEN}  ✅ Successfully redeemed ${value:.2f} from {title}!{Style.RESET_ALL}")
                                        else:
                                            print(f"{Fore.YELLOW}  ⚠️ Redemption failed: {result.get('error', result)}{Style.RESET_ALL}")
                                    else:
                                        # Manual notification - automatic redemption requires on-chain transaction
                                        # which is complex with proxy wallets
                                        print(f"{Fore.YELLOW}  ⚠️ Automatic redemption not available{Style.RESET_ALL}")
                                        print(f"{Fore.CYAN}     Please visit https://polymarket.com/portfolio to claim ${value:.2f}{Style.RESET_ALL}")

                                except Exception as e:
                                    print(f"{Fore.YELLOW}  ⚠️ Could not redeem: {e}{Style.RESET_ALL}")
                                    print(f"{Fore.CYAN}     Please claim manually: https://polymarket.com/portfolio{Style.RESET_ALL}")

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

