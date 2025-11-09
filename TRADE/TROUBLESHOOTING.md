# Scalping Bot Troubleshooting Guide

## Issue: "No markets found!"

### Root Cause Analysis

The bot was unable to find markets due to **two main issues**:

#### 1. Cloudflare Protection (403 Access Denied)
The Polymarket Gamma API (`https://gamma-api.polymarket.com`) is protected by Cloudflare, which blocks automated requests that don't look like real browsers. This affects:
- Simple `curl` commands
- Basic Python `requests` library calls
- Automated scripts without proper headers

#### 2. Overly Restrictive Filters
The default configuration had **very narrow filters**:
- `HOURLY_MARKETS_ONLY=true` - Only scanned markets expiring within 1.5 hours
- `PREFERRED_MARKETS=bitcoin,ethereum` - Only 2 keywords
- This combination often resulted in **zero markets** being found

### Solutions Implemented

#### ✅ 1. Multi-Method HTTP Requests
Updated `TRADE/utils/market_fetcher.py` to try multiple HTTP libraries:
1. **httpx** (Polymarket's official method) - tries first
2. **cloudscraper** (Cloudflare bypass) - tries second
3. **requests** (fallback) - tries last

This significantly improves the chance of bypassing Cloudflare protection.

#### ✅ 2. Updated Default Configuration
Modified `TRADE/.env.example`:
```bash
# OLD (too restrictive)
HOURLY_MARKETS_ONLY=true
PREFERRED_MARKETS=bitcoin,ethereum

# NEW (more flexible)
HOURLY_MARKETS_ONLY=false
PREFERRED_MARKETS=bitcoin,ethereum,btc,eth,crypto,trump,election
MAX_DAYS_TO_EXPIRY=7
```

#### ✅ 3. Enhanced Debug Logging
Added detailed debug output to show:
- Which HTTP method succeeded
- How many markets were fetched
- How many passed filters
- Why markets were filtered out

#### ✅ 4. Diagnostic Script
Created `TRADE/test_api.py` to test API accessibility from your environment.

---

## How to Fix Your Bot

### Step 1: Install Required Libraries
```bash
cd C:\Users\catal\Desktop\1\copytrade\TRADE
pip install httpx cloudscraper
```

### Step 2: Update Your .env File
Copy from `.env.example` or update your existing `.env`:
```bash
# Change this line
HOURLY_MARKETS_ONLY=false

# And expand your keywords
PREFERRED_MARKETS=bitcoin,ethereum,btc,eth,crypto,trump,election,president
```

### Step 3: Test API Accessibility
Run the diagnostic script:
```bash
python test_api.py
```

This will test all HTTP methods and show which ones work in your environment.

### Step 4: Run the Bot
```bash
python scalping_bot.py
```

You should now see debug output like:
```
🔍 DEBUG: HOURLY_MARKETS_ONLY=False, fetching keywords: ['bitcoin', 'ethereum', ...]
🔍 DEBUG: Fetching markets for keyword 'bitcoin' from https://gamma-api.polymarket.com/markets
🔍 DEBUG: httpx returned status 200  ✅
🔍 DEBUG: Received 20 markets for 'bitcoin'
🔍 DEBUG: Total markets fetched: 45
🔍 Found 45 markets to scan
```

---

## Understanding the Filters

### `HOURLY_MARKETS_ONLY`
- **true**: Only scans markets expiring within 1.5 hours
  - ✅ Lower risk (less time for price to change)
  - ❌ **Very few markets** (often zero)
  - ❌ May miss all opportunities

- **false**: Scans all markets matching keywords (recommended)
  - ✅ **Many more opportunities**
  - ✅ Still filtered by `MAX_DAYS_TO_EXPIRY`
  - ⚠️ Slightly higher risk (longer until expiry)

### `PREFERRED_MARKETS`
Comma-separated keywords to search for. Examples:
- `bitcoin,ethereum` - Only BTC and ETH markets
- `bitcoin,btc,crypto,election` - Crypto and political markets
- `trump,biden,president,election` - Political markets only

### `MAX_DAYS_TO_EXPIRY`
Only trade markets expiring within X days:
- `1` - Only markets expiring today/tomorrow
- `7` - Markets expiring within a week (recommended)
- `30` - Markets expiring within a month

---

## Environment-Specific Issues

### If API Still Returns 403
The Cloudflare protection might be **stricter in some environments**:

1. **Geographic Restrictions**: Polymarket may block certain countries
2. **VPN/Proxy**: Try using a VPN if you're in a restricted region
3. **IP-based Blocking**: Your IP might be rate-limited

**Solution**: Run the bot from a different environment:
- Different network (mobile hotspot, different WiFi)
- VPN to a different country (US recommended)
- Cloud server (AWS, Google Cloud, DigitalOcean)

### If Running from a Server
Add these environment variables:
```bash
export POLYMARKET_API_URL=https://gamma-api.polymarket.com
export HOST=https://clob.polymarket.com
```

---

## Performance Tuning

### Conservative Settings (Low Risk)
```bash
HOURLY_MARKETS_ONLY=true  # If hourly markets are available
MAX_DAYS_TO_EXPIRY=1
PREFERRED_MARKETS=bitcoin,ethereum
MAX_POSITION_SIZE=10.0
MAX_CONCURRENT_POSITIONS=3
```

### Balanced Settings (Recommended)
```bash
HOURLY_MARKETS_ONLY=false
MAX_DAYS_TO_EXPIRY=7
PREFERRED_MARKETS=bitcoin,ethereum,btc,eth,crypto
MAX_POSITION_SIZE=50.0
MAX_CONCURRENT_POSITIONS=10
```

### Aggressive Settings (Higher Risk, More Opportunities)
```bash
HOURLY_MARKETS_ONLY=false
MAX_DAYS_TO_EXPIRY=30
PREFERRED_MARKETS=bitcoin,ethereum,crypto,trump,election,sports,president
MAX_POSITION_SIZE=100.0
MAX_CONCURRENT_POSITIONS=20
```

---

## Verification Checklist

Before running the bot, verify:
- [ ] `httpx` and `cloudscraper` are installed
- [ ] `.env` file exists and has valid `PROXY_WALLET` and `PK`
- [ ] `HOURLY_MARKETS_ONLY=false` (unless you specifically want hourly markets)
- [ ] `PREFERRED_MARKETS` has multiple keywords
- [ ] `test_api.py` successfully fetches markets
- [ ] You have USDC in your wallet

---

## Still Not Working?

If you still see "No markets found" after following these steps:

1. **Check the debug output** - it will show exactly why markets aren't being found
2. **Run `test_api.py`** - this will tell you if the API is accessible
3. **Try a VPN** - Cloudflare might be blocking your region
4. **Check your keywords** - some keywords might not have active markets
5. **Disable hourly filter** - set `HOURLY_MARKETS_ONLY=false`

---

## Example Output (Working)

When the bot is working correctly, you should see:
```
🤖 Initializing Polymarket Scalping Bot...
👤 Wallet: 0xa34C36df85424AbBCB81fe38CfFA91fdD27a46cB
⏱️  Scan interval: 0.1s
🔑 Setting up CLOB client...
📊 Initializing strategies...
   ✅ Binary Arbitrage (min profit: 0.04¢)
   ✅ Momentum Scalping (profit target: 0.02¢)
   ✅ Mean Reversion (entry: 70%/30%)
✅ Bot initialized successfully!

🚀 Scalping Bot is now running!
💫 Press Ctrl+C to stop

🔍 DEBUG: HOURLY_MARKETS_ONLY=False, fetching keywords: ['bitcoin', 'ethereum', ...]
🔍 DEBUG: Fetching markets for keyword 'bitcoin'
🔍 DEBUG: httpx returned status 200
🔍 DEBUG: Received 20 markets for 'bitcoin'
🔍 DEBUG: Total markets fetched: 45
🔍 Found 45 markets to scan
   Sample: Will Bitcoin close above $100,000 on November 15?
   Prices: Up=$0.653 Down=$0.342 Sum=$0.995
   Arb opportunity: True (profit: $0.0050)
   ...
```

---

## Contact / Issues

If you continue to have issues, please provide:
1. Output from `test_api.py`
2. First 50 lines of bot output (with debug enabled)
3. Your `.env` configuration (without sensitive keys)
