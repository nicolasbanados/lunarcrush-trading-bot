"""
LunarCrush API Client
Fetches social intelligence data for cryptocurrency trading signals
"""

import requests
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class LunarCrushClient:
    """Client for interacting with LunarCrush API v4"""
    
    def __init__(self, api_key: str, base_url: str = "https://lunarcrush.com/api4"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.cache = {}
        self.cache_ttl = 180  # 3 minutes
        
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make HTTP request to LunarCrush API with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"LunarCrush API request failed: {e}")
            raise
    
    def get_coins_list(self, sort: str = "market_cap_rank", limit: int = 100, 
                       desc: bool = False) -> List[Dict]:
        """
        Get list of coins with social and market metrics
        
        Args:
            sort: Sort by metric (market_cap_rank, galaxy_score, alt_rank, etc.)
            limit: Number of results (max 1000)
            desc: Reverse sort order
            
        Returns:
            List of coin data dictionaries
        """
        cache_key = f"coins_list_{sort}_{limit}_{desc}"
        
        # Check cache
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug(f"Using cached coins list")
                return cached_data
        
        params = {
            "sort": sort,
            "limit": limit
        }
        if desc:
            params["desc"] = "true"
        
        try:
            response = self._make_request("/public/coins/list/v2", params)
            data = response.get("data", [])
            
            # Cache the result
            self.cache[cache_key] = (data, time.time())
            
            logger.info(f"Fetched {len(data)} coins from LunarCrush")
            return data
        except Exception as e:
            logger.error(f"Failed to fetch coins list: {e}")
            return []
    
    def get_coin_details(self, coin: str) -> Optional[Dict]:
        """
        Get detailed information for a specific coin
        
        Args:
            coin: Coin symbol (e.g., 'btc', 'eth') or numeric ID
            
        Returns:
            Coin data dictionary or None
        """
        cache_key = f"coin_{coin}"
        
        # Check cache
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                return cached_data
        
        try:
            response = self._make_request(f"/public/coins/{coin}/v1")
            data = response.get("data", {})
            
            # Cache the result
            self.cache[cache_key] = (data, time.time())
            
            return data
        except Exception as e:
            logger.error(f"Failed to fetch coin details for {coin}: {e}")
            return None
    
    def get_topic_summary(self, topic: str) -> Optional[Dict]:
        """
        Get 24-hour social activity summary for a topic
        
        Args:
            topic: Topic name (e.g., 'bitcoin', 'ethereum')
            
        Returns:
            Topic summary data or None
        """
        try:
            response = self._make_request(f"/public/topic/{topic}/v1")
            return response.get("data", {})
        except Exception as e:
            logger.error(f"Failed to fetch topic summary for {topic}: {e}")
            return None
    
    def get_topic_time_series(self, topic: str, bucket: str = "hour") -> List[Dict]:
        """
        Get historical time series data for a topic
        
        Args:
            topic: Topic name
            bucket: 'hour' or 'day'
            
        Returns:
            List of time series data points
        """
        params = {"bucket": bucket}
        
        try:
            response = self._make_request(f"/public/topic/{topic}/time-series/v2", params)
            return response.get("data", [])
        except Exception as e:
            logger.error(f"Failed to fetch time series for {topic}: {e}")
            return []
    
    def calculate_metrics_changes(self, coin_data: Dict, historical_data: List[Dict]) -> Dict:
        """
        Calculate percentage changes in social metrics
        
        Args:
            coin_data: Current coin data
            historical_data: Historical time series data
            
        Returns:
            Dictionary with calculated changes
        """
        if not historical_data or len(historical_data) < 2:
            return {}
        
        # Calculate 7-day averages
        recent_7d = historical_data[-168:] if len(historical_data) >= 168 else historical_data  # Last 7 days (hourly)
        
        avg_social_volume = sum(d.get("posts_active", 0) for d in recent_7d) / len(recent_7d) if recent_7d else 0
        avg_interactions = sum(d.get("interactions", 0) for d in recent_7d) / len(recent_7d) if recent_7d else 0
        
        current_social_volume = coin_data.get("social_volume_24h", 0)
        current_interactions = coin_data.get("interactions_24h", 0)
        
        social_volume_change = ((current_social_volume - avg_social_volume) / avg_social_volume) if avg_social_volume > 0 else 0
        interactions_change = ((current_interactions - avg_interactions) / avg_interactions) if avg_interactions > 0 else 0
        
        return {
            "social_volume_change": social_volume_change,
            "interactions_change": interactions_change,
            "avg_social_volume_7d": avg_social_volume,
            "avg_interactions_7d": avg_interactions
        }
    
    def get_enriched_coins_data(self, limit: int = 100) -> List[Dict]:
        """
        Get coins list with enriched metrics and calculated changes
        
        Args:
            limit: Number of coins to fetch
            
        Returns:
            List of enriched coin data
        """
        coins = self.get_coins_list(limit=limit)
        
        enriched_coins = []
        for coin in coins:
            # Add calculated fields
            enriched_coin = coin.copy()
            
            # Calculate Galaxy Score momentum
            galaxy_score = coin.get("galaxy_score")
            galaxy_score_prev = coin.get("galaxy_score_previous")
            if galaxy_score is not None and galaxy_score_prev is not None:
                enriched_coin["galaxy_score_momentum"] = galaxy_score > galaxy_score_prev
                enriched_coin["galaxy_score_change"] = galaxy_score - galaxy_score_prev
            else:
                enriched_coin["galaxy_score_momentum"] = False
                enriched_coin["galaxy_score_change"] = 0
            
            # Calculate AltRank improvement
            alt_rank = coin.get("alt_rank")
            alt_rank_prev = coin.get("alt_rank_previous")
            if alt_rank is not None and alt_rank_prev is not None:
                enriched_coin["altrank_improvement"] = alt_rank_prev - alt_rank  # Lower is better
            else:
                enriched_coin["altrank_improvement"] = 0
            
            # Calculate volume change
            volume_24h = coin.get("volume_24h", 0)
            # Estimate previous volume (would need historical data for accuracy)
            enriched_coin["volume_change_estimate"] = 0.1  # Placeholder
            
            enriched_coins.append(enriched_coin)
        
        logger.info(f"Enriched {len(enriched_coins)} coins with calculated metrics")
        return enriched_coins
    
    def clear_cache(self):
        """Clear the internal cache"""
        self.cache = {}
        logger.debug("Cache cleared")


if __name__ == "__main__":
    # Test the client
    logging.basicConfig(level=logging.INFO)
    
    # This requires a valid API key
    # client = LunarCrushClient("YOUR_API_KEY")
    # coins = client.get_enriched_coins_data(limit=10)
    # print(f"Fetched {len(coins)} coins")
    # if coins:
    #     print(f"First coin: {coins[0]['symbol']} - Galaxy Score: {coins[0].get('galaxy_score')}")
    
    print("LunarCrush client module loaded successfully")
