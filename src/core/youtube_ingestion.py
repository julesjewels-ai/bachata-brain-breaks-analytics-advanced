"""
Real Data Ingestion Service using YouTube Data API.
"""
import logging
import random
from typing import List, Dict, Any

import pandas as pd

from src.core.interfaces import DataIngestionService
from src.core.models import VideoAnalysisInput
from src.core.youtube import YouTubeAPIClient

logger = logging.getLogger(__name__)

class YouTubeIngestionService(DataIngestionService):
    """
    Ingests video data from a real YouTube channel via the Data API.
    Transforms data into VideoAnalysisInput models.
    """
    def __init__(self, youtube_client: YouTubeAPIClient, target_channel_id: str):
        self.youtube_client = youtube_client
        self.target_channel_id = target_channel_id

    async def ingest_data(self) -> pd.DataFrame:
        """
        Asynchronously fetches and transforms channel videos.
        Returns a validated pandas DataFrame.
        """
        raw_data = await self._fetch_and_transform()
        return pd.DataFrame(raw_data)

    async def _fetch_and_transform(self) -> List[Dict[str, Any]]:
        """
        Fetches the latest videos and maps them into the expected schema.
        """
        videos = await self.youtube_client.get_channel_videos(self.target_channel_id, max_results=50)
        
        validated_data = []
        for video in videos:
            # For the prototype, we assign a random retention since the Public Data API 
            # does not expose true audience retention (requires OAuth).
            # We also guess type based on title or default to Long.
            title = video.get("title", "")
            is_shorts = "#shorts" in title.lower() or "shorts" in title.lower()
            
            # Clean title for basic validation
            clean_title = title.replace("\n", " ").strip()
            if not clean_title or not clean_title.isprintable():
                clean_title = "Untitled Video"

            record = {
                "video_id": video["video_id"],
                "title": clean_title[:200],  # Ensure it fits max length
                "views": video.get("views", 0),
                "retention_avg_pct": random.uniform(20.0, 95.0), # Mock retention
                "type": "Shorts" if is_shorts else "Long"
            }
            
            # Validate through Pydantic model
            try:
                validated_model = VideoAnalysisInput(**record)
                validated_data.append(validated_model.model_dump())
            except Exception as e:
                logger.warning(
                    "Skipping video %s: %s",
                    video.get("video_id", "unknown"), e
                )
                
        return validated_data
