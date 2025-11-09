import time
import signal
import sys
from config.env import Config
from helpers.clob_client import create_clob_client
from services.data_fetcher import DataFetcher
from services.trade_monitor import TradeMonitor
from services.trade_executor import TradeExecutor
from storage.local_storage import LocalStorage
from colorama import Fore, Style, init

# Initialize colorama
init()

class CopyTradingBot:
    def __init__(self):
        self.storage = LocalStorage()
        self.data_fetcher = DataFetcher(self.storage)
        self.clob_client = None
        self.trade_monitor = None
        self.trade_executor = None
        
    def initialize(self):
        """Initialize the bot components"""
        print(f"{Fore.BLUE}🤖 Initializing Polymarket Copy Trading Bot...{Style.RESET_ALL}")

        # Check configuration
        print(f"🎯 Target trader: {Config.USER_ADDRESS}")
        print(f"👤 Your wallet: {Config.PROXY_WALLET}")
        print(f"⏱️ Fetch interval: {Config.FETCH_INTERVAL} seconds")

        # Clear old pending trades - only copy NEW trades from this point forward
        print(f"{Fore.YELLOW}🧹 Clearing old pending trades...{Style.RESET_ALL}")
        self.storage.clear_pending_trades(Config.USER_ADDRESS)
        print(f"{Fore.GREEN}✅ Only new trades will be copied{Style.RESET_ALL}")

        # Create CLOB client
        print(f"{Fore.YELLOW}🔑 Setting up CLOB client...{Style.RESET_ALL}")
        self.clob_client = create_clob_client()

        # Initialize services
        self.trade_monitor = TradeMonitor(self.storage, self.data_fetcher)
        self.trade_executor = TradeExecutor(self.clob_client, self.storage, self.data_fetcher)

        print(f"{Fore.GREEN}✅ Bot initialized successfully!{Style.RESET_ALL}")
    
    def start(self):
        """Start the copy trading bot"""
        try:
            self.initialize()
            
            # Start monitoring and execution
            self.trade_monitor.start_monitoring()
            self.trade_executor.start_executing()

            print(f"{Fore.GREEN}🚀 Copy Trading Bot is now running!{Style.RESET_ALL}")
            print(f"{Fore.CYAN}📊 Monitoring trades from {Config.USER_ADDRESS}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}💫 Press Ctrl+C to stop{Style.RESET_ALL}")
            
            # Keep the main thread alive
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.stop()
        except Exception as e:
            print(f"{Fore.RED}❌ Fatal error: {e}{Style.RESET_ALL}")
            self.stop()
    
    def stop(self):
        """Stop the copy trading bot"""
        print(f"\n{Fore.YELLOW}⏹ Stopping Copy Trading Bot...{Style.RESET_ALL}")

        if self.trade_monitor:
            self.trade_monitor.stop_monitoring()

        if self.trade_executor:
            self.trade_executor.stop_executing()

        print(f"{Fore.GREEN}✅ Bot stopped successfully!{Style.RESET_ALL}")
        sys.exit(0)

