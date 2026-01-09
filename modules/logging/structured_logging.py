"""
Structured logging setup and configuration for Cortex Agent application.

This module provides structured logging capabilities using structlog with features:
- JSON structured output for production
- Rich console output for development  
- Performance timing capabilities
- Contextual logging with session/thread/user information
- Integration with Streamlit's debug mode
"""
import logging
import sys
import structlog
import streamlit as st

def _get_debug_mode() -> bool:
    """
    Safely get debug mode status, avoiding circular imports.
    Falls back to direct session state access if session manager not available.
    """
    try:
        # Try to import session manager (may fail during initialization)
        from modules.config.session_state import get_session_manager
        return get_session_manager().is_debug_mode()
    except (ImportError, AttributeError):
        # Fallback to direct session state access during initialization
        try:
            return st.session_state.get("debug_payload_response", False)
        except:
            return False

def setup_structured_logging():
    """
    Configure structured logging with structlog for enhanced observability.
    
    Features:
    - JSON structured output for production
    - Rich console output for development  
    - Performance timing capabilities
    - Contextual logging with session/thread/user information
    - Integration with Streamlit's debug mode
    """
    
    # Determine log level based on debug mode
    debug_mode = _get_debug_mode()
    log_level = logging.DEBUG if debug_mode else logging.INFO
    
    # Configure standard logging first
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    
    # Configure structlog processors
    processors = [
        # Add timestamp
        structlog.processors.TimeStamper(fmt="ISO"),
        
        # Add log level
        structlog.stdlib.add_log_level,
        
        # Add logger name
        structlog.stdlib.add_logger_name,
        
        # Add caller information in debug mode
        structlog.processors.CallsiteParameterAdder(
            parameters=[structlog.processors.CallsiteParameter.FILENAME,
                       structlog.processors.CallsiteParameter.FUNC_NAME,
                       structlog.processors.CallsiteParameter.LINENO]
        ) if _get_debug_mode() else structlog.processors.CallsiteParameterAdder(),
        
        # Process stack info
        structlog.processors.StackInfoRenderer(),
        
        # Format exceptions
        structlog.processors.format_exc_info,
        
        # Final processor - choose format based on environment
        structlog.dev.ConsoleRenderer(colors=True) if sys.stdout.isatty() 
        else structlog.processors.JSONRenderer()
    ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )
    
    # Return configured logger
    return structlog.get_logger("cortex_agent")

# Initialize logging (but don't configure until after Streamlit setup)
logger = None

def get_logger():
    """Get the configured structured logger, setting up if needed"""
    global logger
    if logger is None:
        logger = setup_structured_logging()
    
    # Update log level based on current debug mode setting
    debug_mode = _get_debug_mode()
    log_level = logging.DEBUG if debug_mode else logging.INFO
    logging.getLogger().setLevel(log_level)
    
    return logger

def update_log_level():
    """Update the log level based on current debug mode setting"""
    debug_mode = _get_debug_mode()
    log_level = logging.DEBUG if debug_mode else logging.INFO
    logging.getLogger().setLevel(log_level)
    
    # Also update the root logger to be sure
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Use the configured logger to log the level change
    logger = get_logger()
    logger.info(f"Log level updated to: {'DEBUG' if debug_mode else 'INFO'} (debug_mode={debug_mode})")
