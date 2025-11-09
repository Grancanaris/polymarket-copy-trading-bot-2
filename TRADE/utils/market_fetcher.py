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
                possible_token_fields = ['tokens', 'clobTokenIds', 'tokenIds', 'outcomes', 'outcomePrices', 'markets']
                for field in possible_token_fields:
                    if field in markets_data[0]:
                        value = markets_data[0][field]
                        value_type = type(value).__name__
                        print(f"🔍 DEBUG: Found field '{field}': type={value_type}, value={str(value)[:200]}")

                        # Try to parse if it's a stringified JSON
                        if isinstance(value, str):
                            try:
                                import json
                                parsed = json.loads(value)
                                print(f"🔍 DEBUG: '{field}' is stringified JSON! Parsed type={type(parsed).__name__}, length={len(parsed) if isinstance(parsed, (list, dict)) else 'N/A'}")
                            except:
                                pass

            for market_data in markets_data:
                # Skip non-binary markets
                tokens = market_data.get('tokens', [])

                # If tokens is empty or wrong length, try alternative fields
                if len(tokens) != 2:
                    # Try clobTokenIds (may be stringified JSON)
                    if 'clobTokenIds' in market_data:
                        clob_tokens = market_data.get('clobTokenIds')
                        if isinstance(clob_tokens, str):
                            try:
                                import json
                                tokens = json.loads(clob_tokens)
                            except:
                                tokens = []
                        else:
                            tokens = clob_tokens if clob_tokens else []

                    # Try outcomes field (may be a list of outcome names like ["Yes", "No"])
                    elif 'outcomes' in market_data:
                        outcomes = market_data.get('outcomes')
                        if isinstance(outcomes, str):
                            try:
                                import json
                                tokens = json.loads(outcomes)
                            except:
                                tokens = []
                        elif isinstance(outcomes, list):
                            tokens = outcomes
                        else:
                            tokens = []

                if len(tokens) != 2:
                    continue

                # Parse market data
                market = self._parse_market(market_data)
                if market:
                    # Get orderbook data for this market
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

        Args:
            keywords: List of keywords to search for
            limit: Maximum number of markets per keyword

        Returns:
            List of Market objects
        """
        all_markets = []
        seen_condition_ids = set()

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

                print(f"🔍 DEBUG: Received {len(markets_data)} markets for '{keyword}'")

                for market_data in markets_data:
                    condition_id = market_data.get('conditionId')

                    # Skip duplicates
                    if condition_id in seen_condition_ids:
                        continue

                    # Skip non-binary markets - try alternative field names
                    tokens = market_data.get('tokens', [])

                    if len(tokens) != 2:
                        # Try clobTokenIds (may be stringified JSON)
                        clob_tokens = market_data.get('clobTokenIds')
                        if isinstance(clob_tokens, str):
                            try:
                                import json
                                tokens = json.loads(clob_tokens)
                            except:
                                tokens = []
                        elif clob_tokens:
                            tokens = clob_tokens

                    if len(tokens) != 2:
                        # Try outcomes field
                        outcomes = market_data.get('outcomes')
                        if isinstance(outcomes, str):
                            try:
                                import json
                                tokens = json.loads(outcomes)
                            except:
                                tokens = []
                        elif isinstance(outcomes, list):
                            tokens = outcomes
                        else:
                            tokens = []

                    if len(tokens) != 2:
                        continue

                    market = self._parse_market(market_data)
                    if market:
                        self._enrich_with_orderbook(market)
                        all_markets.append(market)
                        seen_condition_ids.add(condition_id)

            except Exception as e:
                print(f"❌ Error fetching markets for '{keyword}': {e}")
                import traceback
                traceback.print_exc()

        print(f"🔍 DEBUG: Total markets fetched: {len(all_markets)}")
        return all_markets

    def _parse_market(self, market_data: Dict[str, Any]) -> Optional[Market]:
        """
        Parse raw market data into Market object

        Args:
            market_data: Raw market data from API

        Returns:
            Market object or None if invalid
        """
        try:
            import json

            # Extract tokens - try multiple field names
            tokens = market_data.get('tokens', [])

            # Try clobTokenIds (may be stringified JSON)
            if len(tokens) != 2:
                clob_tokens = market_data.get('clobTokenIds')
                if isinstance(clob_tokens, str):
                    try:
                        tokens = json.loads(clob_tokens)
                    except:
                        tokens = []
                elif clob_tokens:
                    tokens = clob_tokens if isinstance(clob_tokens, list) else []

            # Try outcomes field (may be stringified JSON)
            if len(tokens) != 2:
                outcomes = market_data.get('outcomes')
                if isinstance(outcomes, str):
                    try:
                        tokens = json.loads(outcomes)
                    except:
                        tokens = []
                elif isinstance(outcomes, list):
                    tokens = outcomes
                else:
                    tokens = []

            if len(tokens) != 2:
                return None

            # Try to get outcome prices (may be stringified JSON)
            prices = []
            outcome_prices = market_data.get('outcomePrices')
            if isinstance(outcome_prices, str):
                try:
                    prices = json.loads(outcome_prices)
                except:
                    prices = []
            elif isinstance(outcome_prices, list):
                prices = outcome_prices

            # Parse end date
            end_date_str = market_data.get('endDate', market_data.get('end_date_iso'))
            if not end_date_str:
                return None

            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except:
                return None

            # Get token IDs - tokens might be outcome strings like ["Yes", "No"]
            # while actual token IDs are in clobTokenIds
            clob_token_ids = market_data.get('clobTokenIds')
            if isinstance(clob_token_ids, str):
                try:
                    clob_token_ids = json.loads(clob_token_ids)
                except:
                    clob_token_ids = None

            # Debug: Print token structure for first market
            if not hasattr(self, '_debug_printed'):
                print(f"🔍 DEBUG: Tokens: {tokens}")
                print(f"🔍 DEBUG: Clob Token IDs: {clob_token_ids}")
                print(f"🔍 DEBUG: Prices: {prices}")
                self._debug_printed = True

            # Determine token IDs and outcomes
            token_0 = tokens[0]
            token_1 = tokens[1]

            # Get actual token IDs
            if clob_token_ids and len(clob_token_ids) == 2:
                # Use clob token IDs if available
                actual_token_id_0 = clob_token_ids[0]
                actual_token_id_1 = clob_token_ids[1]
            elif isinstance(token_0, str) and len(token_0) > 10:
                # Tokens are already IDs (long hex strings)
                actual_token_id_0 = token_0
                actual_token_id_1 = token_1
            elif isinstance(token_0, dict):
                # Tokens are objects with metadata
                actual_token_id_0 = token_0.get('token_id') or token_0.get('tokenId') or token_0.get('id')
                actual_token_id_1 = token_1.get('token_id') or token_1.get('tokenId') or token_1.get('id')
            else:
                # Can't determine token IDs
                return None

            # Get prices
            if prices and len(prices) == 2:
                price_0 = float(prices[0])
                price_1 = float(prices[1])
            elif isinstance(token_0, dict) and 'price' in token_0:
                price_0 = float(token_0.get('price', 0.5))
                price_1 = float(token_1.get('price', 0.5))
            else:
                # Try to get from top-level market data
                price_0 = float(market_data.get('lastTradePrice', 0.5))
                price_1 = 1.0 - price_0

            # Determine which is "Yes" (Up) and which is "No" (Down)
            if isinstance(token_0, str):
                # Check if it's an outcome string like "Yes"/"No"
                outcome_0 = token_0.lower()
                outcome_1 = token_1.lower()
            elif isinstance(token_0, dict):
                outcome_0 = token_0.get('outcome', '').lower()
                outcome_1 = token_1.get('outcome', '').lower()
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

        Args:
            market: Market object to enrich with orderbook data
        """
        try:
            # Fetch orderbook from CLOB API
            url = f"{self.clob_api_url}/book"

            # Get orderbook for Up token
            params_up = {'token_id': market.token_id_up}
            response_up = requests.get(url, params=params_up, timeout=5)

            if response_up.status_code == 200:
                book_up = response_up.json()
                bids = book_up.get('bids', [])
                asks = book_up.get('asks', [])

                if bids:
                    market.best_bid_up = float(bids[0].get('price', 0))
                if asks:
                    market.best_ask_up = float(asks[0].get('price', 0))

            # Get orderbook for Down token
            params_down = {'token_id': market.token_id_down}
            response_down = requests.get(url, params=params_down, timeout=5)

            if response_down.status_code == 200:
                book_down = response_down.json()
                bids = book_down.get('bids', [])
                asks = book_down.get('asks', [])

                if bids:
                    market.best_bid_down = float(bids[0].get('price', 0))
                if asks:
                    market.best_ask_down = float(asks[0].get('price', 0))

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
            market = self._parse_market(market_data)

            if market:
                self._enrich_with_orderbook(market)

            return market

        except Exception as e:
            print(f"❌ Error fetching market {condition_id}: {e}")
            return None
