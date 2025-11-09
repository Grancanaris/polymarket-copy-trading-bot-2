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
        Fetch active markets from Polymarket CLOB API (includes token IDs)

        Args:
            limit: Maximum number of markets to fetch

        Returns:
            List of Market objects
        """
        try:
            # First try CLOB API which has token IDs directly
            url = f"{self.clob_api_url}/markets"

            print(f"🔍 DEBUG: Fetching markets from CLOB API: {url}")

            markets_data = self._make_request(url, params=None)

            if not markets_data:
                print(f"❌ Failed to fetch markets from CLOB API, trying Gamma API...")
                return self._fetch_from_gamma_api(limit)

            # Handle both list and dict responses from CLOB API
            if isinstance(markets_data, dict):
                print(f"🔍 DEBUG: CLOB API returned dict, extracting markets list...")
                print(f"🔍 DEBUG: Dict keys: {list(markets_data.keys())}")

                # Try different possible field names for markets list
                if 'data' in markets_data:
                    markets_data = markets_data['data']
                elif 'markets' in markets_data:
                    markets_data = markets_data['markets']
                elif 'results' in markets_data:
                    markets_data = markets_data['results']
                else:
                    print(f"❌ Could not find markets list in CLOB API response")
                    return self._fetch_from_gamma_api(limit)

            if not isinstance(markets_data, list):
                print(f"❌ Unexpected response format from CLOB API: {type(markets_data)}")
                return self._fetch_from_gamma_api(limit)

            print(f"🔍 DEBUG: Received {len(markets_data)} markets from CLOB API")

            markets = []

            # Debug: Print first market structure
            if markets_data and len(markets_data) > 0:
                print(f"🔍 DEBUG: First market keys: {list(markets_data[0].keys())[:30]}")

                # Check if tokens field exists
                if 'tokens' in markets_data[0]:
                    tokens_value = markets_data[0]['tokens']
                    print(f"🔍 DEBUG: 'tokens' field type: {type(tokens_value).__name__}")
                    if isinstance(tokens_value, list) and len(tokens_value) > 0:
                        print(f"🔍 DEBUG: First token: {tokens_value[0]}")

            for market_data in markets_data:
                # Always filter by crypto keywords to avoid fetching sports/politics markets
                keywords = ScalpingConfig.PREFERRED_MARKETS
                market = self._parse_clob_market(market_data, keywords_filter=keywords)
                if market:
                    # Get orderbook data for this market to get accurate prices
                    self._enrich_with_orderbook(market)
                    markets.append(market)

            print(f"🔍 DEBUG: Parsed {len(markets)} binary markets from CLOB API")
            return markets

        except Exception as e:
            print(f"❌ Error fetching markets from CLOB API: {e}")
            import traceback
            traceback.print_exc()
            print(f"🔍 Falling back to Gamma API...")
            return self._fetch_from_gamma_api(limit)

    def _fetch_from_gamma_api(self, limit: int = 50) -> List[Market]:
        """
        Fallback: Fetch markets from Gamma API

        Args:
            limit: Maximum number of markets to fetch

        Returns:
            List of Market objects
        """
        try:
            url = f"{self.gamma_api_url}/markets"
            params = {
                'closed': 'false',
                'limit': limit,
                'offset': 0
            }

            print(f"🔍 DEBUG: Fetching markets from Gamma API: {url}")

            markets_data = self._make_request(url, params)

            if not markets_data or not isinstance(markets_data, list):
                return []

            print(f"🔍 DEBUG: Received {len(markets_data)} markets from Gamma API")

            markets = []
            for market_data in markets_data:
                # Always filter by crypto keywords to avoid fetching sports/politics markets
                keywords = ScalpingConfig.PREFERRED_MARKETS
                market = self._parse_market(market_data, keywords_filter=keywords)
                if market:
                    self._enrich_with_orderbook(market)
                    markets.append(market)

            print(f"🔍 DEBUG: Parsed {len(markets)} binary markets from Gamma API")
            return markets

        except Exception as e:
            print(f"❌ Error fetching from Gamma API: {e}")
            return []

    def fetch_markets_by_keywords(self, keywords: List[str], limit: int = 20) -> List[Market]:
        """
        Fetch markets matching keywords (e.g., 'bitcoin', 'ethereum')

        Uses two strategies:
        1. CLOB API with local filtering
        2. Gamma API with query parameter (fallback)

        Args:
            keywords: List of keywords to search for
            limit: Maximum number of markets per keyword

        Returns:
            List of Market objects
        """
        all_markets = []
        seen_condition_ids = set()

        # Strategy 1: Try CLOB API first (has token IDs)
        print(f"🔍 DEBUG: Fetching markets from CLOB API and filtering by keywords...")
        try:
            url = f"{self.clob_api_url}/markets"
            markets_data = self._make_request(url, params=None)

            # Handle dict response from CLOB API
            if markets_data and isinstance(markets_data, dict):
                print(f"🔍 DEBUG: CLOB API returned dict, extracting markets list...")
                if 'data' in markets_data:
                    markets_data = markets_data['data']
                elif 'markets' in markets_data:
                    markets_data = markets_data['markets']
                elif 'results' in markets_data:
                    markets_data = markets_data['results']

            if markets_data and isinstance(markets_data, list):
                print(f"🔍 DEBUG: Fetched {len(markets_data)} markets from CLOB API")

                for market_data in markets_data:
                    condition_id = market_data.get('condition_id') or market_data.get('conditionId')

                    # Skip duplicates
                    if condition_id in seen_condition_ids:
                        continue

                    # Try to parse market data with keyword filter
                    market = self._parse_clob_market(market_data, keywords_filter=keywords)
                    if market:
                        self._enrich_with_orderbook(market)
                        all_markets.append(market)
                        seen_condition_ids.add(condition_id)
                        print(f"   ✅ Found via CLOB API: {market.question[:60]}")

                print(f"🔍 DEBUG: {len(all_markets)} markets matched keywords from CLOB API")

        except Exception as e:
            print(f"❌ Error fetching from CLOB API: {e}")

        # Strategy 2: If we got very few results, try Gamma API
        if len(all_markets) < 5:
            print(f"\n🔍 DEBUG: Only found {len(all_markets)} markets via CLOB API. Trying Gamma API...")

            for keyword in keywords:
                try:
                    url = f"{self.gamma_api_url}/markets"
                    params = {
                        'closed': 'false',
                        'limit': limit,
                        'offset': 0,
                        'query': keyword
                    }

                    print(f"🔍 DEBUG: Fetching markets for keyword '{keyword}' from Gamma API")

                    markets_data = self._make_request(url, params)

                    if not markets_data or not isinstance(markets_data, list):
                        continue

                    print(f"🔍 DEBUG: API returned {len(markets_data)} markets for '{keyword}'")

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

        print(f"🔍 DEBUG: Total markets after all strategies: {len(all_markets)}")
        return all_markets

    def _parse_clob_market(self, market_data: Dict[str, Any], keywords_filter: List[str] = None) -> Optional[Market]:
        """
        Parse market data from CLOB API (different format than Gamma API)

        Args:
            market_data: Raw market data from CLOB API
            keywords_filter: Optional list of keywords to filter markets

        Returns:
            Market object or None if invalid
        """
        try:
            import json

            # Get condition_id - required field
            condition_id = market_data.get('condition_id') or market_data.get('conditionId')
            if not condition_id:
                return None

            # Filter out closed/inactive markets
            # Check for 'closed' or 'active' fields
            closed = market_data.get('closed', False)
            active = market_data.get('active', True)

            if closed or not active:
                return None

            # Get question/description
            question = market_data.get('question') or market_data.get('description', 'Unknown')

            # Filter by keywords if provided
            if keywords_filter:
                question_lower = question.lower()
                has_keyword = any(keyword.lower() in question_lower for keyword in keywords_filter)
                if not has_keyword:
                    return None

            # Get end date EARLY to filter out expired markets
            end_date_str = market_data.get('end_date_iso') or market_data.get('endDate') or market_data.get('end_date')
            if not end_date_str:
                return None

            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except:
                return None

            # Filter out markets that have already expired
            now = datetime.now(timezone.utc)
            if end_date <= now:
                return None

            # Get tokens array - this should contain the token IDs
            tokens = market_data.get('tokens', [])

            # Parse tokens if stringified
            if isinstance(tokens, str):
                try:
                    tokens = json.loads(tokens)
                except:
                    pass

            # Validate we have exactly 2 tokens (binary market)
            if not isinstance(tokens, list) or len(tokens) != 2:
                return None

            # Extract token IDs
            # Tokens can be either:
            # 1. List of token ID strings: ["0x123...", "0x456..."]
            # 2. List of token objects: [{"token_id": "0x123...", "outcome": "Yes", ...}, {...}]

            token_id_0 = None
            token_id_1 = None
            outcome_0 = 'yes'
            outcome_1 = 'no'

            if isinstance(tokens[0], str):
                # Simple string array
                token_id_0 = tokens[0]
                token_id_1 = tokens[1]
            elif isinstance(tokens[0], dict):
                # Object array - extract token_id field
                token_id_0 = tokens[0].get('token_id') or tokens[0].get('tokenId') or tokens[0].get('id')
                token_id_1 = tokens[1].get('token_id') or tokens[1].get('tokenId') or tokens[1].get('id')

                # Also get outcomes if available
                outcome_0 = str(tokens[0].get('outcome', 'yes')).lower()
                outcome_1 = str(tokens[1].get('outcome', 'no')).lower()

            # Validate token IDs
            if not token_id_0 or not token_id_1:
                return None

            # Note: end_date already parsed and validated above (lines 353-366)

            # Get prices if available
            price_0 = 0.5
            price_1 = 0.5

            # Check for outcome_prices field
            outcome_prices = market_data.get('outcome_prices') or market_data.get('outcomePrices')
            if outcome_prices:
                if isinstance(outcome_prices, str):
                    try:
                        outcome_prices = json.loads(outcome_prices)
                    except:
                        pass

                if isinstance(outcome_prices, list) and len(outcome_prices) >= 2:
                    price_0 = float(outcome_prices[0])
                    price_1 = float(outcome_prices[1])

            # Map to Up/Down based on outcome
            if 'yes' in outcome_0 or 'up' in outcome_0 or 'higher' in outcome_0:
                token_id_up = token_id_0
                price_up = price_0
                token_id_down = token_id_1
                price_down = price_1
            else:
                token_id_up = token_id_1
                price_up = price_1
                token_id_down = token_id_0
                price_down = price_0

            market = Market(
                condition_id=condition_id,
                question=question,
                end_date=end_date,
                token_id_up=token_id_up,
                token_id_down=token_id_down,
                price_up=price_up,
                price_down=price_down,
                slug=market_data.get('slug'),
                volume_24h=float(market_data.get('volume', 0)),
                liquidity=float(market_data.get('liquidity', 0))
            )

            return market

        except Exception as e:
            # Silently skip invalid markets
            return None

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

            # Filter out closed/inactive markets
            # Check for 'closed' or 'active' fields
            closed = market_data.get('closed', False)
            active = market_data.get('active', True)

            if closed or not active:
                return None

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

            # Filter out markets that have already expired
            now = datetime.now(timezone.utc)
            if end_date <= now:
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
