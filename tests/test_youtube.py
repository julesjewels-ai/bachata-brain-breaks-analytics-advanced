import json
import pytest
import os
from unittest.mock import patch, MagicMock
from src.core.youtube import YouTubeAPIClient
from src.core.config import AppConfig

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
@patch('src.core.youtube.aiohttp.ClientSession.get')
async def test_get_channel_videos_success(mock_get, youtube_client):
    channel_id = "UC12345"
    uploads_id = "UU12345"

    # We need to mock the async context manager returned by session.get
    mock_response_channel = MagicMock()
    mock_response_channel.status = 200
    mock_response_channel.json = pytest.helpers.async_return(load_snapshot("youtube_channel_response.json"))
    mock_response_channel.__aenter__.return_value = mock_response_channel

    mock_response_playlist = MagicMock()
    mock_response_playlist.status = 200
    mock_response_playlist.json = pytest.helpers.async_return(load_snapshot("youtube_playlist_response.json"))
    mock_response_playlist.__aenter__.return_value = mock_response_playlist
    
    mock_response_videos = MagicMock()
    mock_response_videos.status = 200
    mock_response_videos.json = pytest.helpers.async_return(load_snapshot("youtube_videos_response.json"))
    mock_response_videos.__aenter__.return_value = mock_response_videos

    # Set up side_effect to return different responses based on url
    def get_side_effect(url, *args, **kwargs):
        if 'channels' in url:
            return mock_response_channel
        elif 'playlistItems' in url:
            return mock_response_playlist
        elif 'videos' in url:
            return mock_response_videos
        return MagicMock()

    mock_get.side_effect = get_side_effect

    videos = await youtube_client.get_channel_videos(channel_id)

    assert len(videos) == 1
    assert videos[0]["video_id"] == "VID_1"
    assert videos[0]["title"] == "Test Video"
    assert videos[0]["views"] == 1500
    assert videos[0]["likes"] == 100
    assert videos[0]["comments"] == 10

@pytest.mark.asyncio
@patch('src.core.youtube.aiohttp.ClientSession.get')
async def test_get_channel_videos_no_uploads(mock_get, youtube_client, caplog):
    channel_id = "UC_NO_UPLOADS"
    
    mock_response_channel = MagicMock()
    mock_response_channel.status = 200
    mock_response_channel.json = pytest.helpers.async_return({"items": []})
    mock_response_channel.__aenter__.return_value = mock_response_channel

    mock_get.return_value = mock_response_channel

    videos = await youtube_client.get_channel_videos(channel_id)

    assert videos == []
    assert "Could not find uploads playlist" in caplog.text