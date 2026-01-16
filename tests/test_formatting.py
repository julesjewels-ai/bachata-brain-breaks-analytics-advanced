import pytest
from pydantic import BaseModel, ValidationError, Field, field_validator
from src.core.formatting import format_validation_error

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
