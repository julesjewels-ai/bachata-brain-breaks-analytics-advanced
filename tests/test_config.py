"""
Tests for configuration module.
"""
import os
import pytest
from unittest.mock import patch
from src.core.config import AppConfig


def test_app_config_defaults():
    # Mock environment variables to be empty/default
    with patch.dict(os.environ, {}, clear=True):
        config = AppConfig.get_config()
        assert config.environment == "development"
        assert config.google_api_key is None


def test_app_config_env_vars():
    with patch.dict(os.environ, {
        "GOOGLE_API_KEY": "test_key",
        "APP_ENV": "production"
    }, clear=True):
        config = AppConfig.get_config()
        assert config.environment == "production"
        assert config.google_api_key == "test_key"


def test_get_api_key_raises_error():
    with patch.dict(os.environ, {}, clear=True):
        config = AppConfig.get_config()
        with pytest.raises(ValueError, match="GOOGLE_API_KEY is missing"):
            config.get_api_key()
