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
        """Claim available rewards"""
        try:
            # Get unclaimed rewards
            rewards = self.clob_client.get_unclaimed_rewards()

            if rewards and len(rewards) > 0:
                total_rewards = sum(float(r.get('amount', 0)) for r in rewards)

                if total_rewards > 0:
                    print(f"{Fore.CYAN}💰 Claiming ${total_rewards:.2f} in rewards...{Style.RESET_ALL}")

                    # Claim rewards
                    result = self.clob_client.claim_rewards()

                    if result.get('success', False):
                        print(f"{Fore.GREEN}✅ Successfully claimed ${total_rewards:.2f}!{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.YELLOW}⚠️ Claim result: {result}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.BLUE}ℹ️ No rewards available to claim{Style.RESET_ALL}")
            else:
                print(f"{Fore.BLUE}ℹ️ No unclaimed rewards found{Style.RESET_ALL}")

        except AttributeError:
            # Method might not exist in this version of py_clob_client
            print(f"{Fore.YELLOW}⚠️ Rewards claiming not supported in this client version{Style.RESET_ALL}")
            self.running = False  # Stop trying if method doesn't exist
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️ Could not claim rewards: {e}{Style.RESET_ALL}")
