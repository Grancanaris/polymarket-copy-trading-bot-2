#!/usr/bin/env python3
"""
Capture actual Polymarket API responses to a file for analysis
RUN THIS ON YOUR WINDOWS MACHINE where the API is accessible
"""

import requests
import json

def capture_responses():
    """Fetch and save API responses"""

    results = {}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    # 1. Fetch general markets
    print("🔍 Fetching general markets...")
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {'closed': 'false', 'limit': 3}
        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            results['general_markets'] = data
            print(f"   ✅ Got {len(data)} general markets")
        else:
            print(f"   ❌ Status: {response.status_code}")
            results['general_markets_error'] = response.text
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results['general_markets_error'] = str(e)

    # 2. Fetch bitcoin markets
    print("🔍 Fetching bitcoin markets...")
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {'closed': 'false', 'limit': 3, 'query': 'bitcoin'}
        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            results['bitcoin_markets'] = data
            print(f"   ✅ Got {len(data)} bitcoin markets")
            if len(data) > 0:
                print(f"   First market: {data[0].get('question', 'Unknown')[:60]}")
        else:
            print(f"   ❌ Status: {response.status_code}")
            results['bitcoin_markets_error'] = response.text
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results['bitcoin_markets_error'] = str(e)

    # 3. Fetch ethereum markets
    print("🔍 Fetching ethereum markets...")
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {'closed': 'false', 'limit': 3, 'query': 'ethereum'}
        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            results['ethereum_markets'] = data
            print(f"   ✅ Got {len(data)} ethereum markets")
            if len(data) > 0:
                print(f"   First market: {data[0].get('question', 'Unknown')[:60]}")
        else:
            print(f"   ❌ Status: {response.status_code}")
            results['ethereum_markets_error'] = response.text
    except Exception as e:
        print(f"   ❌ Error: {e}")
        results['ethereum_markets_error'] = str(e)

    # Save to file
    output_file = "api_responses.json"
    print(f"\n💾 Saving to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"✅ Done! Saved API responses to {output_file}")
    print(f"\n📋 Summary:")
    for key, value in results.items():
        if isinstance(value, list):
            print(f"   {key}: {len(value)} items")
        elif 'error' in key:
            print(f"   {key}: {value[:100]}")

    # Also print a sample market structure
    print(f"\n🔍 Sample market structure:")
    print("=" * 80)

    for market_type in ['bitcoin_markets', 'ethereum_markets', 'general_markets']:
        if market_type in results and isinstance(results[market_type], list) and len(results[market_type]) > 0:
            market = results[market_type][0]

            print(f"\n{market_type.upper()} - First market keys:")
            print(f"Question: {market.get('question', 'Unknown')[:60]}")

            # Check for token-related fields
            print(f"\nChecking for token-related fields:")

            # Check direct fields
            for field in ['clobTokenIds', 'tokens', 'tokenIds', 'outcomes', 'outcomePrices']:
                if field in market:
                    value = market[field]
                    if isinstance(value, str):
                        # Try to parse JSON string
                        try:
                            parsed = json.loads(value)
                            print(f"   ✅ {field}: (stringified) {parsed}")
                        except:
                            print(f"   ✅ {field}: {value[:100]}")
                    else:
                        print(f"   ✅ {field}: {value}")

            # Check events structure
            if 'events' in market:
                events = market['events']
                print(f"\n   ✅ events: list with {len(events)} items")

                if len(events) > 0:
                    event = events[0]
                    print(f"      Event fields: {list(event.keys())}")

                    if 'markets' in event:
                        event_markets = event['markets']
                        print(f"      events[0].markets: list with {len(event_markets)} items")

                        if len(event_markets) > 0:
                            nested_market = event_markets[0]
                            print(f"         Nested market fields: {list(nested_market.keys())}")

                            # Check for token fields in nested market
                            for field in ['clobTokenIds', 'tokenId', 'tokens', 'outcome']:
                                if field in nested_market:
                                    value = nested_market[field]
                                    print(f"         ✅ {field}: {value}")

            break  # Only show first available market type

if __name__ == "__main__":
    print("📡 Polymarket API Response Capture Tool")
    print("=" * 80)
    print("This will fetch sample markets and save the raw API responses")
    print("=" * 80)
    print()

    capture_responses()

    print("\n" + "=" * 80)
    print("✅ COMPLETE!")
    print("=" * 80)
    print("\nPlease share the 'api_responses.json' file or paste its contents")
    print("so I can fix the parser to work with the actual API structure.")
