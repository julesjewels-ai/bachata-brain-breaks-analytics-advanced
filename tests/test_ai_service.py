"""
Unit tests for GeminiStreamingService.
"""
from src.core.services.ai import GeminiStreamingService
from src.core.domain import VideoAnalysisInput

def test_analyze_semantics_valid_input():
    service = GeminiStreamingService()
    videos = [
        VideoAnalysisInput(
            video_id="vid_1",
            title="Test Video",
            views=1000,
            retention_avg_pct=80.5,
            type="Long"
        )
    ]
    result = service.analyze_semantics(videos)
    assert "[Gemini 3 Thinking Mode]" in result
    assert "Analysis Complete" in result

def test_analyze_semantics_empty_input():
    service = GeminiStreamingService()
    result = service.analyze_semantics([])
    assert result == "No data to analyze."
