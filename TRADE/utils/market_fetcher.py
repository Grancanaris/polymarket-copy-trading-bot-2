"""
Market data fetcher for Polymarket API
"""

import requests
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from models.market import Market
from config.config import ScalpingConfig


class MarketFetcher:
    """Fetches market data from Polymarket APIs"""

    def __init__(self):
        self.gamma_api_url = ScalpingConfig.POLYMARKET_API_URL
        self.clob_api_url = ScalpingConfig.HOST

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

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            markets_data = response.json()
            markets = []

            for market_data in markets_data:
                # Skip non-binary markets
                if len(market_data.get('tokens', [])) != 2:
                    continue

                # Parse market data
                market = self._parse_market(market_data)
                if market:
                    # Get orderbook data for this market
                    self._enrich_with_orderbook(market)
                    markets.append(market)

            return markets

        except Exception as e:
            print(f"❌ Error fetching markets: {e}")
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

                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()

                markets_data = response.json()

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
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            market_data = response.json()
            market = self._parse_market(market_data)

            if market:
                self._enrich_with_orderbook(market)

            return market

        except Exception as e:
            print(f"❌ Error fetching market {condition_id}: {e}")
            return None
