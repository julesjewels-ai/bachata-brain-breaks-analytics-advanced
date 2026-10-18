import json
import os
from unittest.mock import MagicMock

import pytest
from aioresponses import aioresponses

from src.core.config import AppConfig
from src.core.youtube import YouTubeAPIClient


def load_snapshot(filename):
    filepath = os.path.join(os.path.dirname(__file__), "snapshots", filename)
    with open(filepath, "r") as f:
        return json.load(f)

@pytest.fixture
def mock_config():
    config = MagicMock(spec=AppConfig)
    config.get_youtube_api_key.return_value = "TEST_API_KEY"
    return config

@pytest.fixture
def youtube_client(mock_config):
    return YouTubeAPIClient(config=mock_config)

@pytest.mark.asyncio
async def test_get_channel_videos_success(youtube_client):
    channel_id = "UC12345"
    uploads_id = "UU12345"
    
    with aioresponses() as m:
        # Mock channel request
        m.get(
            f"https://www.googleapis.com/youtube/v3/channels?id={channel_id}&key=TEST_API_KEY&part=contentDetails",
            payload=load_snapshot("youtube_channel_response.json")
        )
        
        # Mock playlistItems request
        m.get(
            f"https://www.googleapis.com/youtube/v3/playlistItems?key=TEST_API_KEY&maxResults=50&part=snippet&playlistId={uploads_id}",
            payload=load_snapshot("youtube_playlist_response.json")
        )
        
        # Mock videos statistics request
        m.get(
            "https://www.googleapis.com/youtube/v3/videos?id=VID_1&key=TEST_API_KEY&part=statistics",
            payload=load_snapshot("youtube_videos_response.json")
        )
        
        videos = await youtube_client.get_channel_videos(channel_id)
        
        assert len(videos) == 1
        assert videos[0]["video_id"] == "VID_1"
        assert videos[0]["title"] == "Test Video"
        assert videos[0]["views"] == 1500
        assert videos[0]["likes"] == 100
        assert videos[0]["comments"] == 10

@pytest.mark.asyncio
async def test_get_channel_videos_no_uploads(youtube_client, caplog):
    channel_id = "UC_NO_UPLOADS"
    
    with aioresponses() as m:
        m.get(
            f"https://www.googleapis.com/youtube/v3/channels?id={channel_id}&key=TEST_API_KEY&part=contentDetails",
            payload={"items": []}
        )
        
        videos = await youtube_client.get_channel_videos(channel_id)
        
        assert videos == []
        assert "Could not find uploads playlist" in caplog.text
