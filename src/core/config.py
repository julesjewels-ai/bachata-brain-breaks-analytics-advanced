"""
Configuration management for the application.
Handles loading and validating environment variables securely.
"""
import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class AppConfig(BaseModel):
    """
    Application configuration with strict validation.
    Follows Single Responsibility Principle for configuration.
    """
    google_api_key: Optional[str] = Field(
        default=None,
        description="API Key for Google GenAI service"
    )
    environment: str = Field(
        default="development",
        pattern=r"^(development|production|testing)$",
        description="Runtime environment"
    )
    cache_dir: str = Field(
        default=".cache/ai_responses",
        description="Directory to store AI response cache"
    )

    @classmethod
    def get_config(cls) -> "AppConfig":
        """
        Factory method to load and validate configuration.
        """
        try:
            return cls(
                google_api_key=os.getenv("GOOGLE_API_KEY"),
                environment=os.getenv("APP_ENV", "development"),
                cache_dir=os.getenv("AI_CACHE_DIR", ".cache/ai_responses")
            )
        except ValidationError as e:
            logger.error(f"Configuration validation failed: {e}")
            raise

    def get_api_key(self) -> str:
        """
        Retrieves API key with safety check.
        """
        if not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY is missing in environment variables.")
        return self.google_api_key
