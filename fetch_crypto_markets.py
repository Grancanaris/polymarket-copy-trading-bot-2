#!/usr/bin/env python3
"""
Fetch crypto markets similar to polymarket.com/crypto?tab=hourly
"""
import sys
import os
from datetime import datetime, timezone
import requests

# Try importing alternative HTTP libraries
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False

def is_crypto_market(question: str, description: str = '') -> bool:
    """
    Strict crypto market filter

    Returns True only if the market is clearly about cryptocurrency
    """
    text = (question + ' ' + description).lower()

    # Cryptocurrency names and symbols
    crypto_terms = [
        'bitcoin', 'btc',
        'ethereum', 'eth',
        'solana', 'sol',
        'cardano', 'ada',
        'polygon', 'matic',
        'dogecoin', 'doge',
        'xrp', 'ripple',
        'litecoin', 'ltc',
        'chainlink', 'link',
        'polkadot', 'dot',
        'avalanche', 'avax',
        'shiba', 'shib',
        'crypto', 'cryptocurrency',
        'usdt', 'usdc', 'tether',
        'binance', 'bnb',
        'coinbase',
        # Price targets
        '$50k btc', '$100k btc', '$50k ethereum', '$100k ethereum',
        'btc price', 'eth price', 'bitcoin price', 'ethereum price',
        # Crypto-specific terms
        'blockchain', 'defi', 'nft', 'token ',  # space after token to avoid matching other words
        'satoshi', 'mining', 'hash rate', 'proof of stake', 'proof of work',
        'smart contract', 'web3', 'dapp',
        'exchange', 'wallet',
        'halving', 'fork',
        'altcoin', 'memecoin',
        # Exchanges and protocols
        'kraken', 'ftx', 'uniswap', 'opensea', 'metamask',
    ]

    # Check if any crypto term is in the text
    has_crypto_term = any(term in text for term in crypto_terms)

    if not has_crypto_term:
        return False

    # Exclude false positives (these are often tagged with crypto but are about politics/economy)
    exclude_terms = [
        'fed rate', 'federal reserve', 'interest rate',
        'trump', 'biden', 'president', 'election',
        'putin', 'russia', 'ukraine', 'nato',
        'israel', 'netanyahu', 'iran', 'khamenei',
        'recession', 'gdp', 'unemployment',
        'supreme court', 'senate', 'congress',
        'nuclear weapon',
    ]

    has_exclude_term = any(term in text for term in exclude_terms)

    if has_exclude_term:
        return False

    return True


