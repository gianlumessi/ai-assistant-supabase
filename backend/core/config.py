"""Configuration validation and environment variable management."""

import os
import logging
from typing import Optional
from dotenv import load_dotenv
from backend.core.exceptions import ConfigurationError

load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Application configuration with validation."""

    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str

    # OpenAI
    OPENAI_API_KEY: str

    # App settings
    LOG_LEVEL: str = 'INFO'
    USE_JSON_LOGGING: bool = False

    @classmethod
    def validate_and_load(cls) -> None:
        """
        Validate and load all required environment variables.
        Raises ConfigurationError if any required variables are missing.
        """
        errors = []

        # Validate Supabase configuration
        cls.SUPABASE_URL = os.getenv('SUPABASE_URL', '')
        if not cls.SUPABASE_URL:
            errors.append('SUPABASE_URL is required')

        cls.SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY', '')
        if not cls.SUPABASE_ANON_KEY:
            errors.append('SUPABASE_ANON_KEY is required')

        cls.SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')
        if not cls.SUPABASE_SERVICE_ROLE_KEY:
            errors.append('SUPABASE_SERVICE_ROLE_KEY is required')

        # Validate OpenAI configuration
        cls.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
        if not cls.OPENAI_API_KEY:
            errors.append('OPENAI_API_KEY is required')

        # Optional configuration
        cls.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
        cls.USE_JSON_LOGGING = os.getenv('USE_JSON_LOGGING', 'false').lower() in ('true', '1', 'yes')

        if errors:
            error_message = 'Configuration validation failed:\n  - ' + '\n  - '.join(errors)
            raise ConfigurationError(error_message)

        logger.info('Configuration validated successfully')

    @classmethod
    def get_openai_api_key(cls) -> str:
        """Get OpenAI API key."""
        if not hasattr(cls, 'OPENAI_API_KEY') or not cls.OPENAI_API_KEY:
            raise ConfigurationError('OPENAI_API_KEY not configured. Call validate_and_load() first.')
        return cls.OPENAI_API_KEY

    @classmethod
    def get_supabase_config(cls) -> tuple[str, str, str]:
        """Get Supabase configuration (URL, anon key, service role key)."""
        if not hasattr(cls, 'SUPABASE_URL'):
            raise ConfigurationError('Supabase configuration not loaded. Call validate_and_load() first.')
        return cls.SUPABASE_URL, cls.SUPABASE_ANON_KEY, cls.SUPABASE_SERVICE_ROLE_KEY


# Initialize configuration on module import (will be called during startup)
config = Config
