import json
import pytest
from unittest.mock import patch, mock_open
from src.core.repository import JsonlRepository, RepositoryError
from src.core.models import VideoAnalysisInput

class TestJsonlRepository:
    def test_save_success(self):
        filepath = "test_archive.jsonl"
        repo = JsonlRepository[VideoAnalysisInput](filepath)

        items = [
            VideoAnalysisInput(
                video_id="vid-1",
                title="Test Video 1",
                views=100,
                retention_avg_pct=50.0,
                type="Shorts"
            ),
            VideoAnalysisInput(
                video_id="vid-2",
                title="Test Video 2",
                views=200,
                retention_avg_pct=60.0,
                type="Long"
            )
        ]

        m_open = mock_open()
        with patch("builtins.open", m_open):
            repo.save(items)

        # Verify that open was called correctly
        m_open.assert_called_once_with(filepath, 'a', encoding='utf-8')

        # Verify that items were written
        handle = m_open()

        # Two items, so two write calls
        assert handle.write.call_count == 2

        call_args_list = handle.write.call_args_list
        write1 = call_args_list[0][0][0]
        write2 = call_args_list[1][0][0]

        data1 = json.loads(write1.strip())
        data2 = json.loads(write2.strip())

        assert data1["video_id"] == "vid-1"
        assert data2["video_id"] == "vid-2"


    def test_save_io_error(self):
        repo = JsonlRepository[VideoAnalysisInput]("test_archive.jsonl")
        items = [
            VideoAnalysisInput(
                video_id="vid-1",
                title="Test Video 1",
                views=100,
                retention_avg_pct=50.0,
                type="Shorts"
            )
        ]

        # Patch builtins.open to raise IOError
        with patch("builtins.open", side_effect=IOError("Test IO Error")):
            with pytest.raises(RepositoryError, match="Failed to save items to test_archive.jsonl: Test IO Error"):
                repo.save(items)
