import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

class ScalpingConfig:
    # Wallet configuration
    PROXY_WALLET = os.getenv('PROXY_WALLET')
    if not PROXY_WALLET:
        raise ValueError("PROXY_WALLET is required")

    PRIVATE_KEY = os.getenv('PK')
    if not PRIVATE_KEY:
        raise ValueError('PK is required')

    # API URLs
    HOST = os.getenv('HOST', 'https://clob.polymarket.com')
    POLYMARKET_API_URL = os.getenv('POLYMARKET_API_URL', 'https://gamma-api.polymarket.com')

    # Trading parameters
    SCAN_INTERVAL = float(os.getenv('SCAN_INTERVAL', '0.1'))
    MAX_POSITION_SIZE = float(os.getenv('MAX_POSITION_SIZE', '50.0'))
    MAX_TOTAL_EXPOSURE = float(os.getenv('MAX_TOTAL_EXPOSURE', '500.0'))
    MIN_TRADE_SIZE = float(os.getenv('MIN_TRADE_SIZE', '1.0'))

    # Binary Arbitrage Strategy
    ENABLE_ARBITRAGE = os.getenv('ENABLE_ARBITRAGE', 'true').lower() == 'true'
    ARB_MIN_PROFIT = float(os.getenv('ARB_MIN_PROFIT', '0.01'))  # 1¢ minimum
    ARB_POSITION_SIZE = int(os.getenv('ARB_POSITION_SIZE', '10'))

    # Momentum Scalping Strategy
    ENABLE_MOMENTUM = os.getenv('ENABLE_MOMENTUM', 'true').lower() == 'true'
    MOMENTUM_PROFIT_TARGET = float(os.getenv('MOMENTUM_PROFIT_TARGET', '0.02'))  # 2¢
    MOMENTUM_STOP_LOSS = float(os.getenv('MOMENTUM_STOP_LOSS', '0.05'))  # 5¢
    MOMENTUM_PRICE_CHANGE_THRESHOLD = float(os.getenv('MOMENTUM_PRICE_CHANGE_THRESHOLD', '0.03'))
    MOMENTUM_POSITION_SIZES = [int(x) for x in os.getenv('MOMENTUM_POSITION_SIZES', '10,37,62,75').split(',')]

    # Mean Reversion Strategy
    ENABLE_MEAN_REVERSION = os.getenv('ENABLE_MEAN_REVERSION', 'true').lower() == 'true'
    MEAN_REV_ENTRY_HIGH = float(os.getenv('MEAN_REV_ENTRY_HIGH', '0.70'))
    MEAN_REV_ENTRY_LOW = float(os.getenv('MEAN_REV_ENTRY_LOW', '0.30'))
    MEAN_REV_EXIT_TARGET = float(os.getenv('MEAN_REV_EXIT_TARGET', '0.50'))
    MEAN_REV_PROFIT_TARGET = float(os.getenv('MEAN_REV_PROFIT_TARGET', '0.05'))

    # Market Making Strategy
    ENABLE_MARKET_MAKING = os.getenv('ENABLE_MARKET_MAKING', 'false').lower() == 'true'
    MM_SPREAD_TARGET = float(os.getenv('MM_SPREAD_TARGET', '0.02'))
    MM_ORDER_SIZE = int(os.getenv('MM_ORDER_SIZE', '10'))

    # Market selection
    # Expanded crypto keywords to catch more crypto-related markets
    default_keywords = 'bitcoin,ethereum,btc,eth,crypto,cryptocurrency,solana,cardano,polygon,matic'
    PREFERRED_MARKETS = os.getenv('PREFERRED_MARKETS', default_keywords).split(',')
    HOURLY_MARKETS_ONLY = os.getenv('HOURLY_MARKETS_ONLY', 'true').lower() == 'true'
    MAX_DAYS_TO_EXPIRY = int(os.getenv('MAX_DAYS_TO_EXPIRY', '1'))

    # Risk management
    MAX_LOSS_PER_TRADE = float(os.getenv('MAX_LOSS_PER_TRADE', '5.0'))
    MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', '50.0'))
    MAX_CONCURRENT_POSITIONS = int(os.getenv('MAX_CONCURRENT_POSITIONS', '10'))
    POSITION_HOLD_TIME = int(os.getenv('POSITION_HOLD_TIME', '300'))  # 5 minutes

    # Web3 config
    RPC_URL = os.getenv('RPC_URL', 'https://polygon-rpc.com')
    USDC_CONTRACT_ADDRESS = os.getenv('USDC_CONTRACT_ADDRESS', '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')
