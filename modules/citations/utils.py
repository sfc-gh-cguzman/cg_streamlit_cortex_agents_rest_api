"""
Citation utilities and shared functionality.

This module provides common utilities for citation management including
session state initialization, citation clearing, and validation functions.

Key Features:
- Session state management for citations
- Citation validation utilities  
- Common citation patterns and constants
- Cleanup and reset functions
- Citation data validation and formatting
- File and documentation citation type detection

Usage:
    # Initialize citation system
    initialize_citation_session_state()
    
    # Clear citations for new conversation
    clear_citation_state()
    
    # Validate citation data
    is_valid, error = validate_citation_data(citation_dict)
    
    # Check citation types
    if is_documentation_citation(data):
        key = format_citation_key(doc_id, doc_title)
"""

from typing import Dict, Any, Tuple
from modules.logging import get_logger

logger = get_logger()

# Citation patterns and constants
CITATION_ID_PATTERN = r'\b(cs_[a-f0-9-]+)\b'
DOCUMENTATION_CITATION_TYPE = "cortex_search_citation"


def initialize_citation_session_state() -> None:
    """Initialize all citation-related session state variables."""
    from modules.config.session_state import get_session_manager
    
    # Session manager handles all initialization automatically
    session_manager = get_session_manager()
    session_manager.ensure_defaults()
    
    logger.debug("Initialized citation session state via SessionStateManager")


def clear_citation_state() -> None:
    """Clear citation-related session state for new conversations."""
    from modules.config.session_state import get_session_manager
    
    session_manager = get_session_manager()
    
    # Clear citation state via session manager
    session_manager.clear_tool_citations()
    session_manager.reset_citations()
    
    # Also clear table data when clearing citations  
    clear_table_state()
    
    logger.debug("Cleared all citation session state via SessionStateManager")
    logger.debug("All response-specific citation namespaces cleared for new conversation")


def clear_table_state() -> None:
    """Clear table and chart related session state for new conversations or after errors."""
    from modules.config.session_state import get_session_manager
    
    session_manager = get_session_manager()
    
    # Clear response content via session manager
    table_count = len(session_manager.response_state.current_response_tables)
    chart_count = len(session_manager.response_state.current_response_charts)
    
    session_manager.clear_response_content()
    
    if table_count > 0:
        logger.debug(f"Cleared {table_count} tables from session state")
    if chart_count > 0:
        logger.debug(f"Cleared {chart_count} charts from session state")
    
    logger.debug("Cleared table and chart reference tracking state via SessionStateManager")


def get_citation_stats() -> Dict[str, int]:
    """Get statistics about current citation state."""
    from modules.config.session_state import get_session_manager
    
    session_manager = get_session_manager()
    
    return {
        'citation_counter': session_manager.tool_state.citation_counter,
        'mapped_citations': len(session_manager.tool_state.citation_id_mapping),
        'collected_citations': len(session_manager.tool_state.streaming_citations),
        'tool_citations': len(session_manager.get_tool_citations())
    }


def validate_citation_data(citation: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate citation data structure.
    
    Args:
        citation: Citation dictionary to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(citation, dict):
        return False, "Citation must be a dictionary"
    
    citation_type = citation.get('citation_type')
    if not citation_type:
        return False, "Citation must have a citation_type field"
    
    if citation_type == 'documentation':
        if not citation.get('doc_id'):
            return False, "Documentation citation must have doc_id"
        if not citation.get('doc_title'):
            return False, "Documentation citation must have doc_title"
    
    elif citation_type == 'file':
        if not citation.get('file_path'):
            return False, "File citation must have file_path"
        if not citation.get('file_type'):
            return False, "File citation must have file_type"
    
    else:
        return False, f"Unknown citation type: {citation_type}"
    
    return True, ""


def is_documentation_citation(annotation_data: Dict[str, Any]) -> bool:
    """Check if annotation data represents a documentation citation."""
    return (
        isinstance(annotation_data, dict) and
        annotation_data.get('type') == DOCUMENTATION_CITATION_TYPE and
        annotation_data.get('doc_id') and
        annotation_data.get('doc_title')
    )


def is_file_citation(annotation_data: Dict[str, Any]) -> bool:
    """Check if annotation data represents a file citation."""
    if not isinstance(annotation_data, dict):
        return False
    
    file_path = annotation_data.get("file_path") or annotation_data.get("path") or annotation_data.get("url")
    file_type = annotation_data.get("file_type") or annotation_data.get("type")
    
    return (
        file_path and 
        file_type and 
        file_type != DOCUMENTATION_CITATION_TYPE
    )


def extract_citation_id_from_url(url: str) -> str:
    """Extract citation ID from a documentation URL if present."""
    import re
    
    # Look for citation ID pattern in URL
    match = re.search(CITATION_ID_PATTERN, url)
    return match.group(1) if match else ""


def format_citation_key(doc_id: str, doc_title: str) -> str:
    """Create a standardized citation key for deduplication."""
    return f"{doc_id}#{doc_title}"


def format_file_citation_key(file_path: str, file_type: str) -> str:
    """Create a standardized file citation key for deduplication."""
    return f"file#{file_path}#{file_type}"
