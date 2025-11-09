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

            for market_data in markets_data:
                # Skip non-binary markets
                tokens = market_data.get('tokens', [])
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

                    # Skip non-binary markets
                    if len(market_data.get('tokens', [])) != 2:
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
            # Extract tokens
            tokens = market_data.get('tokens', [])
            if len(tokens) != 2:
                return None

            # Parse end date
            end_date_str = market_data.get('endDate', market_data.get('end_date_iso'))
            if not end_date_str:
                return None

            try:
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
            except:
                return None

            # Get token data
            token_0 = tokens[0]
            token_1 = tokens[1]

            # Determine which is "Up" (Yes) and which is "Down" (No)
            # Usually outcome "Yes" has higher price when market is bullish
            outcome_0 = token_0.get('outcome', '').lower()
            outcome_1 = token_1.get('outcome', '').lower()

            # Map outcomes to Up/Down
            if 'yes' in outcome_0 or 'up' in outcome_0 or 'higher' in outcome_0:
                token_id_up = token_0.get('token_id')
                price_up = float(token_0.get('price', 0.5))
                token_id_down = token_1.get('token_id')
                price_down = float(token_1.get('price', 0.5))
            else:
                token_id_up = token_1.get('token_id')
                price_up = float(token_1.get('price', 0.5))
                token_id_down = token_0.get('token_id')
                price_down = float(token_0.get('price', 0.5))

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
