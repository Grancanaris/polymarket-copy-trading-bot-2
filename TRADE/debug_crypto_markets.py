#!/usr/bin/env python3
"""
Debug script to inspect the actual API structure for crypto markets
"""

import requests
import json

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
except ImportError:
    HAS_CLOUDSCRAPER = False
    print("⚠️  cloudscraper not installed. Install with: pip install cloudscraper")

def debug_crypto_markets():
    """Fetch and inspect crypto market structure"""

    # Fetch bitcoin markets
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        'closed': 'false',
        'limit': 10,
        'query': 'bitcoin'  # Search for bitcoin markets
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    print(f"🔍 Fetching bitcoin markets from {url}")
    print(f"📊 Params: {params}\n")

    try:
        # Use cloudscraper if available, otherwise regular requests
        if HAS_CLOUDSCRAPER:
            print("🔧 Using cloudscraper to bypass Cloudflare...")
            scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False
                }
            )
            response = scraper.get(url, params=params, timeout=10)
        else:
            print("🔧 Using regular requests...")
            response = requests.get(url, params=params, headers=headers, timeout=10)

        response.raise_for_status()

        markets_data = response.json()

        if not isinstance(markets_data, list):
            print(f"❌ Unexpected response type: {type(markets_data)}")
            return

        print(f"✅ Received {len(markets_data)} markets\n")

        if len(markets_data) == 0:
            print("❌ No markets found!")
            return

        # Inspect first market in detail
        market = markets_data[0]

        print("=" * 80)
        print("MARKET STRUCTURE")
        print("=" * 80)
        print(f"\n📋 Question: {market.get('question', 'Unknown')}\n")
        print(f"🔑 Available fields ({len(market.keys())} total):")
        for key in sorted(market.keys()):
            value = market[key]
            value_type = type(value).__name__

            # Show value for important fields
            if key in ['conditionId', 'question', 'outcomes', 'clobTokenIds', 'tokens', 'events', 'lastTradePrice', 'bestBid', 'bestAsk']:
                if isinstance(value, str) and len(value) > 100:
                    print(f"   • {key}: {value_type} (length: {len(value)})")
                    # Try to parse if it's JSON
                    try:
                        parsed = json.loads(value)
                        print(f"      → Parsed as: {type(parsed).__name__}")
                        if isinstance(parsed, list):
                            print(f"      → List length: {len(parsed)}")
                            if len(parsed) > 0:
                                print(f"      → First item: {str(parsed[0])[:100]}")
                    except:
                        pass
                else:
                    print(f"   • {key}: {value_type} = {value}")
            else:
                print(f"   • {key}: {value_type}")

        # Deep dive into events structure
        print("\n" + "=" * 80)
        print("EVENTS FIELD STRUCTURE")
        print("=" * 80)

        if 'events' in market:
            events = market['events']
            print(f"\n📊 Events type: {type(events).__name__}")

            if isinstance(events, list):
                print(f"📊 Events count: {len(events)}")

                if len(events) > 0:
                    event = events[0]
                    print(f"\n🔍 First event fields:")
                    for key in sorted(event.keys()):
                        value = event[key]
                        value_type = type(value).__name__

                        if key == 'markets':
                            print(f"   • {key}: {value_type}")
                            if isinstance(value, list):
                                print(f"      → Markets count: {len(value)}")
                                if len(value) > 0:
                                    print(f"\n      🔍 First nested market:")
                                    nested_market = value[0]
                                    for nkey in sorted(nested_market.keys()):
                                        nvalue = nested_market[nkey]
                                        nvalue_type = type(nvalue).__name__

                                        # Show important fields
                                        if nkey in ['clobTokenIds', 'tokenId', 'tokens', 'outcome', 'outcomePrices']:
                                            if isinstance(nvalue, str) and len(nvalue) > 50:
                                                print(f"         • {nkey}: {nvalue_type} (length: {len(nvalue)})")
                                                # Try parsing
                                                try:
                                                    parsed = json.loads(nvalue)
                                                    print(f"            → Parsed: {parsed}")
                                                except:
                                                    print(f"            → Value: {nvalue[:100]}...")
                                            else:
                                                print(f"         • {nkey}: {nvalue_type} = {nvalue}")
                                        else:
                                            print(f"         • {nkey}: {nvalue_type}")
                        else:
                            if isinstance(value, str) and len(value) > 100:
                                print(f"   • {key}: {value_type} (length: {len(value)})")
                            else:
                                print(f"   • {key}: {value_type} = {str(value)[:100]}")

        # Try to find token IDs
        print("\n" + "=" * 80)
        print("SEARCHING FOR TOKEN IDs")
        print("=" * 80)

        possible_paths = []

        # Check top level
        for field in ['clobTokenIds', 'tokens', 'tokenIds']:
            if field in market:
                value = market[field]
                possible_paths.append(f"market['{field}'] = {value}")

        # Check events.markets
        if 'events' in market and isinstance(market['events'], list) and len(market['events']) > 0:
            event = market['events'][0]
            if 'markets' in event and isinstance(event['markets'], list):
                for i, nested_market in enumerate(event['markets'][:2]):  # Check first 2
                    for field in ['clobTokenIds', 'tokenId', 'tokens']:
                        if field in nested_market:
                            value = nested_market[field]
                            possible_paths.append(f"events[0].markets[{i}]['{field}'] = {value}")

        if possible_paths:
            print("\n✅ Found token IDs at:")
            for path in possible_paths:
                print(f"   • {path}")
        else:
            print("\n❌ No token IDs found!")

        # Show full JSON for debugging
        print("\n" + "=" * 80)
        print("FULL JSON (first market)")
        print("=" * 80)
        print(json.dumps(market, indent=2))

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_crypto_markets()
