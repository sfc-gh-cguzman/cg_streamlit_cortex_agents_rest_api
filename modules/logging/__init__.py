"""
Structured logging module for Cortex Agent application.

This module provides comprehensive logging capabilities including:
- Structured logging setup and configuration
- Logging context management
- Performance monitoring decorators
- API call logging decorators

Usage:
    from modules.logging import get_logger, LoggingContext, log_performance

    # Get configured logger
    logger = get_logger()
    
    # Use context manager
    with LoggingContext(user_id="123", operation="data_load"):
        logger.info("Processing data")
    
    # Use performance decorator
    @log_performance("database_query")
    def query_database():
        pass
"""

# Import all logging utilities for convenient access
from .structured_logging import (
    setup_structured_logging,
    get_logger,
    update_log_level
)

from .context import (
    LoggingContext,
    log_performance,
    log_api_call
)

# Export all logging utilities
__all__ = [
    "setup_structured_logging",
    "get_logger",
    "update_log_level",
    "LoggingContext", 
    "log_performance",
    "log_api_call"
]
