#!/usr/bin/env python3
"""
Detailed market data inspector to understand why searches return unexpected results
"""

import json
import requests
from typing import Dict, Any

def inspect_market_deeply(market: Dict[str, Any], keyword: str) -> None:
    """
    Deep inspection of a market to find where a keyword appears

    Args:
        market: Market data dictionary
        keyword: Keyword to search for
    """
    print(f"\n{'='*80}")
    print(f"INSPECTING MARKET: {market.get('question', 'Unknown')}")
    print(f"Searching for keyword: '{keyword}'")
    print(f"{'='*80}\n")

    def search_dict(obj: Any, path: str = "", depth: int = 0) -> None:
        """Recursively search for keyword in dictionary"""
        indent = "  " * depth

        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key

                # Check if keyword is in the key itself
                if keyword.lower() in str(key).lower():
                    print(f"{indent}🔍 FOUND in KEY: {current_path}")
                    print(f"{indent}   Value type: {type(value).__name__}")
                    print(f"{indent}   Value: {str(value)[:200]}\n")

                # Check if keyword is in the value
                if isinstance(value, str) and keyword.lower() in value.lower():
                    print(f"{indent}🔍 FOUND in VALUE: {current_path}")
                    print(f"{indent}   Value: {value[:200]}\n")

                # Recurse into nested structures
                if depth < 5:  # Limit depth to avoid infinite recursion
                    search_dict(value, current_path, depth + 1)

        elif isinstance(obj, list):
            for i, item in enumerate(obj[:10]):  # Limit to first 10 items
                current_path = f"{path}[{i}]"
                search_dict(item, current_path, depth + 1)

        elif isinstance(obj, str) and keyword.lower() in obj.lower():
            print(f"{indent}🔍 FOUND in STRING: {path}")
            print(f"{indent}   Value: {obj[:200]}\n")

    search_dict(market)

    print(f"\n{'='*80}\n")


def main():
    print("🔍 Market Data Deep Inspector")
    print("="*80)

    # Fetch markets for bitcoin
    print("\n📡 Fetching bitcoin markets...")
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        'closed': 'false',
        'limit': 3,
        'offset': 0,
        'query': 'bitcoin'
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        markets = response.json()

        if isinstance(markets, list) and len(markets) > 0:
            print(f"✅ Got {len(markets)} markets\n")

            # Inspect first market
            first_market = markets[0]
            print(f"First market question: {first_market.get('question', 'Unknown')}")

            # Deep inspection
            inspect_market_deeply(first_market, "bitcoin")

            # Also show full structure of top-level fields
            print("\n📋 TOP-LEVEL FIELDS:")
            print("="*80)
            for key, value in first_market.items():
                value_type = type(value).__name__
                value_preview = str(value)[:100] if not isinstance(value, (dict, list)) else f"{value_type} with {len(value)} items"
                print(f"  {key}: {value_type} = {value_preview}")

            # Save full response
            print("\n💾 Saving full response to bitcoin_market_full.json...")
            with open('bitcoin_market_full.json', 'w') as f:
                json.dump(first_market, f, indent=2)
            print("✅ Saved!")

        else:
            print("❌ No markets found or unexpected response format")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
