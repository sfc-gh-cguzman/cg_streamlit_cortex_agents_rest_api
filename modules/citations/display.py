"""
Citation display utilities for post-completion rendering.

This module handles the display of collected citations after streaming completes.
It renders citations as clean hyperlinks and file previews with proper deduplication.

Key Features:
- Post-completion citation display
- Clean hyperlink formatting
- File citation previews
- Deduplication of identical citations
- Professional citation section layout
"""

import streamlit as st
from typing import Set
from modules.logging import get_logger
from modules.config.app_config import ENABLE_CITATIONS

logger = get_logger()


def display_post_completion_citations() -> None:
    """
    Display all collected citations after streaming completes.
    
    This function renders a dedicated "Citations" section with:
    - Clean hyperlinks for documentation citations
    - File previews for file citations
    - Proper deduplication to avoid duplicate displays
    """
    # Always log that we're being called for debugging
    logger.debug("display_post_completion_citations() called")
    
    if not ENABLE_CITATIONS:
        logger.debug("Citations disabled - ENABLE_CITATIONS = False")
        return
    
    logger.debug("Citations enabled - proceeding with display")
    
    # Get citations from session manager
    from modules.config.session_state import get_session_manager
    
    session_manager = get_session_manager()
    
    # Get citation data from session manager (mixed scope architecture)
    thread_citations = session_manager.get_thread_citations()  # Thread-scoped: persistent data
    thread_tool_citations = session_manager.get_thread_tool_citations()  # Thread-scoped: tool data
    request_citation_mapping = session_manager.get_request_citation_mapping()  # Request-scoped: counters
    
    # Fallback to legacy storage for compatibility
    tool_result_citations = session_manager.get_tool_citations()
    citation_id_mapping = session_manager.tool_state.citation_id_mapping
    streaming_citations = session_manager.tool_state.streaming_citations
    
    # Use mixed scope: thread-based data, request-based counters
    citations = thread_citations if thread_citations else streaming_citations
    citation_mapping = request_citation_mapping if request_citation_mapping else citation_id_mapping
    effective_tool_citations = thread_tool_citations if thread_tool_citations else tool_result_citations
    
    # Get debug mode status
    debug_mode = session_manager.is_debug_mode()
    
    current_response_id = session_manager.response_state.current_response_id
    logger.debug(f"Citation display check - Response: {current_response_id}")
    logger.debug(f"Thread citations: {len(thread_citations)}, Request mapping: {len(request_citation_mapping)}, Tool citations: {len(thread_tool_citations)}")
    logger.debug(f"Legacy - Streaming: {len(streaming_citations)}, Tool: {len(tool_result_citations)}, ID mapping: {len(citation_id_mapping)}")
    logger.debug(f"Final selection - Citations: {len(citations)}, Citation mapping: {len(citation_mapping)}, Tool citations: {len(effective_tool_citations)}")
    logger.debug(f"Final citation display - Debug mode: {debug_mode}")
    
    # Only display citations that were actually used in the response text
    
    if citation_mapping and effective_tool_citations:
        # Build ordered citations based on actual usage in response text
        ordered_citations = []
        for citation_number in sorted(citation_mapping.values()):
            # Find the citation ID that maps to this number
            citation_id = None
            for cid, cnum in citation_mapping.items():
                if cnum == citation_number:
                    citation_id = cid
                    break
            
            # Only include citations that exist in tool results AND were used in text
            if citation_id and citation_id in effective_tool_citations:
                citation_data = effective_tool_citations[citation_id].copy()  # Copy to avoid modifying original
                citation_data['citation_number'] = citation_number  # Add number for display
                citation_data['citation_id'] = citation_id  # Store the ID for reference
                ordered_citations.append(citation_data)
                logger.debug(f"Used Citation [{citation_number}]: {citation_id} -> {citation_data.get('doc_title')}")
            else:
                logger.warning(f"Citation number {citation_number} mapped to {citation_id} but not found in tool results")
        
        citations = ordered_citations
        logger.debug(f"Displaying {len(citations)} used citations (out of {len(tool_result_citations)} total)")
        
        # Debug: Log unused citations
        used_citation_ids = set(citation_id_mapping.keys())
        all_citation_ids = set(tool_result_citations.keys())
        unused_citations = all_citation_ids - used_citation_ids
        if unused_citations:
            logger.debug(f"📋 UNUSED CITATIONS: {len(unused_citations)} citations from tool results were not referenced in text")
            for unused_id in list(unused_citations)[:3]:  # Show first 3 examples
                unused_title = tool_result_citations[unused_id].get('doc_title', 'Unknown')
                logger.debug(f"  🚫 Unused: {unused_id} -> {unused_title}")
                
    elif streaming_citations:
        citations = streaming_citations
        logger.debug(f"Displaying {len(citations)} streaming citations (fallback)")
    else:
        logger.debug("No citations to display - no citation mapping or tool citations available")
        logger.debug("No citations to display - no data in session state")
        # Show citation state info for debugging
        logger.debug(f"Citation mapping: {citation_id_mapping}")
        logger.debug(f"Tool citations: {len(tool_result_citations)} available")
        
        # 🔍 DEBUG: Show a message in the UI too  
        if debug_mode:
            st.warning("**DEBUG:** No citations found to display. Check debug logs for details.")
        
        return
    
    logger.debug("Displaying post-completion citations", citation_count=len(citations))
    
    # Display citations section header with material icon
    st.subheader(":material/sticky_note_2: Citations")
    
    # Build comma-separated citation list with clickable links
    citation_items = []
    displayed_citation_ids: Set[str] = set()
    
    for citation in citations:
        citation_type = citation.get('citation_type')
        
        # Handle tool result citations (new format from Snowflake Cortex)
        if citation.get('doc_id') and citation.get('doc_title') and citation.get('id', '').startswith('cs_'):
            citation_id = citation.get('id')
            doc_title = citation.get('doc_title', 'Unknown')
            doc_id = citation.get('doc_id', '')
            citation_number = citation.get('citation_number', 0)
            
            # Skip duplicates
            if citation_id not in displayed_citation_ids:
                displayed_citation_ids.add(citation_id)
                
                # Create clickable link if doc_id is a URL
                if doc_id and (doc_id.startswith("http://") or doc_id.startswith("https://")):
                    citation_items.append(f"**[{citation_number}]**: [{doc_title}]({doc_id})")
                else:
                    citation_items.append(f"**[{citation_number}]**: {doc_title}")
                
                logger.debug(f"Added citation [{citation_number}]: {doc_title}")
            
        # Handle legacy streaming citations 
        elif citation_type == 'documentation':
            doc_title = citation.get('doc_title', 'Unknown')
            citation_number = len(citation_items) + 1
            citation_items.append(f"**[{citation_number}]**: {doc_title}")
            
        elif citation_type == 'file':
            filename = citation.get('filename', 'Unknown File')
            citation_number = len(citation_items) + 1
            citation_items.append(f"**[{citation_number}]**: {filename}")
            
        else:
            logger.debug(f"Unknown citation format: {citation}")
    
    # Display comma-separated citation list
    if citation_items:
        citation_text = " , ".join(citation_items)
        st.markdown(citation_text)
        logger.debug(f"Displayed {len(citation_items)} citations in comma-separated format")
    else:
        logger.debug("No citation items to display")


