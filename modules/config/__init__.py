"""
Configuration management module for Cortex Agent application.

This module provides configuration utilities including:
- Application constants and feature flags
- Snowflake authentication configuration  
- Session state management

Usage:
    from modules.config import SnowflakeConfig, ensure_session_state_defaults
    from modules.config.app_config import API_TIMEOUT, ENABLE_DEBUG_MODE
    
    # Create Snowflake configuration
    config = SnowflakeConfig()
    
    # Initialize session state
    ensure_session_state_defaults()
"""

# Import all configuration utilities for convenient access
from .app_config import (
    API_TIMEOUT,
    MAX_DATAFRAME_ROWS,
    THREAD_BASE_ENDPOINT,
    ENABLE_FILE_PREVIEW,
    ENABLE_CITATIONS,
    ENABLE_SUGGESTIONS,
    MAX_PDF_PAGES,
    ENABLE_DEBUG_MODE,
    SHOW_FIRST_TOOL_USE_ONLY
)

from .snowflake_config import SnowflakeConfig

from .session_state import ensure_session_state_defaults

# Export all configuration utilities
__all__ = [
    # Application configuration
    "API_TIMEOUT",
    "MAX_DATAFRAME_ROWS", 
    "THREAD_BASE_ENDPOINT",
    "ENABLE_FILE_PREVIEW",
    "ENABLE_CITATIONS",
    "ENABLE_SUGGESTIONS",
    "MAX_PDF_PAGES",
    "ENABLE_DEBUG_MODE",
    "SHOW_FIRST_TOOL_USE_ONLY",
    
    # Snowflake configuration
    "SnowflakeConfig",
    
    # Session state management
    "ensure_session_state_defaults"
]