def make_request(url: str, params: dict = None):
    """Make HTTP request with fallback methods"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    # Try httpx
    if HAS_HTTPX:
        try:
            response = httpx.get(url, params=params, timeout=15)
            if response.status_code == 200:
                return response.json()
        except:
            pass

    # Try cloudscraper
    if HAS_CLOUDSCRAPER:
        try:
            scraper = cloudscraper.create_scraper()
            response = scraper.get(url, params=params, timeout=15)
            if response.status_code == 200:
                return response.json()
        except:
            pass

    # Try requests
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()
    except:
        pass

    return None


def fetch_crypto_markets_by_volume(limit: int = 50):
    """
    Fetch crypto markets sorted by volume (similar to /crypto?tab=hourly)

    Strategy:
    1. Fetch all active markets from Gamma API
    2. Apply strict crypto filter
    3. Sort by 24h volume
    4. Return top markets
    """
    print("="*80)
    print("FETCHING CRYPTO MARKETS (sorted by volume)")
    print("="*80)

    # Fetch all active markets
    print("\n🔍 Fetching active markets from Polymarket API...")

    try:
        # Try Gamma API (more reliable than CLOB for listing)
        url = "https://gamma-api.polymarket.com/markets"
        params = {
            'closed': 'false',
            'limit': 200,
        }

        markets_data = make_request(url, params)

        if not markets_data:
            print("❌ Failed to fetch markets from API")
            return []

        # Handle dict response
        if isinstance(markets_data, dict):
            if 'data' in markets_data:
                markets_data = markets_data['data']
            elif 'markets' in markets_data:
                markets_data = markets_data['markets']

        if not isinstance(markets_data, list):
            print(f"❌ Unexpected response type: {type(markets_data)}")
            return []

        print(f"✅ Fetched {len(markets_data)} total markets")

        # Parse and filter crypto markets
        print("\n🔍 Filtering for crypto markets...")

        crypto_markets = []

        for market_data in markets_data:
            question = market_data.get('question', '')
            description = market_data.get('description', '')

            # Apply strict crypto filter
            if is_crypto_market(question, description):
                # Skip closed/inactive markets
                closed = market_data.get('closed', False)
                active = market_data.get('active', True)
                if closed or not active:
                    continue

                # Get basic market info
                volume_24h = float(market_data.get('volume24hr', 0))
                liquidity = float(market_data.get('liquidity', 0))
                condition_id = market_data.get('conditionId', '')
                slug = market_data.get('slug', '')

                # Get outcomes and prices
                outcomes = market_data.get('outcomes', ['Yes', 'No'])

                # Parse outcome prices
                outcome_prices = market_data.get('outcomePrices')
                if isinstance(outcome_prices, str):
                    import json
                    try:
                        outcome_prices = json.loads(outcome_prices)
                    except:
                        outcome_prices = ['0.5', '0.5']

                if isinstance(outcome_prices, list) and len(outcome_prices) >= 2:
                    price_0 = float(outcome_prices[0])
                    price_1 = float(outcome_prices[1])
                else:
                    price_0 = 0.5
                    price_1 = 0.5

                # Get end date
                end_date_str = market_data.get('endDate', market_data.get('end_date_iso'))
                if end_date_str:
                    try:
                        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                        # Skip expired markets
                        if end_date <= datetime.now(timezone.utc):
                            continue
                    except:
                        end_date = None
                else:
                    end_date = None

                market_info = {
                    'question': question,
                    'condition_id': condition_id,
                    'slug': slug,
                    'volume_24h': volume_24h,
                    'liquidity': liquidity,
                    'price_0': price_0,
                    'price_1': price_1,
                    'outcomes': outcomes,
                    'end_date': end_date,
                }

                crypto_markets.append(market_info)
                print(f"   ✅ {question[:70]}")

        print(f"\n✅ Found {len(crypto_markets)} crypto markets")

        # Sort by 24h volume (descending)
        crypto_markets.sort(key=lambda m: m['volume_24h'], reverse=True)

        # Print top markets
        print("\n" + "="*80)
        print("TOP CRYPTO MARKETS BY VOLUME")
        print("="*80)

        for i, market in enumerate(crypto_markets[:limit], 1):
            if market['end_date']:
                hours_left = (market['end_date'] - datetime.now(timezone.utc)).total_seconds() / 3600
                expiry_str = f"{hours_left:.1f} hours"
            else:
                expiry_str = "Unknown"

            print(f"\n{i}. {market['question']}")
            print(f"   Condition ID: {market['condition_id']}")
            print(f"   Outcomes: {market['outcomes'][0]} (${market['price_0']:.3f}) / {market['outcomes'][1]} (${market['price_1']:.3f})")
            print(f"   Volume 24h: ${market['volume_24h']:,.0f}")
            print(f"   Liquidity: ${market['liquidity']:,.0f}")
            print(f"   Expires in: {expiry_str}")
            if market['slug']:
                print(f"   URL: https://polymarket.com/event/{market['slug']}")

        return crypto_markets[:limit]

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Fetch crypto markets from Polymarket')
    parser.add_argument('--limit', type=int, default=20, help='Number of markets to fetch (default: 20)')
    parser.add_argument('--hourly-only', action='store_true', help='Only show markets expiring within 1.5 hours')

    args = parser.parse_args()

    markets = fetch_crypto_markets_by_volume(limit=args.limit)

    if args.hourly_only:
        # Filter to only markets expiring within 1.5 hours
        hourly_markets = []
        for m in markets:
            if m['end_date']:
                hours_left = (m['end_date'] - datetime.now(timezone.utc)).total_seconds() / 3600
                if hours_left <= 1.5:
                    hourly_markets.append(m)

        print(f"\n{'='*80}")
        print(f"HOURLY CRYPTO MARKETS: {len(hourly_markets)}")
        print(f"{'='*80}")

        for i, market in enumerate(hourly_markets, 1):
            hours_left = (market['end_date'] - datetime.now(timezone.utc)).total_seconds() / 3600
            print(f"\n{i}. {market['question']}")
            print(f"   Expires in: {hours_left:.1f} hours")
            print(f"   Price: ${market['price_0']:.3f}")
            print(f"   Volume 24h: ${market['volume_24h']:,.0f}")
