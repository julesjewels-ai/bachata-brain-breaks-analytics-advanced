"""
Tests for formatting module.
"""
import pandas as pd
from pydantic import ValidationError, BaseModel, Field
from src.core.formatting import (
    format_validation_error, prepare_display_dataframe
)


def test_prepare_display_dataframe():
    df = pd.DataFrame({
        'video_id': ['1'],
        'title': ['Test'],
        'views': [1000],
        'retention_avg_pct': [50.6],
        'type': ['Shorts']
    })
    display_df = prepare_display_dataframe(df)
    assert display_df['Views'].iloc[0] == "1,000"
    assert display_df['Retention'].iloc[0] == "50.6%"
    assert 'Video Title' in display_df.columns


def test_prepare_display_dataframe_empty():
    df = pd.DataFrame()
    display_df = prepare_display_dataframe(df)
    assert display_df.empty


def test_format_validation_error():
    class TestModel(BaseModel):
        field1: int = Field(..., gt=10)

    try:
        TestModel(field1=5)
    except ValidationError as e:
        msg = format_validation_error(e)
        assert "Validation Error:" in msg
        assert "field1" in msg
        assert "Input should be greater than 10" in msg
