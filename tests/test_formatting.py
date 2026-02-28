import pytest
import pandas as pd
from pydantic import BaseModel, ValidationError, Field, field_validator
from src.core.formatting import format_validation_error, prepare_display_dataframe


class ValidationTestModel(BaseModel):
    name: str = Field(..., min_length=3)
    age: int = Field(..., gt=0)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if "bad" in v:
            raise ValueError("Name cannot contain 'bad'")
        return v


def test_format_validation_error_basic():
    """Test formatting of standard Pydantic errors."""
    with pytest.raises(ValidationError) as exc:
        ValidationTestModel(name="A", age=-5)

    formatted = format_validation_error(exc.value)
    print(f"\nFormatted Output:\n{formatted}")  # For visual inspection in logs

    assert "Validation Error:" in formatted
    assert "• name: String should have at least 3 characters" in formatted
    assert "• age: Input should be greater than 0" in formatted


def test_format_validation_error_custom():
    """Test formatting of custom ValueError messages."""
    with pytest.raises(ValidationError) as exc:
        ValidationTestModel(name="bad name", age=10)

    formatted = format_validation_error(exc.value)

    # "Value error, " should be stripped
    assert "• name: Name cannot contain 'bad'" in formatted
    assert "Value error," not in formatted


def test_prepare_display_dataframe():
    """Test dataframe preparation for display."""
    df = pd.DataFrame({
        'title': ['Video A', 'Video B'],
        'views': [1000, 1500000],
        'retention_avg_pct': [45.678, 99.123],
        'type': ['Shorts', 'Long']
    })

    display_df = prepare_display_dataframe(df)

    # Check columns are renamed
    assert "Video Title" in display_df.columns
    assert "Views" in display_df.columns
    assert "Retention" in display_df.columns

    # Check values are formatted
    assert display_df.iloc[0]['Views'] == "1,000"
    assert display_df.iloc[1]['Views'] == "1,500,000"
    assert display_df.iloc[0]['Retention'] == "45.7%"
    assert display_df.iloc[1]['Retention'] == "99.1%"

    # Test with empty dataframe
    empty_df = pd.DataFrame()
    display_empty = prepare_display_dataframe(empty_df)
    assert display_empty.empty
