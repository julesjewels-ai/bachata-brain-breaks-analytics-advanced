import json
import os
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from src.core.youtube import YouTubeAPIClient
from src.core.youtube_ingestion import YouTubeIngestionService


def load_snapshot(filename):
    filepath = os.path.join(os.path.dirname(__file__), "snapshots", filename)
    with open(filepath, "r") as f:
        return json.load(f)

@pytest.fixture
def mock_youtube_client():
    client = MagicMock(spec=YouTubeAPIClient)
    # Mock the async method to return some sample data
    client.get_channel_videos = AsyncMock(return_value=load_snapshot("youtube_ingestion_mock_data.json"))
    return client

@pytest.mark.asyncio
async def test_ingest_data(mock_youtube_client):
    service = YouTubeIngestionService(
        youtube_client=mock_youtube_client,
        target_channel_id="UC123"
    )
    
    # ingest_data is now async
    df = await service.ingest_data()
    
    # Check that it returns a DataFrame
    assert isinstance(df, pd.DataFrame)
    
    # It should have skipped the invalid one because empty title falls back to "Untitled Video" but 
    # wait - empty title fallback makes it valid!
    # Let's see how many were ingested
    assert len(df) == 3
    
    # Check that types were inferred correctly
    types = df["type"].tolist()
    assert types[0] == "Long"
    assert types[1] == "Shorts"
    assert types[2] == "Long"
    
    # Check retention mock presence
    assert "retention_avg_pct" in df.columns
    assert all((df["retention_avg_pct"] >= 20.0) & (df["retention_avg_pct"] <= 95.0))
    
    # Verify the mock was called with the right arguments
    mock_youtube_client.get_channel_videos.assert_called_once_with("UC123", max_results=50)

@pytest.mark.asyncio
async def test_ingest_data_validation_drop(mock_youtube_client):
    # If a video violates validation strongly and we can't clean it
    mock_youtube_client.get_channel_videos = AsyncMock(return_value=load_snapshot("youtube_ingestion_validation_data.json"))
    service = YouTubeIngestionService(
        youtube_client=mock_youtube_client,
        target_channel_id="UC123"
    )
    df = await service.ingest_data()
    
    # Should only have 1 valid row
    assert len(df) == 1
    assert df.iloc[0]["video_id"] == "VID_1"
