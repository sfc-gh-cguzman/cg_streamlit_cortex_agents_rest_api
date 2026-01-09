"""
Snowflake integration module for Cortex Agent application.

This module provides core Snowflake functionality including:
- External Snowflake client for API calls and session management
- Agent discovery and management utilities
- Core Snowflake connectivity and authentication

Usage:
    from modules.snowflake import ExternalSnowflakeClient, get_available_agents
    from modules.snowflake.client import ExternalSnowflakeClient
    from modules.snowflake.agents import get_available_agents, format_sample_questions_for_ui
    
    # Create Snowflake client
    client = ExternalSnowflakeClient(config)
    
    # Discover agents
    agents = get_available_agents(account, auth_token)
"""

from .client import ExternalSnowflakeClient
from .agents import get_available_agents, format_sample_questions_for_ui

# Export all Snowflake utilities
__all__ = [
    "ExternalSnowflakeClient",
    "get_available_agents", 
    "format_sample_questions_for_ui"
]
