"""
Citation collection utilities for real-time streaming responses.

This module handles the collection and processing of citation annotations
during Snowflake Cortex Agent response streaming. Citations are collected
in real-time but not displayed immediately - they are stored for post-completion
display to provide a clean streaming experience.

Key Features:
- Real-time citation collection from response.text.annotation events
- Support for documentation and file citations with dual storage
- Thread-based and legacy session state management
- Citation ID mapping for text replacement functionality
- String-based citation parsing for file references
- Error handling and debug logging integration

Citation Flow:
1. response.text.annotation events trigger handle_streaming_citation()
2. Citations are parsed and validated from annotation data
3. Both thread-based and legacy storage ensure compatibility
4. Citation IDs are mapped for later text replacement
5. Post-completion display shows all collected citations

Usage:
    # Called automatically during streaming
    handle_streaming_citation(annotation_data, content_idx, debug_mode)
    
    # Access collected citations
    citations = get_collected_citations()
    doc_citations = get_citations_by_type('documentation')
"""

import streamlit as st
from typing import Dict, Any, List
from modules.logging import get_logger
from modules.config.app_config import ENABLE_CITATIONS

logger = get_logger()


def handle_streaming_citation(annotation_data: Dict[str, Any], content_idx: int, debug_mode: bool = False) -> None:
    """
    Collect citations for post-completion display.
    
    This function processes citation annotations during streaming and stores them
    in session state for later display. It does not display citations immediately.
    
    Args:
        annotation_data: Citation annotation data from the API
        content_idx: Content index from the streaming event
        debug_mode: Whether to show debug information
    """
    if not ENABLE_CITATIONS:
        return
    
    logger.debug("Processing streaming citation", 
                content_index=content_idx,
                annotation_type=type(annotation_data).__name__)
    
    # Enhanced annotation data logging for debugging
    logger.debug(f"Collector - Annotation data: {annotation_data}")
    logger.debug(f"Collector - Annotation type: {type(annotation_data)}")
    logger.debug(f"Collector - Annotation keys: {list(annotation_data.keys()) if isinstance(annotation_data, dict) else 'Not a dict'}")
    
    try:
        # Get session manager for citation storage
        from modules.config.session_state import get_session_manager
        session_manager = get_session_manager()
        
        # Citation collection always happens regardless of debug mode - core functionality
        
        # Always log citation collection regardless of debug mode
        logger.debug(f"Collecting citation - Title: {annotation_data.get('doc_title', 'Unknown')}")
        logger.debug(f"Citation data: doc_id={annotation_data.get('doc_id')}, type={annotation_data.get('type')}")
        
        # Extract documentation citation data
        if isinstance(annotation_data, dict):
            doc_id = annotation_data.get("doc_id")
            doc_title = annotation_data.get("doc_title") 
            citation_type = annotation_data.get("type")
            
            # Log what we're finding in annotation data
            logger.debug(f"Annotation parsing - doc_id: {doc_id}, doc_title: {doc_title}, type: {citation_type}")
            logger.debug(f"Annotation keys: {list(annotation_data.keys())}")
            
            # Collect documentation citations
            if doc_id and doc_title:
                logger.debug(f"Valid documentation citation - {doc_title}")
                
                # Extract search_result_id from annotation data (this is the exact citation ID)
                search_result_id = annotation_data.get('search_result_id')
                
                citation_entry = {
                    'doc_id': doc_id,
                    'doc_title': doc_title,
                    'citation_type': 'documentation',
                    'search_result_id': search_result_id,  # Store the exact citation ID
                    'annotation_data': annotation_data
                }
                # Store in both legacy (for compatibility) and thread-based storage
                session_manager.tool_state.streaming_citations.append(citation_entry)
                session_manager.add_thread_citation(citation_entry)
                
                # Store the exact citation ID in the mapping for text replacement
                if search_result_id:
                    # Note: citation_mapping might be different from citation_id_mapping
                    # Keeping basic functionality but using session manager
                    if not hasattr(session_manager.tool_state, 'citation_mapping'):
                        session_manager.tool_state.citation_mapping = {}
                    session_manager.tool_state.citation_mapping[search_result_id] = citation_entry
                    logger.debug(f"Stored citation mapping: {search_result_id} → {doc_title}")
                
                logger.debug("Collected documentation citation",
                           doc_id=doc_id,
                           doc_title=doc_title)
                
            # Handle file citations
            file_path = annotation_data.get("file_path") or annotation_data.get("path") or annotation_data.get("url")
            file_type = annotation_data.get("file_type") or annotation_data.get("type")
            
            if file_path and file_type and file_type != "cortex_search_citation":
                citation_entry = {
                    'file_path': file_path,
                    'file_type': file_type,
                    'citation_type': 'file',
                    'citation_id': f"stream_{len(session_manager.tool_state.streaming_citations)}",
                    'annotation_data': annotation_data
                }
                # Store in both legacy (for compatibility) and thread-based storage
                session_manager.tool_state.streaming_citations.append(citation_entry)
                session_manager.add_thread_citation(citation_entry)
                
                logger.debug("Collected file citation",
                           file_path=file_path,
                           file_type=file_type)
        
        # Handle string-based citations with file references
        elif isinstance(annotation_data, str):
            from modules.utils.text_processing import parse_file_references_new
            cleaned_text, file_references = parse_file_references_new(annotation_data)
            
            for file_path, file_type, _ in file_references:
                citation_entry = {
                    'file_path': file_path,
                    'file_type': file_type,
                    'citation_type': 'file',
                    'citation_id': f"stream_{len(session_manager.tool_state.streaming_citations)}",
                    'annotation_data': annotation_data
                }
                # Store in both legacy (for compatibility) and thread-based storage
                session_manager.tool_state.streaming_citations.append(citation_entry)
                session_manager.add_thread_citation(citation_entry)
                
                logger.debug("Collected parsed file citation",
                           file_path=file_path,
                           file_type=file_type)
                
    except Exception as e:
        logger.error("Error collecting streaming citation", 
                    error=str(e), 
                    annotation_data=annotation_data)
        # Error handling happens regardless of debug mode - core functionality


def get_collected_citations() -> List[Dict[str, Any]]:
    """Get all citations collected during streaming."""
    from modules.config.session_state import get_session_manager
    
    session_manager = get_session_manager()
    return session_manager.tool_state.streaming_citations


def clear_collected_citations() -> None:
    """Clear all collected citations from session state."""
    from modules.config.session_state import get_session_manager
    
    session_manager = get_session_manager()
    session_manager.tool_state.streaming_citations.clear()


def count_collected_citations() -> int:
    """Count the number of citations collected during streaming."""
    return len(get_collected_citations())


def get_citations_by_type(citation_type: str) -> List[Dict[str, Any]]:
    """Get collected citations filtered by type (documentation, file)."""
    citations = get_collected_citations()
    return [c for c in citations if c.get('citation_type') == citation_type]
