"""
Market data fetcher for Polymarket API
"""

import requests
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from models.market import Market
from config.config import ScalpingConfig

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


class MarketFetcher:
    """Fetches market data from Polymarket APIs"""

    def __init__(self):
        self.gamma_api_url = ScalpingConfig.POLYMARKET_API_URL
        self.clob_api_url = ScalpingConfig.HOST

        # Headers to avoid Cloudflare bot detection
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

        # Initialize cloudscraper if available
        if HAS_CLOUDSCRAPER:
            self.scraper = cloudscraper.create_scraper(
                browser={
                    'browser': 'chrome',
                    'platform': 'windows',
                    'mobile': False
                }
            )
        else:
            self.scraper = None

    def _make_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """
        Make HTTP request with fallback to different methods
        Tries: httpx -> cloudscraper -> requests

        Args:
            url: URL to fetch
            params: Query parameters

        Returns:
            Response JSON or None
        """
        methods = []

        # Try httpx first (Polymarket's official method)
        if HAS_HTTPX:
            methods.append(('httpx', lambda: httpx.get(url, params=params, timeout=10)))

        # Try cloudscraper (Cloudflare bypass)
        if self.scraper:
            methods.append(('cloudscraper', lambda: self.scraper.get(url, params=params, timeout=10)))

        # Try requests as fallback
        methods.append(('requests', lambda: requests.get(url, params=params, headers=self.headers, timeout=10)))

        for method_name, method_func in methods:
            try:
                response = method_func()
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"🔍 DEBUG: {method_name} returned status {response.status_code}")
            except Exception as e:
                print(f"🔍 DEBUG: {method_name} failed: {e}")
                continue

        print(f"❌ All HTTP methods failed for {url}")
        return None

    def fetch_active_markets(self, limit: int = 50) -> List[Market]:
        """
        Fetch active markets from Polymarket

        Args:
            limit: Maximum number of markets to fetch

        Returns:
            List of Market objects
        """
        try:
            # Fetch markets from Gamma API
            url = f"{self.gamma_api_url}/markets"
            params = {
                'closed': 'false',  # Only active markets
                'limit': limit,
                'offset': 0
            }

            print(f"🔍 DEBUG: Fetching markets from {url}")
            print(f"🔍 DEBUG: Params: {params}")

            markets_data = self._make_request(url, params)

            if not markets_data:
                print(f"❌ Failed to fetch markets data")
                return []

            if not isinstance(markets_data, list):
                print(f"❌ Unexpected response format: {type(markets_data)}")
                return []

            print(f"🔍 DEBUG: Received {len(markets_data)} markets from API")

            markets = []

            # Debug: Print first market structure
            if markets_data and len(markets_data) > 0:
                print(f"🔍 DEBUG: First market keys: {list(markets_data[0].keys())}")

                # Check for different possible token field names
                possible_token_fields = ['tokens', 'clobTokenIds', 'clob_token_ids', 'tokenIds', 'outcomes', 'outcomePrices', 'outcome_prices', 'markets', 'events']
                for field in possible_token_fields:
                    if field in markets_data[0]:
                        value = markets_data[0][field]
                        value_type = type(value).__name__
                        sample_value = str(value)[:200] if not isinstance(value, (dict, list)) or len(str(value)) < 200 else str(value)[:200]
                        print(f"🔍 DEBUG: Found field '{field}': type={value_type}, value={sample_value}")

                        # Try to parse if it's a stringified JSON
                        if isinstance(value, str):
                            try:
                                import json
                                parsed = json.loads(value)
                                print(f"🔍 DEBUG: '{field}' is stringified JSON! Parsed type={type(parsed).__name__}, length={len(parsed) if isinstance(parsed, (list, dict)) else 'N/A'}")
                                if isinstance(parsed, list) and len(parsed) > 0:
                                    print(f"🔍 DEBUG: First element sample: {str(parsed[0])[:100]}")
                            except:
                                pass
                        elif isinstance(value, list) and len(value) > 0:
                            print(f"🔍 DEBUG: First element in list: {str(value[0])[:100]}")
                        elif isinstance(value, dict):
                            print(f"🔍 DEBUG: Dict keys: {list(value.keys())[:10]}")

            for market_data in markets_data:
                # Try to parse market data
                # _parse_market will return None if it's not a valid binary market
                # Pass crypto keywords filter if configured
                keywords = ScalpingConfig.PREFERRED_MARKETS if ScalpingConfig.HOURLY_MARKETS_ONLY else None
                market = self._parse_market(market_data, keywords_filter=keywords)
                if market:
                    # Get orderbook data for this market to get accurate prices
                    self._enrich_with_orderbook(market)
                    markets.append(market)

            print(f"🔍 DEBUG: Parsed {len(markets)} binary markets")
            return markets

        except Exception as e:
            print(f"❌ Error fetching markets: {e}")
            import traceback
            traceback.print_exc()
            return []

    def fetch_markets_by_keywords(self, keywords: List[str], limit: int = 20) -> List[Market]:
        """
        Fetch markets matching keywords (e.g., 'bitcoin', 'ethereum')

        Uses two strategies:
        1. API query parameter (fast but may have false positives)
        2. Local filtering (slower but more accurate)

        Args:
            keywords: List of keywords to search for
            limit: Maximum number of markets per keyword

        Returns:
            List of Market objects
        """
        all_markets = []
        seen_condition_ids = set()

        # Strategy 1: Use API query parameter for each keyword
        for keyword in keywords:
            try:
                url = f"{self.gamma_api_url}/markets"
                params = {
                    'closed': 'false',
                    'limit': limit,
                    'offset': 0,
                    'query': keyword  # Search by keyword
                }

                print(f"🔍 DEBUG: Fetching markets for keyword '{keyword}' from {url}")

                markets_data = self._make_request(url, params)

                if not markets_data:
                    print(f"❌ Failed to fetch markets for '{keyword}'")
                    continue

                if not isinstance(markets_data, list):
                    print(f"❌ Unexpected response format for '{keyword}': {type(markets_data)}")
                    continue

                print(f"🔍 DEBUG: API returned {len(markets_data)} markets for '{keyword}'")

                # Count how many pass our filter
                filtered_count = 0
                for market_data in markets_data:
                    condition_id = market_data.get('conditionId')

                    # Skip duplicates
                    if condition_id in seen_condition_ids:
                        continue

                    # Try to parse market data with strict filtering
                    market = self._parse_market(market_data, keywords_filter=keywords)
                    if market:
                        self._enrich_with_orderbook(market)
                        all_markets.append(market)
                        seen_condition_ids.add(condition_id)
                        filtered_count += 1
                        print(f"   ✅ Matched: {market.question[:60]}")

                print(f"🔍 DEBUG: {filtered_count}/{len(markets_data)} markets passed filter for '{keyword}'")

            except Exception as e:
                print(f"❌ Error fetching markets for '{keyword}': {e}")
                import traceback
                traceback.print_exc()

        # Strategy 2: If we got very few results, try fetching all active markets and filtering locally
        if len(all_markets) < 5:
            print(f"\n🔍 DEBUG: Only found {len(all_markets)} markets via API query. Trying local filtering...")
            try:
                url = f"{self.gamma_api_url}/markets"
                params = {
                    'closed': 'false',
                    'limit': 100,  # Fetch more markets to filter locally
                    'offset': 0
                }

                markets_data = self._make_request(url, params)

                if markets_data and isinstance(markets_data, list):
                    print(f"🔍 DEBUG: Fetched {len(markets_data)} markets for local filtering")

                    for market_data in markets_data:
                        condition_id = market_data.get('conditionId')

                        # Skip duplicates
                        if condition_id in seen_condition_ids:
                            continue

                        # Try to parse market data with keyword filter
                        market = self._parse_market(market_data, keywords_filter=keywords)
                        if market:
                            self._enrich_with_orderbook(market)
                            all_markets.append(market)
                            seen_condition_ids.add(condition_id)
                            print(f"   ✅ Found via local filter: {market.question[:60]}")

            except Exception as e:
                print(f"❌ Error in local filtering: {e}")

        print(f"🔍 DEBUG: Total markets after all strategies: {len(all_markets)}")
        return all_markets

    def _parse_market(self, market_data: Dict[str, Any], keywords_filter: List[str] = None) -> Optional[Market]:
        """
        Parse raw market data into Market object

        Args:
            market_data: Raw market data from API
            keywords_filter: Optional list of keywords to filter markets (e.g., ['bitcoin', 'ethereum'])

        Returns:
            Market object or None if invalid
        """
        try:
            import json

            # Filter by keywords if provided
            # STRICTER FILTERING: Only match if keyword is in the question itself
            # This prevents false positives from metadata/tags
            if keywords_filter:
                question = market_data.get('question', '').lower()

                # Check if any keyword is in the question (primary filter)
                has_keyword_in_question = any(
                    keyword.lower() in question
                    for keyword in keywords_filter
                )

                # If not in question, check description and slug as fallback
                if not has_keyword_in_question:
                    description = market_data.get('description', '').lower()
                    slug = market_data.get('slug', '').lower()

                    has_keyword_elsewhere = any(
                        keyword.lower() in description or keyword.lower() in slug
                        for keyword in keywords_filter
                    )

                    if not has_keyword_elsewhere:
                        return None  # Skip markets that don't match keywords
                    else:
                        # Found in description/slug but not question
                        # Add additional validation: question should be related to crypto/markets
                        crypto_terms = ['price', 'value', 'market', 'trade', 'token', 'coin', 'crypto']
                        has_market_context = any(term in question for term in crypto_terms)
                        if not has_market_context:
                            # Likely a false positive (keyword in metadata but market is unrelated)
                            return None

            # First, try to get clobTokenIds (the actual token IDs for trading)
            # This field is often stringified JSON
            clob_token_ids = None
            for field_name in ['clobTokenIds', 'clob_token_ids', 'tokenIds', 'token_ids']:
                if field_name in market_data:
                    value = market_data.get(field_name)
                    if isinstance(value, str):
                        try:
                            clob_token_ids = json.loads(value)
                            break
                        except:
                            pass
                    elif isinstance(value, list) and len(value) == 2:
                        clob_token_ids = value
                        break

            # Get outcome prices (also often stringified JSON)
            prices = []
            for field_name in ['outcomePrices', 'outcome_prices', 'prices']:
                if field_name in market_data:
                    value = market_data.get(field_name)
                    if isinstance(value, str):
                        try:
                            prices = json.loads(value)
                            if isinstance(prices, list) and len(prices) == 2:
                                break
                        except:
                            pass
                    elif isinstance(value, list) and len(value) == 2:
                        prices = value
                        break

            # Get outcomes (outcome names like ["Yes", "No"])
            outcomes = None
            for field_name in ['outcomes', 'outcome_names']:
                if field_name in market_data:
                    value = market_data.get(field_name)
                    if isinstance(value, str):
                        try:
                            outcomes = json.loads(value)
                            if isinstance(outcomes, list) and len(outcomes) == 2:
                                break
                        except:
                            pass
                    elif isinstance(value, list) and len(value) == 2:
                        outcomes = value
                        break

            # Check if we have token IDs from the markets field (nested structure)
            if not clob_token_ids and 'markets' in market_data:
                markets_field = market_data.get('markets', [])
                if isinstance(markets_field, list) and len(markets_field) > 0:
                    # Extract token IDs from nested markets
                    clob_token_ids = []
                    for mkt in markets_field[:2]:  # Take first 2
                        if isinstance(mkt, dict):
                            token_id = mkt.get('clobTokenIds') or mkt.get('tokenId') or mkt.get('token_id')
                            if token_id:
                                clob_token_ids.append(token_id)

            # Check events field for nested market data
            if not clob_token_ids and 'events' in market_data:
                events = market_data.get('events', [])
                if isinstance(events, list) and len(events) > 0:
                    event = events[0]
                    if isinstance(event, dict) and 'markets' in event:
                        event_markets = event.get('markets', [])
                        if isinstance(event_markets, list) and len(event_markets) > 0:
                            clob_token_ids = []
                            for mkt in event_markets[:2]:
                                if isinstance(mkt, dict):
                                    token_id = mkt.get('clobTokenIds') or mkt.get('tokenId')
                                    if isinstance(token_id, str):
                                        try:
                                            token_id = json.loads(token_id)
                                        except:
                                            pass
                                    if token_id:
                                        if isinstance(token_id, list):
                                            clob_token_ids.extend(token_id)
                                        else:
                                            clob_token_ids.append(token_id)

            # Debug: Print token structure for first market
            if not hasattr(self, '_debug_printed'):
                print(f"🔍 DEBUG: Outcomes: {outcomes}")
                print(f"🔍 DEBUG: Clob Token IDs: {clob_token_ids}")
                print(f"🔍 DEBUG: Prices: {prices}")
                self._debug_printed = True

            # Validate we have token IDs
            if not clob_token_ids or len(clob_token_ids) != 2:
                # Try to get tokens from top level in various formats
                tokens = market_data.get('tokens', [])

                # Case 1: List of token objects with 'token_id' field
                if isinstance(tokens, list) and len(tokens) == 2:
                    if isinstance(tokens[0], dict):
                        # Extract token_id from each object
                        token_ids = []
                        for token in tokens:
                            token_id = token.get('token_id') or token.get('tokenId') or token.get('id')
                            if token_id:
                                token_ids.append(token_id)
                        if len(token_ids) == 2:
                            clob_token_ids = token_ids
                    # Case 2: List of token ID strings
                    elif isinstance(tokens[0], str) and len(tokens[0]) > 20:
                        clob_token_ids = tokens

                # Try stringified tokens field
                if not clob_token_ids or len(clob_token_ids) != 2:
                    tokens_str = market_data.get('tokens')
                    if isinstance(tokens_str, str):
                        try:
                            tokens_parsed = json.loads(tokens_str)
                            if isinstance(tokens_parsed, list) and len(tokens_parsed) == 2:
                                clob_token_ids = tokens_parsed
                        except:
                            pass

                # If still no tokens, this is not a valid binary market
                if not clob_token_ids or len(clob_token_ids) != 2:
                    if not hasattr(self, '_debug_no_tokens_printed'):
                        print(f"❌ No valid token IDs found for market: {market_data.get('question', 'Unknown')[:50]}")
                        print(f"   Available fields: {list(market_data.keys())[:20]}")
                        self._debug_no_tokens_printed = True
                    return None

            # Parse end date
            end_date_str = market_data.get('endDate', market_data.get('end_date_iso', market_data.get('endDateIso')))
            if not end_date_str:
                return None

            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except:
                return None

            # Get actual token IDs
            actual_token_id_0 = clob_token_ids[0]
            actual_token_id_1 = clob_token_ids[1]

            # Get prices
            if prices and len(prices) == 2:
                price_0 = float(prices[0])
                price_1 = float(prices[1])
            else:
                # Try to get from top-level market data
                last_price = market_data.get('lastTradePrice')
                if last_price:
                    price_0 = float(last_price)
                    price_1 = 1.0 - price_0
                else:
                    # If no prices available, will fetch from orderbook later
                    price_0 = 0.5
                    price_1 = 0.5

            # Determine which is "Yes" (Up) and which is "No" (Down)
            # Use outcomes array if available
            if outcomes and len(outcomes) == 2:
                outcome_0 = str(outcomes[0]).lower() if outcomes[0] else 'yes'
                outcome_1 = str(outcomes[1]).lower() if outcomes[1] else 'no'
            else:
                # Default: assume position 0 is Yes
                outcome_0 = 'yes'
                outcome_1 = 'no'

            # Map to Up/Down based on outcome
            if 'yes' in outcome_0 or 'up' in outcome_0 or 'higher' in outcome_0:
                token_id_up = actual_token_id_0
                price_up = price_0
                token_id_down = actual_token_id_1
                price_down = price_1
            else:
                token_id_up = actual_token_id_1
                price_up = price_1
                token_id_down = actual_token_id_0
                price_down = price_0

            # Validate token IDs exist
            if not token_id_up or not token_id_down:
                print(f"❌ Missing token IDs for market: {market_data.get('question', 'Unknown')[:50]}")
                return None

            market = Market(
                condition_id=market_data.get('conditionId'),
                question=market_data.get('question', 'Unknown'),
                end_date=end_date,
                token_id_up=token_id_up,
                token_id_down=token_id_down,
                price_up=price_up,
                price_down=price_down,
                slug=market_data.get('slug'),
                volume_24h=float(market_data.get('volume24hr', 0)),
                liquidity=float(market_data.get('liquidity', 0))
            )

            return market

        except Exception as e:
            print(f"❌ Error parsing market: {e}")
            return None

    def _enrich_with_orderbook(self, market: Market) -> None:
        """
        Fetch orderbook data and add to market
        Also updates market prices if they weren't available from Gamma API

        Args:
            market: Market object to enrich with orderbook data
        """
        try:
            # Fetch orderbook from CLOB API
            url = f"{self.clob_api_url}/book"

            # Get orderbook for Up token
            params_up = {'token_id': market.token_id_up}
            response_up = requests.get(url, params=params_up, timeout=5, headers=self.headers)

            if response_up.status_code == 200:
                book_up = response_up.json()
                bids = book_up.get('bids', [])
                asks = book_up.get('asks', [])

                if bids:
                    market.best_bid_up = float(bids[0].get('price', 0))
                if asks:
                    market.best_ask_up = float(asks[0].get('price', 0))

                # If price_up is default (0.5), use midpoint from orderbook
                if market.price_up == 0.5 and market.best_bid_up and market.best_ask_up:
                    market.price_up = (market.best_bid_up + market.best_ask_up) / 2.0
                elif market.price_up == 0.5 and market.best_bid_up:
                    market.price_up = market.best_bid_up
                elif market.price_up == 0.5 and market.best_ask_up:
                    market.price_up = market.best_ask_up

            # Get orderbook for Down token
            params_down = {'token_id': market.token_id_down}
            response_down = requests.get(url, params=params_down, timeout=5, headers=self.headers)

            if response_down.status_code == 200:
                book_down = response_down.json()
                bids = book_down.get('bids', [])
                asks = book_down.get('asks', [])

                if bids:
                    market.best_bid_down = float(bids[0].get('price', 0))
                if asks:
                    market.best_ask_down = float(asks[0].get('price', 0))

                # If price_down is default (0.5), use midpoint from orderbook
                if market.price_down == 0.5 and market.best_bid_down and market.best_ask_down:
                    market.price_down = (market.best_bid_down + market.best_ask_down) / 2.0
                elif market.price_down == 0.5 and market.best_bid_down:
                    market.price_down = market.best_bid_down
                elif market.price_down == 0.5 and market.best_ask_down:
                    market.price_down = market.best_ask_down

        except Exception as e:
            # Non-critical error, orderbook data is optional
            pass

    def get_market_by_condition_id(self, condition_id: str) -> Optional[Market]:
        """
        Fetch a specific market by condition ID

        Args:
            condition_id: Market condition ID

        Returns:
            Market object or None
        """
        try:
            url = f"{self.gamma_api_url}/markets/{condition_id}"
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            market_data = response.json()
            # Don't apply keyword filter when fetching specific market by ID
            market = self._parse_market(market_data, keywords_filter=None)

            if market:
                self._enrich_with_orderbook(market)

            return market

        except Exception as e:
            print(f"❌ Error fetching market {condition_id}: {e}")
            return None