def generate_citation_html_for_processed_content() -> str:
    """
    Generate citation HTML for inclusion in processed content storage.
    
    This function creates the same citation display as display_post_completion_citations()
    but returns the HTML string instead of displaying it directly.
    
    Returns:
        str: Complete citation HTML including header and comma-separated citations
    """
    from modules.config.session_state import get_session_manager
    from modules.config.app_config import ENABLE_CITATIONS
    
    if not ENABLE_CITATIONS:
        return ""
    
    session_manager = get_session_manager()
    
    # Use same logic as display_post_completion_citations()
    thread_citations = session_manager.get_thread_citations()
    thread_tool_citations = session_manager.get_thread_tool_citations()
    request_citation_mapping = session_manager.get_request_citation_mapping()
    
    tool_result_citations = session_manager.get_tool_citations()
    citation_id_mapping = session_manager.tool_state.citation_id_mapping
    streaming_citations = session_manager.tool_state.streaming_citations
    
    citations = thread_citations if thread_citations else streaming_citations
    citation_mapping = request_citation_mapping if request_citation_mapping else citation_id_mapping
    effective_tool_citations = thread_tool_citations if thread_tool_citations else tool_result_citations
    
    if not (citation_mapping and effective_tool_citations):
        return ""
    
    # Build ordered citations (same logic as display function)
    ordered_citations = []
    for citation_number in sorted(citation_mapping.values()):
        citation_id = None
        for cid, cnum in citation_mapping.items():
            if cnum == citation_number:
                citation_id = cid
                break
        
        if citation_id and citation_id in effective_tool_citations:
            citation_data = effective_tool_citations[citation_id].copy()
            citation_data['citation_number'] = citation_number
            citation_data['citation_id'] = citation_id
            ordered_citations.append(citation_data)
    
    if not ordered_citations:
        return ""
    
    # Build citation items (same logic as display function)
    citation_items = []
    displayed_citation_ids = set()
    
    for citation in ordered_citations:
        if citation.get('doc_id') and citation.get('doc_title') and citation.get('id', '').startswith('cs_'):
            citation_id = citation.get('id')
            doc_title = citation.get('doc_title', 'Unknown')
            doc_id = citation.get('doc_id', '')
            citation_number = citation.get('citation_number', 0)
            
            if citation_id not in displayed_citation_ids:
                displayed_citation_ids.add(citation_id)
                
                if doc_id and (doc_id.startswith("http://") or doc_id.startswith("https://")):
                    citation_items.append(f"**[{citation_number}]**: [{doc_title}]({doc_id})")
                else:
                    citation_items.append(f"**[{citation_number}]**: {doc_title}")
    
    if citation_items:
        citation_text = " , ".join(citation_items)
        # Return complete HTML with header and citations using material icon
        return f"\n\n## :material/sticky_note_2: Citations\n\n{citation_text}\n\n"
    
    return ""


