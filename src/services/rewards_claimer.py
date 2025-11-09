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

                        # Note: For Polymarket proxy wallets, automatic redemption is complex
                        # The positions are owned by the proxy contract, not the EOA
                        # For now, notify the user to redeem manually
                        print(f"{Fore.YELLOW}⚠️  Auto-redemption for proxy wallets requires manual action{Style.RESET_ALL}")
                        print(f"{Fore.CYAN}   Please visit https://polymarket.com/portfolio to claim your winnings{Style.RESET_ALL}")

                        # List the redeemable positions for the user
                        for position in redeemable_positions:
                            print(f"{Fore.BLUE}   • {position.get('title', 'Unknown')}: ${position.get('currentValue', 0):.2f}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.BLUE}ℹ️  No redeemable positions found{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}⚠️ Could not fetch positions for claiming{Style.RESET_ALL}")

            except Exception as e:
                print(f"{Fore.YELLOW}⚠️ Could not check for redeemable positions: {e}{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ Error in rewards claiming: {e}{Style.RESET_ALL}")

