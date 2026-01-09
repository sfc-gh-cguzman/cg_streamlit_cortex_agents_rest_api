"""
Application configuration constants and settings.

This module provides centralized configuration constants for the Cortex Agent application,
including API settings, endpoint configurations, and feature flags.
"""
import config

# =============================================================================
# Global Constants for External Deployment
# =============================================================================

# API Configuration (from config.py)
API_TIMEOUT = config.API_TIMEOUT_MS  # in milliseconds
MAX_DATAFRAME_ROWS = config.MAX_DATAFRAME_ROWS

# Thread API endpoint (following official API specification)
# Reference: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-threads-rest-api
THREAD_BASE_ENDPOINT = "/api/v2/cortex/threads"

# Note: Agent-specific endpoints are now built dynamically based on selected agent
# Reference: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-rest-api

# Feature flags (from config.py - can be overridden in session state)
ENABLE_FILE_PREVIEW = config.ENABLE_FILE_PREVIEW
ENABLE_CITATIONS = config.ENABLE_CITATIONS  
ENABLE_SUGGESTIONS = config.ENABLE_SUGGESTIONS
MAX_PDF_PAGES = config.MAX_PDF_PAGES
ENABLE_DEBUG_MODE = config.ENABLE_DEBUG_MODE
SHOW_FIRST_TOOL_USE_ONLY = config.SHOW_FIRST_TOOL_USE_ONLY

# SSL Configuration
SNOWFLAKE_SSL_VERIFY = config.SNOWFLAKE_SSL_VERIFY