def _display_tool_result_citation(citation: dict, displayed_citations: Set[str], citation_number: int) -> None:
    """Display a tool result citation with complete data."""
    doc_id = citation.get('doc_id')
    doc_title = citation.get('doc_title') 
    citation_id = citation.get('id')
    
    if not doc_id or not doc_title:
        logger.warning("Invalid tool result citation", citation=citation)
        return
    
    citation_key = f"{citation_id}#{doc_title}"
    
    # Skip if already displayed
    if citation_key in displayed_citations:
        logger.debug(f"Skipping duplicate tool result citation: {doc_title}")
        return
    
    displayed_citations.add(citation_key)
    
    # Display citation with clean format - just [n]: link
    st.markdown(f"📎 **[{citation_number}]:** [{doc_title}]({doc_id})")
    
    # Remove citation text display for cleaner UI
    
    logger.debug(f"Displayed tool result citation [{citation_number}]: {doc_title}")


def _display_documentation_citation(citation: dict, displayed_citations: Set[str], citation_number: int) -> None:
    """Display a documentation citation as a clean hyperlink with number."""
    doc_id = citation.get('doc_id')
    doc_title = citation.get('doc_title')
    
    if not doc_id or not doc_title:
        logger.warning("Invalid documentation citation", citation=citation)
        return
    
    citation_key = f"{doc_id}#{doc_title}"
    
    if citation_key not in displayed_citations:
        st.markdown(f"**[{citation_number}]:** [{doc_title}]({doc_id})")
        displayed_citations.add(citation_key)
        
        logger.debug("Displayed documentation citation",
                    doc_id=doc_id,
                    doc_title=doc_title)
    else:
        logger.debug("Skipped duplicate documentation citation",
                    doc_id=doc_id,
                    doc_title=doc_title)


def _display_file_citation(citation: dict, displayed_citations: Set[str], citation_number: int) -> None:
    """Display a file citation with preview if possible."""
    file_path = citation.get('file_path')
    file_type = citation.get('file_type')
    citation_id = citation.get('citation_id')
    
    if not file_path or not file_type:
        logger.warning("Invalid file citation", citation=citation)
        return
    
    file_citation_key = f"file#{file_path}#{file_type}"
    
    if file_citation_key not in displayed_citations:
        # Try to display file with preview
        # Note: snowflake_client should be passed as parameter instead of using session state
        # For now, keeping this as is since it requires function signature changes
        snowflake_client = st.session_state.get('snowflake_client')
        
        if snowflake_client and hasattr(snowflake_client, 'session'):
            try:
                from modules.files.management import display_file_with_scrollbar
                session = snowflake_client.session
                
                st.markdown(f"### 📎 File [{citation_number}]")
                display_file_with_scrollbar(
                    relative_path=file_path,
                    session=session,
                    file_type=file_type,
                    citation_id=f"completion_{citation_id}"
                )
                
                logger.debug("Displayed file citation with preview",
                           file_path=file_path,
                           file_type=file_type)
                
            except Exception as e:
                logger.error("Error displaying file citation preview",
                           error=str(e),
                           file_path=file_path)
                # Fallback to simple citation
                st.markdown(f"**[{citation_number}]:** {file_path} ({file_type})")
        else:
            # No session available - show simple citation
            st.markdown(f"**[{citation_number}]:** {file_path} ({file_type})")
            logger.debug("Displayed simple file citation (no session)",
                       file_path=file_path,
                       file_type=file_type)
        
        displayed_citations.add(file_citation_key)
    else:
        logger.debug("Skipped duplicate file citation",
                    file_path=file_path,
                    file_type=file_type)


def count_unique_citations() -> int:
    """Count unique citations that would be displayed."""
    from modules.config.session_state import get_session_manager
    
    session_manager = get_session_manager()
    citations = session_manager.tool_state.streaming_citations
    displayed_citations: Set[str] = set()
    
    for citation in citations:
        citation_type = citation.get('citation_type')
        
        if citation_type == 'documentation':
            doc_id = citation.get('doc_id')
            doc_title = citation.get('doc_title')
            if doc_id and doc_title:
                citation_key = f"{doc_id}#{doc_title}"
                displayed_citations.add(citation_key)
                
        elif citation_type == 'file':
            file_path = citation.get('file_path')
            file_type = citation.get('file_type')
            if file_path and file_type:
                file_citation_key = f"file#{file_path}#{file_type}"
                displayed_citations.add(file_citation_key)
    
    return len(displayed_citations)


def has_citations_to_display() -> bool:
    """Check if there are any citations ready for display."""
    from modules.config.session_state import get_session_manager
    
    session_manager = get_session_manager()
    citations = session_manager.tool_state.streaming_citations
    tool_citations = session_manager.get_tool_citations()
    
    return len(citations) > 0 or len(tool_citations) > 0
