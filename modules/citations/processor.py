"""
Citation ID processing and text replacement utilities.

This module handles the transformation of raw citation IDs (like cs_xxx-xxx) 
and HTML cite tags into clean numbered citations ([1], [2], [3]) in agent
response text, providing a professional citation system.

Key Features:
- Multiple citation format detection (cs_ids, <cite> tags, raw IDs)
- Sequential numbering with session persistence across conversation
- Clickable citation links with hover tooltips  
- Real-time text processing during streaming responses
- Session state integration for cross-request citation continuity
- Smart buffering support for flicker-free citation replacement

Citation Processing Flow:
1. Text contains raw citation IDs or <cite>cs_xxx</cite> tags
2. Pattern matching identifies all citation formats in text
3. Session state provides persistent numbering across requests
4. Tool result data provides citation metadata (title, URL)
5. Citations are replaced with clickable numbered links: <a href="url">[1]</a>
6. Final text displays clean numbered citations for user

Supported Formats:
- <cite>cs_abc123-def456</cite> → [1] (primary format)
- cs_abc123-def456 → [1] (legacy fallback) 
- Raw citation IDs in streaming text

Usage:
    # Process text with citations during streaming
    clean_text = process_citation_ids_in_text(raw_agent_text)
    
    # Reset numbering for new conversation
    reset_citation_numbering()
"""

import re
from modules.logging import get_logger
from modules.config.session_state import get_session_manager

logger = get_logger()


def process_citation_ids_in_text(text: str) -> str:
    """
    Replace citation IDs like cs_xxx-xxx with numbered citations like [1], [2].
    
    Args:
        text: Input text potentially containing citation IDs
        
    Returns:
        Processed text with citation IDs replaced by numbered citations
        
    Example:
        Input: "Data loading cs_9ad954ee-8462-439b-9836-a8157b409510 methods"
        Output: "Data loading [1] methods"
    """
    # Get session manager for structured state access
    session_manager = get_session_manager()
    
    # Process citations using request-scoped tracking for thread integrity
    
    # Log current state when processing citations
    request_mapping = session_manager.get_request_citation_mapping()
    request_counter = session_manager.get_request_citation_counter()
    
    logger.debug(f"Processing citation text - Length: {len(text) if text else 0}, Request counter: {request_counter}, Request mapping: {len(request_mapping)}")
    
    # Look for cs_ citation IDs in text with multiple patterns
    import re
    
    # Pattern 1: Bare cs_ IDs
    cs_citations = re.findall(r'\b(cs_[a-f0-9-]+)\b', text)
    
    # Pattern 2: Any cs_ strings (more permissive) 
    all_cs_references = re.findall(r'(cs_[a-zA-Z0-9-]+)', text)
    
    # Pattern 3: HTML cite tags
    cite_tags = re.findall(r'<cite[^>]*>(.*?)</cite>', text)
    
    if cs_citations:
        logger.debug(f"Found CS citations (bare): {cs_citations}")
    if all_cs_references and all_cs_references != cs_citations:
        logger.debug(f"Found CS references (all): {all_cs_references}")
    if cite_tags:
        logger.debug(f"Found cite tags: {cite_tags}")
    
    if not cs_citations and not all_cs_references and not cite_tags:
        if text and len(text.strip()) > 10:
            logger.debug(f"No citations found in text: '{text[:100]}...')")
        else:
            logger.debug(f"Empty or short text: '{text}'")
    
    # Process cs_ citation IDs found in the text
    
    # Citation numbering logic is now handled inline below
    
    # Replace raw cs_ citation IDs with numbered citations
    import re
    processed_text = text
    
    # Handle <cite>cs_xxx</cite> HTML tags (the actual format used by Snowflake Cortex)
    cite_pattern = r'<cite>(cs_[a-f0-9-]+)</cite>'
    
    # Find all COMPLETE citations in order of appearance (don't use set to preserve order)
    cite_matches = re.findall(cite_pattern, processed_text)
    
    # Only log when we actually find complete citations (reduce noise)
    if cite_matches:
        logger.debug(f"Processing {len(cite_matches)} complete citations: {cite_matches[:3]}{'...' if len(cite_matches) > 3 else ''}")
    else:
        logger.debug(f"No cite tags found in text")
    
    if cite_matches:
        logger.debug(f"Found cite tags in order: {cite_matches}")
        
        # Process citations in order of appearance to maintain proper numbering
        # Use REQUEST-SCOPED citation tracking to match annotation processing
        for cs_id in cite_matches:
            # Use request-scoped citation mapping (consistent with annotation processing)
            request_mapping = session_manager.get_request_citation_mapping()
            if cs_id in request_mapping:
                # Use existing request-scoped number
                citation_num = request_mapping[cs_id]
                logger.debug(f"Reusing existing request-scoped number [{citation_num}] for {cs_id}")
            else:
                # New citation - assign using request-scoped counter
                citation_num = session_manager.increment_request_citation_counter()
                session_manager.set_request_citation_number(cs_id, citation_num)
                logger.debug(f"Assigned new request-scoped number [{citation_num}] for {cs_id}")
            
            # Get citation data using new session manager (should always be available since tool results come before text deltas)
            tool_result_citations = session_manager.get_tool_citations()
            citation_data = tool_result_citations.get(cs_id, {})
            
            if citation_data:
                doc_id = citation_data.get('doc_id', '#')
                doc_title = citation_data.get('doc_title', f'Citation {citation_num}')
                logger.debug(f"📎 Using citation data for [{citation_num}]: {doc_title}")
            else:
                # This should not happen since tool results come first, but fallback just in case
                doc_id = '#'
                doc_title = f'Citation {citation_num}'
                logger.warning(f"Missing tool result data for citation {cs_id}")
                logger.warning(f"Available citations: {list(tool_result_citations.keys())}")
                
                # Check if it's a partial match issue
                for stored_id in tool_result_citations.keys():
                    if cs_id in stored_id or stored_id in cs_id:
                        logger.warning(f"Possible ID mismatch: looking for '{cs_id}' but have '{stored_id}'")
            
            # Create clickable link with hover tooltip
            citation_link = f'<a href="{doc_id}" title="{doc_title}" target="_blank">[{citation_num}]</a>'
            
            # Replace the entire <cite>cs_xxx</cite> tag with clickable numbered citation
            full_cite_tag = f"<cite>{cs_id}</cite>"
            processed_text = processed_text.replace(full_cite_tag, citation_link)
            
            # Log the replacement
            logger.debug(f"Replaced: '{full_cite_tag}' -> '[{citation_num}]' (link to {doc_id}, title: '{doc_title}')")
    
    # Check for raw cs_ IDs (legacy format - shouldn't occur with new cite tag format)
    raw_cs_pattern = r'\b(cs_[a-f0-9-]+)\b'
    raw_cs_matches = re.findall(raw_cs_pattern, processed_text)
    if raw_cs_matches:
        logger.warning(f"Found unexpected raw CS IDs (should be in <cite> tags): {raw_cs_matches}")
        # Log but don't process - citations should come in <cite> tags
    
    # Check for existing numbered citations that might indicate format mismatch
    numbered_pattern = r'\[(\d+)\]'
    numbered_matches = re.findall(numbered_pattern, processed_text)
    if numbered_matches:
        logger.debug(f"Found numbered citations: {numbered_matches}")
    
    return processed_text


