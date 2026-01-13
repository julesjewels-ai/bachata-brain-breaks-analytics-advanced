"""
Tests for configuration management.
"""
import os
import pytest
from src.core.config import AppConfig

def test_app_config_load():
    # Mock environment variables
    os.environ['GOOGLE_API_KEY'] = 'test_key'
    os.environ['APP_ENV'] = 'testing'

    config = AppConfig.get_config()

    assert config.google_api_key == 'test_key'
    assert config.environment == 'testing'
    assert config.get_api_key() == 'test_key'

def test_app_config_validation_error():
    # Test invalid environment
    os.environ['APP_ENV'] = 'invalid_env'
    os.environ['GOOGLE_API_KEY'] = 'test_key'

    with pytest.raises(ValueError):
        AppConfig.get_config()

def test_missing_api_key_access():
    if 'GOOGLE_API_KEY' in os.environ:
        del os.environ['GOOGLE_API_KEY']

    # Reset env to valid state
    os.environ['APP_ENV'] = 'testing'

    # It allows loading with None
    config = AppConfig.get_config()
    assert config.google_api_key is None

    # But checking it raises error
    with pytest.raises(ValueError, match="missing"):
        config.get_api_key()
