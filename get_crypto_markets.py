#!/usr/bin/env python3
"""
Fetch crypto markets from Polymarket (similar to polymarket.com/crypto?tab=hourly)

This script:
1. Fetches all active markets from Polymarket API
2. Applies strict crypto filtering to remove false positives
3. Sorts by 24h volume (similar to the hourly tab)
4. Displays the results

Usage:
  python get_crypto_markets.py
  python get_crypto_markets.py --limit 30
  python get_crypto_markets.py --hourly-only
"""

import sys
import os

# Set environment variables before importing config
os.environ.setdefault('PROXY_WALLET', '0x0000000000000000000000000000000000000000')
os.environ.setdefault('PK', '0x0000000000000000000000000000000000000000000000000000000000000000')
os.environ.setdefault('USER_ADDRESS', '0x0000000000000000000000000000000000000000')

# Add TRADE directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'TRADE'))

from utils.market_fetcher import MarketFetcher
from datetime import datetime, timezone


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Fetch crypto markets from Polymarket')
    parser.add_argument('--limit', type=int, default=25, help='Number of markets to display (default: 25)')
    parser.add_argument('--hourly-only', action='store_true', help='Only show markets expiring within 1.5 hours')

    args = parser.parse_args()

    print("=" * 80)
    print("FETCHING CRYPTO MARKETS FROM POLYMARKET")
    print("=" * 80)

    fetcher = MarketFetcher()

    # Fetch markets using keyword search with crypto filter enabled
    keywords = ['bitcoin', 'ethereum', 'crypto', 'btc', 'eth', 'solana', 'cardano',
                'polygon', 'dogecoin', 'xrp', 'blockchain', 'defi', 'nft']

    print(f"\n🔍 Searching for crypto markets...")
    print(f"📋 Keywords: {', '.join(keywords[:5])}...")

    markets = fetcher.fetch_markets_by_keywords(keywords, limit=50)

    if not markets:
        print("\n❌ No crypto markets found!")
        print("\nPossible reasons:")
        print("  • API is being blocked (Cloudflare protection)")
        print("  • No active crypto markets available")
        print("  • Network connection issues")
        return

    print(f"\n✅ Found {len(markets)} crypto markets")

    # Sort by volume
    markets.sort(key=lambda m: m.volume_24h, reverse=True)

    # Filter hourly if requested
    if args.hourly_only:
        hourly_markets = [m for m in markets if m.is_hourly_market]
        print(f"\n🕐 Filtered to {len(hourly_markets)} hourly markets (expiring within 1.5 hours)")
        markets = hourly_markets

    # Display markets
    print("\n" + "=" * 80)
    print(f"TOP CRYPTO MARKETS BY VOLUME")
    if args.hourly_only:
        print("(Hourly markets only - expiring within 1.5 hours)")
    print("=" * 80)

    for i, market in enumerate(markets[:args.limit], 1):
        hours_left = market.hours_to_expiry

        print(f"\n{i}. {market.question}")
        print(f"   ID: {market.condition_id}")
        print(f"   Prices: {market.outcomes[0]} ${market.price_up:.3f} / {market.outcomes[1]} ${market.price_down:.3f}")
        print(f"   Volume 24h: ${market.volume_24h:,.0f}")
        print(f"   Liquidity: ${market.liquidity:,.0f}")
        print(f"   Expires in: {hours_left:.1f} hours")

        if market.best_bid_up and market.best_ask_up:
            spread = market.best_ask_up - market.best_bid_up
            print(f"   Spread: ${spread:.4f} ({spread/market.price_up*100:.2f}%)")

        if market.slug:
            print(f"   URL: https://polymarket.com/event/{market.slug}")

    print("\n" + "=" * 80)
    print(f"Total: {len(markets)} crypto markets")
    print("=" * 80)


if __name__ == "__main__":
    main()
