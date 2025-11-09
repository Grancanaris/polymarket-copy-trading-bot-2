"""
Test script to explore Polymarket API endpoints for crypto markets
"""
import requests
import json

# Try importing alternative HTTP libraries
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    print("Warning: httpx not available")

try:
    import cloudscraper
    HAS_CLOUDSCRAPER = True
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'mobile': False
        }
    )
except ImportError:
    HAS_CLOUDSCRAPER = False
    scraper = None
    print("Warning: cloudscraper not available")

def test_api_endpoint(url, params=None, description=""):
    """Test an API endpoint and print results"""
    print(f"\n{'='*80}")
    print(f"Testing: {description}")
    print(f"URL: {url}")
    print(f"Params: {params}")
    print(f"{'='*80}")

    data = None
    status_code = None

    # Try httpx first
    if HAS_HTTPX:
        try:
            response = httpx.get(url, params=params, timeout=10)
            status_code = response.status_code
            print(f"Status (httpx): {status_code}")
            if status_code == 200:
                data = response.json()
        except Exception as e:
            print(f"httpx failed: {e}")

    # Try cloudscraper if httpx failed
    if data is None and scraper:
        try:
            response = scraper.get(url, params=params, timeout=10)
            status_code = response.status_code
            print(f"Status (cloudscraper): {status_code}")
            if status_code == 200:
                data = response.json()
        except Exception as e:
            print(f"cloudscraper failed: {e}")

    # Try regular requests as last resort
    if data is None:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
            }
            response = requests.get(url, params=params, headers=headers, timeout=10)
            status_code = response.status_code
            print(f"Status (requests): {status_code}")
            if status_code == 200:
                data = response.json()
            else:
                print(f"Error: {response.text[:200]}")
        except Exception as e:
            print(f"requests failed: {e}")

    # Process successful response
    if data is not None:
        try:
            if isinstance(data, list):
                print(f"✅ Returned: {len(data)} items")
                if data:
                    print(f"\nFirst item keys: {list(data[0].keys())}")
                    print(f"First item question: {data[0].get('question', 'N/A')}")

                    # Check for tags/categories
                    print(f"\nChecking for tags/categories in first item:")
                    for key in ['tags', 'tag', 'category', 'categories', 'groupItemTitle', 'groupItemThreshold']:
                        if key in data[0]:
                            print(f"  {key}: {data[0][key]}")

                    # Print first 5 market questions
                    print(f"\nFirst 5 markets:")
                    for i, market in enumerate(data[:5]):
                        print(f"  {i+1}. {market.get('question', 'N/A')[:80]}")

            elif isinstance(data, dict):
                print(f"✅ Returned dict with keys: {list(data.keys())}")
                # If it's a dict that contains a list of markets
                if 'data' in data:
                    print(f"   'data' field contains: {len(data['data'])} items")
                elif 'markets' in data:
                    print(f"   'markets' field contains: {len(data['markets'])} items")

        except Exception as e:
            print(f"Exception processing data: {e}")
    else:
        print("❌ Failed to get data from all methods")

# Base URLs
GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

print("="*80)
print("EXPLORING POLYMARKET API FOR CRYPTO MARKETS")
print("="*80)

# Test 1: Basic Gamma API markets endpoint
test_api_endpoint(
    f"{GAMMA_API}/markets",
    params={'closed': 'false', 'limit': 10},
    description="Gamma API - Basic markets (no filter)"
)

# Test 2: Try with tag parameter
test_api_endpoint(
    f"{GAMMA_API}/markets",
    params={'closed': 'false', 'limit': 10, 'tag': 'crypto'},
    description="Gamma API - With tag=crypto"
)

# Test 3: Try with category parameter
test_api_endpoint(
    f"{GAMMA_API}/markets",
    params={'closed': 'false', 'limit': 10, 'category': 'crypto'},
    description="Gamma API - With category=crypto"
)

# Test 4: Try query parameter with bitcoin
test_api_endpoint(
    f"{GAMMA_API}/markets",
    params={'closed': 'false', 'limit': 10, 'query': 'bitcoin'},
    description="Gamma API - With query=bitcoin"
)

# Test 5: Try CLOB API
test_api_endpoint(
    f"{CLOB_API}/markets",
    params={},
    description="CLOB API - Basic markets"
)

# Test 6: Try sorting by volume
test_api_endpoint(
    f"{GAMMA_API}/markets",
    params={'closed': 'false', 'limit': 10, 'order': 'volume24hr', 'ascending': 'false'},
    description="Gamma API - Sorted by volume24hr (descending)"
)

# Test 7: Try the /events endpoint which might have category grouping
test_api_endpoint(
    f"{GAMMA_API}/events",
    params={'closed': 'false', 'limit': 5, 'tag': 'crypto'},
    description="Gamma API - Events endpoint with tag=crypto"
)

print("\n" + "="*80)
print("TESTING COMPLETE")
print("="*80)
