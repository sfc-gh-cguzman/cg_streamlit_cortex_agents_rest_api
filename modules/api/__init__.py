"""
API communication module for Cortex Agent application.

This module provides HTTP client utilities and API communication tools
for interacting with Snowflake Cortex Agents and external services.

Usage:
    from modules.api import execute_curl_request, agent_run_streaming, stream_events_realtime
    
    # Make HTTP request
    response = execute_curl_request(
        method="GET",
        url="https://example.com/api/endpoint",
        auth_token="Bearer your_token",
        timeout=30
    )
    
    # Run agent with streaming
    stream_response = agent_run_streaming(thread_id, message, config, client)
    stream_events_realtime(stream_response)
"""

from .http_client import execute_curl_request
from .cortex_integration import agent_run_streaming, stream_events_realtime

# Export all API utilities
__all__ = [
    "execute_curl_request",
    "agent_run_streaming",
    "stream_events_realtime"
]
