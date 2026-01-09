"""
Citation and annotation processing module.

This module provides comprehensive citation handling for Snowflake Cortex Agent responses including:
- Citation ID processing (cs_xxx → [1], [2], [3])
- Streaming citation collection
- Post-completion citation display
- Citation deduplication and formatting

Key Components:
- processor: Citation ID text processing and replacement
- collector: Real-time citation collection during streaming
- display: Post-completion citation display and formatting
- utils: Shared citation utilities and patterns

Features:
- Dual citation system (numbered + hyperlinks)
- Session-persistent citation numbering
- Deduplication across conversation
- Support for documentation and file citations
"""

from .processor import process_citation_ids_in_text, reset_citation_numbering
from .collector import handle_streaming_citation
from .display import display_post_completion_citations
from .utils import initialize_citation_session_state, clear_citation_state

# Export all citation utilities
__all__ = [
    'process_citation_ids_in_text',
    'reset_citation_numbering',
    'handle_streaming_citation', 
    'display_post_completion_citations',
    'initialize_citation_session_state',
    'clear_citation_state'
]
