import pytest
from src.core.services.ai import GeminiStreamingService
from src.core.domain import VideoAnalysisInput

@pytest.fixture
def sample_videos():
    return [
        VideoAnalysisInput(
            video_id="vid_1",
            title="Bachata Demo",
            views=1000,
            retention_avg_pct=80.5,
            type="Long"
        )
    ]

def test_analyze_semantics(sample_videos):
    service = GeminiStreamingService()
    result = service.analyze_semantics(sample_videos)
    assert "Analysis Complete" in result
    assert "Strategy" in result

@pytest.mark.anyio
async def test_analyze_stream(sample_videos):
    service = GeminiStreamingService()
    chunks = []
    async for chunk in service.analyze_stream(sample_videos):
        chunks.append(chunk)

    full_response = "".join(chunks)
    assert "Analysis Complete" in full_response
