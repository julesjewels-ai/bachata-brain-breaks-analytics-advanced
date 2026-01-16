import pytest
from pydantic import ValidationError
from src.core.app import VideoAnalysisInput

def test_formula_injection_equals():
    """Test that titles starting with '=' are rejected (Excel/CSV injection)."""
    data = {
        "video_id": "vid_1",
        "title": "=1+1",
        "views": 100,
        "retention_avg_pct": 50.5,
        "type": "Shorts"
    }
    # This assertion is expected to fail before the fix
    with pytest.raises(ValidationError) as exc:
        VideoAnalysisInput(**data)
    assert "Potential Excel formula injection detected" in str(exc.value)

def test_formula_injection_at():
    """Test that titles starting with '@' are rejected."""
    data = {
        "video_id": "vid_1",
        "title": "@SUM(1,1)",
        "views": 100,
        "retention_avg_pct": 50.5,
        "type": "Shorts"
    }
    with pytest.raises(ValidationError) as exc:
        VideoAnalysisInput(**data)
    assert "Potential Excel formula injection detected" in str(exc.value)

def test_formula_injection_plus():
    """Test that titles starting with '+' are rejected."""
    data = {
        "video_id": "vid_1",
        "title": "+cmd|' /C calc'!A0",
        "views": 100,
        "retention_avg_pct": 50.5,
        "type": "Shorts"
    }
    with pytest.raises(ValidationError) as exc:
        VideoAnalysisInput(**data)
    assert "Potential Excel formula injection detected" in str(exc.value)

def test_formula_injection_minus():
    """Test that titles starting with '-' are rejected."""
    data = {
        "video_id": "vid_1",
        "title": "-1+1",
        "views": 100,
        "retention_avg_pct": 50.5,
        "type": "Shorts"
    }
    with pytest.raises(ValidationError) as exc:
        VideoAnalysisInput(**data)
    assert "Potential Excel formula injection detected" in str(exc.value)
