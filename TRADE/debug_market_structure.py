#!/usr/bin/env python3
"""
Debug script to examine the actual structure of Polymarket API responses
"""

import requests
import json

def examine_market_structure():
    """Fetch a sample market and print its structure"""
    print("🔍 Examining Polymarket API Response Structure\n")

    url = "https://gamma-api.polymarket.com/markets"
    params = {'limit': 1, 'closed': 'false'}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()

            if data and len(data) > 0:
                print("✅ Successfully fetched market data\n")
                print("=" * 60)
                print("FIRST MARKET STRUCTURE:")
                print("=" * 60)

                market = data[0]

                # Print all top-level keys
                print("\nTop-level keys:")
                for key in market.keys():
                    print(f"  - {key}")

                # Print full JSON with indentation
                print("\n" + "=" * 60)
                print("FULL MARKET DATA:")
                print("=" * 60)
                print(json.dumps(market, indent=2))

                # Check for tokens field
                print("\n" + "=" * 60)
                print("TOKEN ANALYSIS:")
                print("=" * 60)

                if 'tokens' in market:
                    tokens = market['tokens']
                    print(f"✅ 'tokens' field EXISTS")
                    print(f"   Type: {type(tokens)}")
                    print(f"   Length: {len(tokens) if isinstance(tokens, list) else 'N/A'}")
                    if isinstance(tokens, list) and len(tokens) > 0:
                        print(f"\n   First token structure:")
                        print(json.dumps(tokens[0], indent=4))
                else:
                    print("❌ 'tokens' field DOES NOT EXIST")
                    print("\n   Looking for alternative fields...")

                    # Check for alternative field names
                    alternative_keys = ['outcomes', 'markets', 'clobTokenIds', 'tokenIds']
                    for alt_key in alternative_keys:
                        if alt_key in market:
                            print(f"   ✅ Found '{alt_key}' instead!")
                            print(f"      Type: {type(market[alt_key])}")
                            if isinstance(market[alt_key], list):
                                print(f"      Length: {len(market[alt_key])}")
            else:
                print("❌ No markets returned")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(response.text[:500])

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    examine_market_structure()
