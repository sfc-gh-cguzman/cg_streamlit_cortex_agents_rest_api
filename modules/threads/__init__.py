"""
Thread management module for Cortex Agent conversations.

This module provides thread lifecycle management utilities for Snowflake Cortex Agents:
- Thread creation, retrieval, and deletion operations
- Thread message management with pagination
- Session state integration for thread persistence

Usage:
    from modules.threads import create_thread, get_thread_messages, delete_thread
    from modules.threads.management import get_or_create_thread
    
    # Create a new thread
    thread_id = create_thread(config, client)
    
    # Get thread messages
    response = get_thread_messages(thread_id, config, client)
    
    # Delete thread
    success = delete_thread(thread_id, config, client)
"""

from .management import (
    create_thread,
    get_thread_messages, 
    delete_thread,
    get_or_create_thread
)

# Export all thread management utilities
__all__ = [
    "create_thread",
    "get_thread_messages",
    "delete_thread", 
    "get_or_create_thread"
]
