"""
UI Components Module

This module provides user interface components for the Cortex Agent application,
including configuration UI, debug interfaces, and display utilities.

Components:
- config_ui: Main configuration interface (sidebar, agent selection, sample questions)
- debug_interface: Debug tools for API request/response inspection and file operations

Key Functions:
- config_options(): Main sidebar configuration interface
- display_agent_status(): Agent selection status display  
- clear_conversation_state(): Reset conversation state
- validate_agent_selection(): Validate agent is selected
- display_debug_interface_now(): Immediate debug interface after streaming
- display_debug_interface_if_available(): Persistent debug interface
- clear_debug_session_state(): Clear debug session variables
"""

# Configuration UI components
from .config_ui import (
    config_options,
    display_agent_status,
    clear_conversation_state,
    validate_agent_selection
)

# Debug interface components  
from .debug_interface import (
    display_debug_interface_now,
    display_debug_interface_if_available,
    clear_debug_session_state
)

__all__ = [
    # Configuration UI
    'config_options',
    'display_agent_status', 
    'clear_conversation_state',
    'validate_agent_selection',
    # Debug interface
    'display_debug_interface_now',
    'display_debug_interface_if_available',
    'clear_debug_session_state'
]
