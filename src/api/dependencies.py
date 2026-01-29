from functools import lru_cache
from src.core.services import AnalyticsService

@lru_cache()
def get_analytics_service() -> AnalyticsService:
    return AnalyticsService()
