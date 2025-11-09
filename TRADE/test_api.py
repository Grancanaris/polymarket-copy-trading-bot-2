#!/usr/bin/env python3
"""
Diagnostic script to test Polymarket API accessibility
Run this from your Windows environment to check if the API is accessible
"""

import sys
import requests
try:
    import httpx
except ImportError:
    print("Installing httpx...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx

try:
    import cloudscraper
except ImportError:
    print("Installing cloudscraper...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cloudscraper"])
    import cloudscraper

def test_with_requests():
    """Test with requests library"""
    print("\n" + "="*60)
    print("Testing with requests library")
    print("="*60)
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {'limit': 2, 'closed': 'false'}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)
        print(f"✅ Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Retrieved {len(data)} markets")
            if len(data) > 0:
                print(f"✅ Sample market: {data[0].get('question', 'N/A')[:60]}...")
                return True
        else:
            print(f"❌ Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_with_httpx():
    """Test with httpx library (Polymarket's preferred method)"""
    print("\n" + "="*60)
    print("Testing with httpx library")
    print("="*60)
    try:
        url = "https://gamma-api.polymarket.com/markets"
        params = {'limit': 2}

        response = httpx.get(url, params=params, timeout=10)
        print(f"✅ Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Retrieved {len(data)} markets")
            if len(data) > 0:
                print(f"✅ Sample market: {data[0].get('question', 'N/A')[:60]}...")
                return True
        else:
            print(f"❌ Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_with_cloudscraper():
    """Test with cloudscraper (Cloudflare bypass)"""
    print("\n" + "="*60)
    print("Testing with cloudscraper (Cloudflare bypass)")
    print("="*60)
    try:
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )

        url = "https://gamma-api.polymarket.com/markets"
        params = {'limit': 2, 'closed': 'false'}

        response = scraper.get(url, params=params, timeout=10)
        print(f"✅ Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Retrieved {len(data)} markets")
            if len(data) > 0:
                print(f"✅ Sample market: {data[0].get('question', 'N/A')[:60]}...")
                return True
        else:
            print(f"❌ Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_clob_endpoint():
    """Test CLOB sampling-simplified-markets endpoint"""
    print("\n" + "="*60)
    print("Testing CLOB sampling-simplified-markets endpoint")
    print("="*60)
    try:
        url = "https://clob.polymarket.com/sampling-simplified-markets"

        response = requests.get(url, timeout=10)
        print(f"✅ Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Retrieved data: {len(data)} items")
            return True
        else:
            print(f"❌ Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("\n🔍 Polymarket API Diagnostic Tool")
    print("=" * 60)

    results = []
    results.append(("requests", test_with_requests()))
    results.append(("httpx", test_with_httpx()))
    results.append(("cloudscraper", test_with_cloudscraper()))
    results.append(("CLOB endpoint", test_clob_endpoint()))

    print("\n" + "="*60)
    print("📊 Summary")
    print("="*60)

    for method, success in results:
        status = "✅ WORKS" if success else "❌ FAILED"
        print(f"{method:20} : {status}")

    if any(success for _, success in results):
        print("\n✅ At least one method works! The bot can fetch markets.")
    else:
        print("\n❌ All methods failed. Polymarket API may be blocked in this environment.")
        print("   Possible reasons:")
        print("   1. Cloudflare protection blocking automated requests")
        print("   2. Geographic restrictions")
        print("   3. IP-based rate limiting")
        print("   4. VPN/proxy required")
