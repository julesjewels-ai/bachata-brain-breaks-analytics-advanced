"""
YouTube Data API Client for fetching channel and video statistics.
"""
import aiohttp
import logging
from typing import Dict, Any, List, Optional
from src.core.config import AppConfig

logger = logging.getLogger(__name__)

class YouTubeAPIClient:
    """
    Client for interacting with the YouTube Data API v3 asynchronously.
    """
    BASE_URL = "https://www.googleapis.com/youtube/v3"

    def __init__(self, config: AppConfig):
        self.api_key = config.get_youtube_api_key()

    async def get_channel_videos(self, channel_id: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Fetches the latest videos for a given channel ID.
        Uses a single shared aiohttp session for all API calls.
        """
        async with aiohttp.ClientSession() as session:
            # First get the uploads playlist ID for the channel
            uploads_playlist_id = await self._get_uploads_playlist_id(session, channel_id)
            if not uploads_playlist_id:
                logger.warning("Could not find uploads playlist for channel %s", channel_id)
                return []

            # Then fetch videos from the uploads playlist
            videos = await self._get_playlist_items(session, uploads_playlist_id, max_results)

            # Get detailed statistics for these videos
            if not videos:
                return []

            video_ids = [v["snippet"]["resourceId"]["videoId"] for v in videos]
            video_stats = await self.get_video_statistics(session, video_ids)

            # Merge data
            result = []
            for video in videos:
                vid_id = video["snippet"]["resourceId"]["videoId"]
                stats = video_stats.get(vid_id, {})
                result.append({
                    "video_id": vid_id,
                    "title": video["snippet"]["title"],
                    "published_at": video["snippet"]["publishedAt"],
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "comments": int(stats.get("commentCount", 0))
                })

            return result

    async def _get_uploads_playlist_id(
        self, session: aiohttp.ClientSession, channel_id: str
    ) -> Optional[str]:
        """Gets the playlist ID for the channel's uploads."""
        params: Dict[str, str | int] = {
            "part": "contentDetails",
            "id": channel_id,
            "key": self.api_key
        }
        async with session.get(f"{self.BASE_URL}/channels", params=params) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error("YouTube API Error (%s) on /channels: %s", response.status, error_text)
            response.raise_for_status()
            data = await response.json()
            items = data.get("items", [])
            if not items:
                return None
            return items[0].get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")

    async def _get_playlist_items(
        self, session: aiohttp.ClientSession, playlist_id: str, max_results: int
    ) -> List[Dict[str, Any]]:
        """Fetches items from a playlist."""
        params: Dict[str, str | int] = {
            "part": "snippet",
            "playlistId": playlist_id,
            "maxResults": min(max_results, 50),
            "key": self.api_key
        }
        async with session.get(f"{self.BASE_URL}/playlistItems", params=params) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error("YouTube API Error (%s) on /playlistItems: %s", response.status, error_text)
            response.raise_for_status()
            data = await response.json()
            return data.get("items", [])

    async def get_video_statistics(
        self, session: aiohttp.ClientSession, video_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetches statistics for a batch of video IDs.
        Returns a dictionary mapping video ID to its stats.
        """
        if not video_ids:
            return {}

        params: Dict[str, str | int] = {
            "part": "statistics",
            "id": ",".join(video_ids),
            "key": self.api_key
        }

        async with session.get(f"{self.BASE_URL}/videos", params=params) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error("YouTube API Error (%s) on /videos: %s", response.status, error_text)
            response.raise_for_status()
            data = await response.json()

            stats_map = {}
            for item in data.get("items", []):
                stats_map[item["id"]] = item.get("statistics", {})

            return stats_map
