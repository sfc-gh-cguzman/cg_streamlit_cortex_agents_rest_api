"""
Logging context management and decorators for enhanced observability.

This module provides utilities for structured logging context, performance monitoring,
and API call tracking with rich contextual information for debugging and monitoring.

Key Features:
- LoggingContext manager for adding structured context to logs
- Performance monitoring decorator with timing and error tracking
- API call logging decorator with session and thread context
- Automatic error logging with exception details
- Integration with Streamlit session state for user context

Components:
- LoggingContext: Context manager for scoped structured logging
- @log_performance: Decorator for automatic performance timing
- @log_api_call: Decorator for API request/response logging

Usage:
    # Add structured context to logs
    with LoggingContext(user_id="123", operation="data_load"):
        logger.info("Processing user data")  # Includes user_id and operation
    
    # Monitor function performance
    @log_performance("database_query")
    def fetch_user_data(user_id):
        return query_db(user_id)
    
    # Track API calls with context
    @log_api_call("cortex_agents", "POST")
    def make_agent_request(payload):
        return requests.post(url, json=payload)

Benefits:
- Consistent structured logging across the application
- Automatic performance monitoring and error tracking
- Rich context for debugging production issues
- Integration with monitoring and alerting systems
"""
import time
import functools
from .structured_logging import get_logger

class LoggingContext:
    """Context manager for adding structured context to logs"""
    
    def __init__(self, **context):
        self.context = context
        self.logger = get_logger()
        
    def __enter__(self):
        self.bound_logger = self.logger.bind(**self.context)
        return self.bound_logger
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.bound_logger.error(
                "Exception in logging context",
                exc_type=exc_type.__name__ if exc_type else None,
                exc_value=str(exc_val) if exc_val else None,
                **self.context
            )

def log_performance(operation_name: str):
    """Decorator for logging performance metrics"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(
                    "Operation completed",
                    operation=operation_name,
                    duration_seconds=round(duration, 4),
                    function=func.__name__,
                    success=True
                )
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    "Operation failed",
                    operation=operation_name,
                    duration_seconds=round(duration, 4),
                    function=func.__name__,
                    error=str(e),
                    error_type=type(e).__name__,
                    success=False
                )
                raise
                
        return wrapper
    return decorator

def log_api_call(api_name: str, method: str = "POST"):
    """Decorator for logging API calls with structured data"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger()
            
            # Extract relevant context
            context = {
                "api_name": api_name,
                "method": method,
                "function": func.__name__
            }
            
            # Add session context if available
            try:
                st = __import__('streamlit')
                if hasattr(st, 'session_state'):
                    # Use direct session state access to avoid circular imports during initialization
                    context.update({
                        "session_id": st.session_state.get("session_id"),
                        "thread_id": st.session_state.get("thread_id"),
                        "user_context": st.session_state.get("user_context", {})
                    })
            except ImportError:
                pass  # Streamlit not available, skip session context
            
            logger.info("API call started", **context)
            
            try:
                result = func(*args, **kwargs)
                logger.info("API call completed", success=True, **context)
                return result
                
            except Exception as e:
                logger.error(
                    "API call failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    success=False,
                    **context
                )
                raise
                
        return wrapper
    return decorator