def get_citation_pattern() -> str:
    """Get the regex pattern used for matching citation IDs in cite tags."""
    return r'<cite>(cs_[a-f0-9-]+)</cite>'


def count_citations_in_text(text: str) -> int:
    """Count the number of citation IDs found in text (both cite tags and raw IDs)."""
    # Count cite tags
    cite_pattern = r'<cite>(cs_[a-f0-9-]+)</cite>'
    cite_matches = re.findall(cite_pattern, text)
    
    # Count raw citation IDs (for legacy support)
    raw_pattern = r'\b(cs_[a-f0-9-]+)\b'
    raw_matches = re.findall(raw_pattern, text)
    
    # Return total count (avoiding double counting)
    all_citations = set(cite_matches + raw_matches)
    return len(all_citations)


def get_or_assign_citation_number(search_result_id: str) -> int:
    """
    Get or assign a citation number for a search_result_id using request-scoped counters.
    
    Citations are numbered starting from [1] for each new request within a thread.
    This ensures clean citation numbering per request with proper thread integrity
    where each request maintains its own isolated citation namespace.
    
    Args:
        search_result_id: The exact citation ID from annotation events
        
    Returns:
        int: The citation number (1, 2, 3, etc.) - resets for each request
    """
    from modules.config.session_state import get_session_manager
    
    session_manager = get_session_manager()
    
    # Check request-scoped citation mapping first
    request_mapping = session_manager.get_request_citation_mapping()
    if search_result_id in request_mapping:
        return request_mapping[search_result_id]
    
    # Assign new citation number using request-scoped counter (starts at 1 for each request)
    citation_number = session_manager.increment_request_citation_counter()
    session_manager.set_request_citation_number(search_result_id, citation_number)
    
    logger.debug(f"Assigned new request citation number: {search_result_id} -> [{citation_number}]")
    return citation_number

def reset_citation_numbering() -> None:
    """
    Initialize citation numbering for a new request.
    
    Resets request-scoped citation counters to start at [1] for the new request.
    Each request within a thread maintains its own isolated citation namespace
    to ensure proper thread integrity and prevent cross-request interference.
    """
    import time
    from modules.config.session_state import get_session_manager
    
    session_manager = get_session_manager()
    
    # Generate unique response ID for this citation set
    response_id = f"resp_{int(time.time() * 1000)}"
    session_manager.response_state.current_response_id = response_id
    
    logger.debug(f"Starting new request citations - ID: {response_id}")
    
    # Reset request-scoped citation state (counters restart at 1)
    session_manager.reset_request_citations()
    
    logger.debug(f"Initialized request-specific citations - Response: {response_id}")
    logger.debug("Citation counters reset to start at [1] for new request")
