"""
Utility module for text processing and data operations.

This module provides text parsing, file reference extraction, and SQL result
processing utilities for handling agent responses and data operations.

Usage:
    from modules.utils import parse_file_references_new, bot_retrieve_sql_results
    
    # Parse file references from text
    cleaned_text, references = parse_file_references_new(agent_response)
    
    # Execute SQL and get DataFrame
    df = bot_retrieve_sql_results("SELECT * FROM table", session)
"""

from .text_processing import (
    parse_file_references_new,
    bot_retrieve_sql_results
)

# Export all utility functions
__all__ = [
    "parse_file_references_new",
    "bot_retrieve_sql_results"
]
