#!/usr/bin/env python3
"""
Test script to verify that expired/closed markets are filtered out
"""

import sys
import os
from datetime import datetime, timezone

# Add TRADE directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'TRADE'))

from utils.market_fetcher import MarketFetcher
from config.config import ScalpingConfig

def test_market_filtering():
    """Test that market fetching filters out expired markets"""

    print("🧪 Testing market filtering...")
    print(f"   Keywords: {ScalpingConfig.PREFERRED_MARKETS}")
    print()

    fetcher = MarketFetcher()

    # Fetch markets by keywords
    markets = fetcher.fetch_markets_by_keywords(
        ScalpingConfig.PREFERRED_MARKETS,
        limit=20
    )

    print(f"\n✅ Found {len(markets)} active markets")
    print()

    if len(markets) == 0:
        print("⚠️  WARNING: No markets found!")
        print("   This might be expected if there are no active crypto markets right now.")
        print("   Try setting HOURLY_MARKETS_ONLY=FALSE in .env to see more markets.")
        return

    # Display market details
    print("📊 Market Details:")
    print("=" * 100)

    now = datetime.now(timezone.utc)

    for i, market in enumerate(markets[:10], 1):  # Show first 10
        hours_remaining = (market.end_date - now).total_seconds() / 3600

        print(f"{i}. {market.question[:70]}")
        print(f"   Expires: {market.end_date.strftime('%Y-%m-%d %H:%M UTC')} ({hours_remaining:.1f}h remaining)")
        print(f"   Prices: Up=${market.price_up:.3f} Down=${market.price_down:.3f}")
        print()

    if len(markets) > 10:
        print(f"... and {len(markets) - 10} more markets")

    # Verify all markets are in the future
    expired_count = 0
    for market in markets:
        if market.end_date <= now:
            expired_count += 1
            print(f"❌ ERROR: Found expired market: {market.question[:60]}")

    if expired_count == 0:
        print(f"\n✅ SUCCESS: All {len(markets)} markets have future expiry dates!")
    else:
        print(f"\n❌ FAILURE: Found {expired_count} expired markets!")
        return False

    return True

if __name__ == "__main__":
    success = test_market_filtering()
    sys.exit(0 if success else 1)
