"""
Cortex API integration and streaming utilities.

This module provides integration with Snowflake Cortex Agents API including:
- Agent run requests with real-time streaming
- Stream event processing and real-time updates
- Request body construction and authentication
- Streamlit UI updates and event handling

Key Features:
- Real-time streaming response processing
- Complete event type handling (status, text, thinking, tools, charts)
- Authentication token management (PAT/JWT)
- Debug mode support with consolidated API response tracking
- Streamlit session state integration
"""
import json
import requests
import streamlit as st
import pandas as pd
import sseclient
from typing import Optional
from collections import defaultdict

from modules.logging import get_logger, log_performance, log_api_call
from modules.config.session_state import get_session_manager
from modules.citations import (
    process_citation_ids_in_text,
    reset_citation_numbering,
    display_post_completion_citations,
    handle_streaming_citation
)
# Removed: get_or_assign_citation_number - no longer needed with new cite tag system
from modules.authentication.token_provider import get_auth_token_for_agents
from modules.authentication.token_provider import connection, oauth_connection
from modules.authentication.okta_oauth import get_oauth_provider, is_oauth_enabled
# Removed circular import - get_thread_messages will be passed as parameter or imported locally
from modules.models.messages import TextContentItem, MessageContentItem, Message, DataAgentRunRequest
from modules.models.events import (
    StatusEventData, TextDeltaEventData, ThinkingDeltaEventData,
    ToolUseEventData, ToolResultEventData, TableEventData, ChartEventData, ErrorEventData
)

# Module-level logger for helper functions
logger = get_logger()

def get_login_token():
    """
    Read the login token supplied automatically by Snowflake. These tokens
    are short lived and should always be read right before creating any new connection.
    """
    with open("/snowflake/session/token", "r") as f:
        return f.read()

@log_performance("agent_streaming")
@log_api_call("cortex_agent_run", "POST")
def agent_run_streaming(thread_id: str, user_message: str, snowflake_config, snowflake_client) -> Optional[requests.Response]:
    """
    Execute an agent run with real-time streaming response processing.
    
    This function handles the complete lifecycle of sending a user message to a Snowflake
    Cortex Agent and setting up the streaming response. It manages authentication,
    request construction, and thread management according to Snowflake API specifications.
    
    Args:
        thread_id (str): Unique identifier for the conversation thread
        user_message (str): User's message to send to the agent
        snowflake_config: SnowflakeConfig instance containing authentication details
        snowflake_client: ExternalSnowflakeClient instance for JWT token generation
        
    Returns:
        Optional[requests.Response]: Streaming response object if successful, None if failed
        
    Raises:
        Logs errors internally and displays user-friendly error messages via Streamlit
    """
    
    try:
        # Get session manager and check if an agent is selected
        session_manager = get_session_manager()
        if not session_manager.has_selected_agent():
            st.error(":material/error: No agent selected. Please select an agent from the sidebar.")
            return None
        
        selected_agent = session_manager.get_selected_agent()
        
        logger.info(
            "Starting agent streaming request",
            thread_id=thread_id,
            agent_name=selected_agent['name'],
            agent_database=selected_agent['database'],
            agent_schema=selected_agent['schema'],
            message_length=len(user_message)
        )


        # Check authentication methods in priority order
        auth_token = None
        auth_method = None
        headers = None
        
        # Priority 1: Okta OAuth
        if is_oauth_enabled():
            oauth_provider = get_oauth_provider()
            if oauth_provider and oauth_provider.is_authenticated():
                oauth_token = oauth_provider.get_access_token()
                if oauth_token:
                    try:
                        session, headers = oauth_connection(oauth_token, snowflake_config)
                        auth_method = "OKTA_OAUTH"
                        logger.info("Using Okta OAuth for agent request")
                    except Exception as e:
                        logger.error(f"Okta OAuth connection failed: {e}")
                        st.error(f"OAuth connection failed. Please try logging out and back in.")
                        return None
        
        # Priority 2: SPCS Token (if running in Snowflake)
        if not auth_method:
            try:
                session, headers = connection(get_login_token())
                auth_method = "SPCS_TOKEN"
            except Exception as e:
                logger.debug("SPCS token not available", error=str(e))
        
        # Priority 3: OAuth token set directly in config
        if not auth_method and snowflake_config.oauth_token:
            try:
                session, headers = oauth_connection(snowflake_config.oauth_token, snowflake_config)
                auth_method = "OAUTH_TOKEN"
                logger.info("Using OAuth token from config")
            except Exception as e:
                logger.error(f"OAuth token connection failed: {e}")
        
        # Priority 4: PAT or RSA authentication
        if not auth_method:
            if snowflake_config.pat:
                auth_token = snowflake_config.pat
                auth_method = "PAT"
            elif snowflake_config.private_key:
                auth_token = get_auth_token_for_agents(snowflake_config, snowflake_client)
                auth_method = "RSA_JWT"
            else:
                logger.error("No authentication token available")
                st.error("No authentication token available. Please configure authentication.")
                return None
            
        logger.debug(
            "Authentication configured",
            auth_method=auth_method,
            token_length=len(auth_token) if auth_token else 0
        )
        
        # Use agent's configured model
        model = selected_agent.get('models', {}).get('orchestration', 'claude-4-sonnet')
        if model == "auto":  # Handle "auto" in agent spec
            model = "claude-4-sonnet"  # fallback
        
        # Build URL for agent API using selected agent details
        agent_database = selected_agent['database']
        agent_schema = selected_agent['schema'] 
        agent_name = selected_agent['name']
        url = f"https://{snowflake_config.account}.snowflakecomputing.com/api/v2/databases/{agent_database}/schemas/{agent_schema}/agents/{agent_name}:run"
        
        # Get recent messages from thread to determine parent_message_id
        # Import locally to avoid circular dependency
        from modules.threads.management import get_thread_messages
        thread_response = get_thread_messages(thread_id, snowflake_config, snowflake_client, page_size=10)
        
        # Determine parent_message_id according to Snowflake docs:
        # - Initial parent_message_id should be 0 (first message in thread)
        # - For subsequent messages, use the message_id of the last ASSISTANT message
        parent_message_id = 0  # Default for first message
        if thread_response and thread_response.messages:
            # Find the most recent assistant message ID to use as parent
            # Snowflake API returns messages in newest-first order, so first assistant = most recent
            for thread_message in thread_response.messages:
                if thread_message.role == "assistant":
                    parent_message_id = thread_message.message_id
                    break
            # If no assistant message found, keep parent_message_id = 0
        
        # Build request body using structured models
        # Note: When using threads, include only the current user message in messages array
        # Historical context is managed automatically by Snowflake via thread_id/parent_message_id
        
        # Create user message using proper models
        user_text_content = TextContentItem(type="text", text=user_message)
        user_content_item = MessageContentItem(actual_instance=user_text_content)
        user_message_obj = Message(role="user", content=[user_content_item])
        
        # Create the main request using DataAgentRunRequest model
        agent_request = DataAgentRunRequest(model=model, messages=[user_message_obj])
        
        # Convert to dict and add thread-specific fields
        request_body = json.loads(agent_request.to_json())
        request_body["models"] = {"orchestration": model}  # Thread API expects nested models structure
        request_body["thread_id"] = int(thread_id)
        request_body["parent_message_id"] = parent_message_id
        
        logger.info(
            "Request body constructed",
            model=model,
            thread_id=thread_id,
            parent_message_id=parent_message_id,
            request_url=url,
            body_size_bytes=len(json.dumps(request_body))
        )
        
        if session_manager.is_debug_mode():
            # Store request body for consolidated JSON export
            session_manager.debug_state.debug_request_body = request_body
        
        # Make streaming request using requests library (like official demo)
        # Build headers based on authentication method
        if auth_method in ["OKTA_OAUTH", "SPCS_TOKEN", "OAUTH_TOKEN"]:
            # Headers already set from connection function with Snowflake token
            logger.debug(f"Using {auth_method} authentication with session token")
        else:
            # Build headers with bearer token for PAT/RSA
            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
                "User-Agent": "CortexAgentDemo/1.0",
            }
        resp = requests.post(
            url=url,
            data=json.dumps(request_body),
            headers=headers,
            stream=True,  # Enable streaming
            verify=snowflake_config.ssl_verify,  # Use configurable SSL verification
            timeout=60
        )
        
        if resp.status_code < 400:
            logger.info(
                "Agent streaming request successful",
                status_code=resp.status_code,
                content_type=resp.headers.get('content-type'),
                thread_id=thread_id,
                agent_name=selected_agent['name']
            )
            return resp
        else:
            logger.error(
                "Agent API request failed",
                status_code=resp.status_code,
                response_text=resp.text[:500],  # Limit response text length
                thread_id=thread_id,
                agent_name=selected_agent['name'],
                url=url
            )
            st.error(f":material/error: Agent API Error: HTTP {resp.status_code}")
            st.error(f"Details: {resp.text}")
            return None
            
    except Exception as e:
        logger.error(
            "Exception in agent streaming",
            error=str(e),
            error_type=type(e).__name__,
            thread_id=thread_id,
            agent_name=selected_agent.get('name', 'unknown') if 'selected_agent' in locals() else 'unknown'
        )
        st.error(f":material/error: Error in agent_run_streaming: {str(e)}")
        return None

def stream_events_realtime(response: requests.Response, debug_mode: bool = False) -> str:
    """
    Process real-time streaming events from Snowflake Cortex Agents API.
    
    This function handles the complete event stream processing for agent responses,
    including status updates, thinking phases, tool executions, and content generation.
    It provides real-time UI updates through Streamlit and manages citation processing.
    
    IMPORTANT: Content is now scoped by (request_id, content_index) to prevent
    cross-request interference. Each request maintains its own content namespace.
    
    Event Types Handled:
    - response.status: Agent orchestration status updates
    - response.thinking.delta: Incremental agent reasoning display
    - response.text.delta: Streaming text response content
    - response.text.annotation: Citation and metadata annotations
    - response.tool_use: Tool invocation notifications
    - response.tool_result: Tool execution results with embedded data
    - response.table: Structured tabular data for display
    - response.chart: Vega-Lite chart specifications
    - response.done: Stream completion signal
    - error: Error conditions and failures
    
    Args:
        response: HTTP response object with SSE streaming enabled
        debug_mode: Enable comprehensive event logging and consolidated API response tracking
        
    Returns:
        Final processed message text with citations processed
        
    Raises:
        Handles all exceptions internally with graceful error display
    """
    # Initialize core state management and validation
    session_manager = get_session_manager()
    
    if not response:
        return ""
    
    # Extract request_id from response headers for content scoping
    current_request_id = response.headers.get('X-Snowflake-Request-Id', 'unknown')
    logger.info(f"Processing request with ID: {current_request_id}")
    
    # Synchronize session state with response header request ID for content retrieval
    session_manager.response_state.current_response_id = current_request_id
    
    if debug_mode:
        logger.info("Debug mode active: Enhanced event tracking enabled", request_id=current_request_id)
    else:
        logger.info("Debug mode inactive: Standard processing mode", request_id=current_request_id)
    
    # Reset citation numbering for this new response - citations should start at [1]
    reset_citation_numbering()
    
    # Initialize debug tracking for comprehensive API response analysis
    consolidated_api_response = {
        "response_metadata": {
            "headers": dict(response.headers),
            "status_code": response.status_code,
            "url": str(response.url),
            "encoding": response.encoding
        },
        "events": [],
        "event_summary": {
            "total_events": 0,
            "event_types": {}
        }
    } if debug_mode else None
    
    # Event tracking for debug analysis
    all_events = []  # Complete event log for debugging
    event_types = {}  # Event type frequency counter
        
    # === STREAMLIT UI INITIALIZATION ===
    content = st.container()
    # REQUEST-SCOPED CONTENT MANAGEMENT
    # Use (request_id, content_index) as keys to prevent cross-request interference
    # CRITICAL: Make content_map persistent across requests within the same session
    if 'streaming_content_map' not in st.session_state:
        st.session_state.streaming_content_map = {}
    content_map = st.session_state.streaming_content_map
    
    def get_content_container(key):
        """Get or create a unique content placeholder for each (request_id, content_index) key."""
        if key not in content_map:
            content_map[key] = content.empty()  # Use empty() not container() - empty() gets replaced, container() appends
        return content_map[key]
    
    # Single status container for the entire request lifecycle
    single_status_container = content.status(
        ":material/refresh: Processing request...", 
        expanded=True, 
        state="running"
    )
    
    # === STATE TRACKING VARIABLES ===
    current_status_label = ":material/refresh: Processing request..."  # Avoid redundant status updates
    thinking_status_set = False  # Track if thinking phase has been displayed
    status_collapsed_on_response = False  # Auto-collapse status when response streams
    
    # === REQUEST-SCOPED CONTENT BUFFERS AND PLACEHOLDERS ===
    # All content management now uses (request_id, content_index) keys
    buffers = defaultdict(str)  # (request_id, content_index) -> accumulated text mapping
    final_agent_reasoning = ""  # Store complete agent reasoning for final display
    thinking_placeholders = {}  # (request_id, content_index) -> thinking displays mapping
    
    # === AGENT RE-EVALUATION TRACKING (REQUEST-SCOPED) ===
    agent_is_reevaluating = False      # Track agent reevaluation state
    highest_content_index = -1         # Highest content index seen for current request
    active_content_indices = set()     # Active content indices for current request only
    

    # === DATA COLLECTION CONTAINERS ===
    bot_text_message = ""              # Final accumulated message text
    search_results = []                # Cortex Search results 
    sql_queries = []                   # Generated SQL queries from tools
    suggestions = []                   # Agent suggestions
    df_sql = pd.DataFrame([])          # SQL result DataFrames
    citations = []                     # Cortex Search citations for display
    charts = []                        # Chart specifications for visualization
    
    # === UI SPINNER MANAGEMENT ===
    # Skip bottom spinners - user already has top-level progress indicator
    spinner = None
    spinner_active = False
    
    try:
        # === MAIN EVENT PROCESSING LOOP ===
        events = sseclient.SSEClient(response).events()
        
        for event in events:
            # ⭐ CRITICAL DEBUG: Log every single event being processed  
            logger.debug(f"🌟 RAW SSE EVENT: type='{event.event}', data_preview='{str(event.data)[:100]}...'")
            
            # Parse event data with error handling
            try:
                event_data = json.loads(event.data) if event.data else {}
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse event data: {event.data}")
                continue
            
            # === EVENT TYPE TRACKING (always needed for logging) ===
            event_type = event.event or "unknown"
            
            # === DEBUG MODE EVENT TRACKING ===
            if debug_mode:
                event_summary = {
                    "event_number": len(all_events) + 1,
                    "event_type": event_type,
                    "event_id": getattr(event, 'id', None),
                    "retry": getattr(event, 'retry', None),
                    "data": event_data,
                    "raw_data": event.data
                }
                all_events.append(event_summary)
                consolidated_api_response["events"].append(event_summary)
                
                # Count event types
                event_types[event_type] = event_types.get(event_type, 0) + 1
                
            # Log all event types for debugging
            logger.debug("Received event", event_type=event.event, has_data=bool(event_data))
            
            # DEBUG: Log all events to see what's actually coming through
            if debug_mode:
                logger.debug(f"Event received: {event.event} - {str(event_data)[:200]}...")
            
            # DEBUG: Log the actual event being matched
            logger.debug(f"Matching on: '{event.event}' (event_type variable: '{event_type}')")
            
            match event.event:
                case "response":
                    # Basic response event - may contain general response data
                    # Just log for now, actual content usually comes in specific events
                    if debug_mode:
                        logger.debug("Received basic response event", event_data=event_data)
                
                case "response.status":
                    # Skip intermediate status spinners - we already have top-level progress indicator
                    data = StatusEventData.from_json(event_data)
                    status_type = event_data.get("status", "")
                    
                    # Detect agent re-evaluation to prepare for content clearing
                    if status_type == "reevaluating_plan":
                        agent_is_reevaluating = True
                        logger.debug("Agent re-evaluation detected - will clear old content when new content_index appears")
                    
                    logger.debug(f"API Status: {data.message} (status: {status_type}) (not displayed to avoid duplicate progress indicators)")
                    # Note: Keeping spinner_active state unchanged to avoid breaking other logic
                    
                case "response.text.delta":
                    data = TextDeltaEventData.from_json(event_data)
                    
                    # Create request-scoped content key
                    content_key = (current_request_id, data.content_index)
                    
                    # Clear old content when agent starts streaming improved response
                    # CRITICAL FIX: Only clear content for the CURRENT request, not previous requests
                    if agent_is_reevaluating and data.content_index > highest_content_index:
                        logger.debug(f"Clearing old content indices {list(active_content_indices)} for request {current_request_id}, starting fresh with content_index {data.content_index}")
                        
                        # Clear all previous content containers FOR THIS REQUEST ONLY
                        for old_content_idx in active_content_indices:
                            old_content_key = (current_request_id, old_content_idx)
                            get_content_container(old_content_key).empty()
                            if old_content_key in buffers:
                                buffers[old_content_key] = ""
                            if old_content_key in thinking_placeholders:
                                thinking_placeholders[old_content_key].empty()
                                del thinking_placeholders[old_content_key]
                        
                        # Reset tracking for new response (current request only)
                        active_content_indices.clear()
                        bot_text_message = ""
                        agent_is_reevaluating = False
                        
                        logger.debug(f"Content cleared for request {current_request_id}, ready for improved response with content_index {data.content_index}")
                    
                    # Track content indices and update highest seen (for current request)
                    highest_content_index = max(highest_content_index, data.content_index)
                    active_content_indices.add(data.content_index)
                    
                    # Add raw text to request-scoped buffers and accumulator
                    buffers[content_key] += data.text
                    bot_text_message += data.text  # Accumulate raw text for return
                    
                    # SMART BUFFERING: Show raw text during streaming, process citations at completion
                    # This eliminates flickering by avoiding citation processing during streaming
                    buffer_text = buffers[content_key]
                    
                    # Show raw text immediately for fast streaming
                    logger.debug(f"Streaming text chunk (length: {len(data.text)}) for request {current_request_id}, content_index {data.content_index}")
                    
                    # Check for table reference patterns in raw text
                    _detect_and_handle_table_references(data.text)
                    
                    # Display raw text without citation processing for smooth streaming
                    get_content_container(content_key).markdown(buffer_text, unsafe_allow_html=True)
                    
                    # Collapse status container on first response text delta - user can now focus on the answer
                    if not status_collapsed_on_response:
                        single_status_container.update(
                            label=":material/check_circle: Processing complete - delivering response", 
                            state="complete",
                            expanded=False  # Collapse the status now that we're streaming the final answer
                        )
                        status_collapsed_on_response = True
                
                case "response.text.annotation":
                    # Text annotations (citations, references, etc.)
                    content_idx = event_data.get("content_index", 0)
                    annotation_data = event_data.get("annotation", {})
                    annotation_index = event_data.get("annotation_index", 0)
                    
                    # Log annotation processing
                    logger.debug(f"Annotation event - Content idx: {content_idx}, Annotation idx: {annotation_index}")
                    logger.debug(f"Annotation data: doc_title={annotation_data.get('doc_title')}, search_result_id={annotation_data.get('search_result_id')}")
                    
                    # Store for later processing
                    citations.append(annotation_data)
                    
                    # PROCESS ANNOTATION EVENTS - This is how Snowflake sends citation data!
                    # Each annotation provides citation data that should be numbered and displayed
                    search_result_id = annotation_data.get('search_result_id')
                    doc_title = annotation_data.get('doc_title')
                    doc_id = annotation_data.get('doc_id')
                    
                    if search_result_id and doc_title and search_result_id.startswith('cs_'):
                        # Store citation data for display
                        citation_data = {
                            'id': search_result_id,
                            'doc_id': doc_id,
                            'doc_title': doc_title,
                            'content_index': content_idx,
                            'annotation_index': annotation_index,
                            'text': annotation_data.get('text', ''),
                            'type': annotation_data.get('type', 'cortex_search_citation')
                        }
                        
                        # Store in both legacy and thread-based storage
                        session_manager.add_tool_citation(search_result_id, citation_data)
                        session_manager.add_thread_tool_citation(search_result_id, citation_data)
                        
                        # Create citation mapping (assign citation number)
                        from modules.citations.processor import get_or_assign_citation_number
                        citation_number = get_or_assign_citation_number(search_result_id)
                        
                        logger.debug(f"Processed annotation citation: {search_result_id} -> [{citation_number}] {doc_title}")
                    else:
                        logger.debug(f"Skipped annotation: Invalid citation data - {search_result_id}")
                    
                    # Also call the streaming citation handler for compatibility
                    handle_streaming_citation(annotation_data, content_idx, debug_mode)
                    
                case "response.text":
                    # Consolidated text response (non-streaming) - only capture in debug mode
                    # We use response.text.delta for streaming, so this is redundant for our use case
                    if debug_mode:
                        logger.debug("Response text event (consolidated, non-streaming)", event_data=event_data)
                        # Store in consolidated debug data for debug interface
                        if consolidated_api_response and "consolidated_text_events" not in consolidated_api_response:
                            consolidated_api_response["consolidated_text_events"] = []
                        if consolidated_api_response:
                            consolidated_api_response["consolidated_text_events"].append(event_data)
                    else:
                        # Ignore consolidated text events - we use streaming text deltas instead
                        logger.debug("Ignoring response.text - using streaming deltas instead, debug mode disabled")
                    
                case "response.thinking.delta":
                    data = ThinkingDeltaEventData.from_json(event_data)
                    # Use request-scoped content key for thinking content
                    thinking_key = (current_request_id, data.content_index)
                    buffers[thinking_key] += data.text
                    
                    # Update THE SINGLE status container to show thinking phase (only once)
                    if not thinking_status_set:
                        single_status_container.update(
                            label=":material/neurology: Agent is thinking...", 
                            state="running", 
                            expanded=True
                        )
                        current_status_label = ":material/neurology: Agent is thinking..."
                        thinking_status_set = True
                    
                    # Create thinking display area within status container for this content index if it doesn't exist
                    if thinking_key not in thinking_placeholders:
                        with single_status_container:
                            st.markdown(f"**:material/neurology: Agent Reasoning:**")
                            thinking_placeholders[thinking_key] = st.empty()
                    
                    # Update the thinking content in real-time for this specific reasoning step
                    if thinking_key in thinking_placeholders:
                        thinking_content = buffers.get(thinking_key, "")
                        if thinking_content:
                            thinking_placeholders[thinking_key].markdown(thinking_content)
                    
                case "response.thinking":
                    # Thinking done for this step
                    content_idx = event_data.get("content_index", 0)
                    thinking_text = event_data.get("text", "")
                    
                    # Store final thinking for display in completed status
                    final_thinking = thinking_text if thinking_text else buffers.get(content_idx, "")
                    if final_thinking:
                        final_agent_reasoning = final_thinking
                    
                    # DON'T display the thinking here - it's already been displayed via thinking.delta
                    # The thinking.delta events already show the content in real-time
                    
                    # Show intermediate state: thinking complete, preparing for action
                    new_label = ":material/check_circle: Thinking complete, selecting tools..."
                    single_status_container.update(
                        label=new_label, 
                        state="running",  # Keep running - tools might follow thinking
                        expanded=True
                    )
                    current_status_label = new_label
                    
                case "response.tool_use":
                    data = ToolUseEventData.from_json(event_data)
                    tool_name = event_data.get("name", "Unknown Tool")
                    tool_input = event_data.get("input", {})
                    # Extract meaningful context from tool input for user visibility
                    tool_context = ""
                    if tool_input:
                        query_text = tool_input.get("query", "")
                        sql_query = tool_input.get("sql", "")
                        reference_vqrs = tool_input.get("reference_vqrs", [])
                        
                        if query_text:
                            # Show a brief version of what's being queried
                            short_query = query_text[:100] + "..." if len(query_text) > 100 else query_text
                            tool_context = f" - {short_query}"
                        elif sql_query:
                            # Show a brief version of the SQL query being executed
                            short_sql = sql_query[:100] + "..." if len(sql_query) > 100 else sql_query
                            tool_context = f" - {short_sql}"
                        elif reference_vqrs:
                            # Show a brief version of the first reference SQL query
                            for vqr in reference_vqrs:
                                if isinstance(vqr, dict) and "sql" in vqr:
                                    short_sql = vqr["sql"][:100] + "..." if len(vqr["sql"]) > 100 else vqr["sql"]
                                    tool_context = f" - {short_sql}"
                                    break
                        elif tool_input.get("search_term"):
                            search_term = tool_input.get("search_term", "")[:50]
                            tool_context = f" - Searching: {search_term}"
                    
                    # Update the status container immediately with the new label
                    new_label = f":material/build: Using Tool: {tool_name}{tool_context}"
                    current_status_label = new_label
                    single_status_container.update(
                        label=new_label, 
                        state="running", 
                        expanded=True
                    )
                    
                    # Now show the detailed content
                    _handle_tool_use_event(data, event_data, single_status_container, current_status_label, debug_mode)
                    
                case "response.tool_result":
                    logger.debug(f"Tool result event received: {event_type}")
                    
                    data = ToolResultEventData.from_json(event_data)
                    
                    # Log tool result data in debug mode
                    if debug_mode:
                        logger.debug(f"Tool result event data: {event_data}")
                    
                    # Analyze data structure for content extraction
                    logger.debug(f"Tool result data object: {data}")
                    logger.debug(f"Data type: {type(data)}")
                    logger.debug(f"Has content attribute: {hasattr(data, 'content')}")
                    
                    if hasattr(data, 'content'):
                        logger.debug(f"Data content: {data.content}")
                        logger.debug(f"Content type: {type(data.content)}")
                    
                    # Extract and store citation data from tool results
                    # Access content from raw event_data for complete structure
                    raw_data = event_data.get('data', {})
                    content_array = raw_data.get('content', [])
                    logger.debug(f"Processing {len(content_array)} content items from tool result")
                    
                    # Check for text and SQL in JSON content for display
                    tool_text = None
                    tool_sql = None
                    
                    for content_item in content_array:
                        logger.debug(f"Content item type: {type(content_item)}, data: {content_item}")
                        
                        if isinstance(content_item, dict):
                            # Extract text and SQL from JSON content for display
                            if content_item.get('type') == 'json' and 'json' in content_item:
                                json_content = content_item['json']
                                if 'text' in json_content:
                                    tool_text = json_content['text']
                                if 'sql' in json_content:
                                    tool_sql = json_content['sql']
                            
                            # Check if this content item contains citation data
                            doc_id = content_item.get('doc_id')
                            doc_title = content_item.get('doc_title') 
                            citation_id = content_item.get('id', '')
                            
                            logger.debug(f"Citation fields: doc_id='{doc_id}', doc_title='{doc_title}', id='{citation_id}'")
                            
                            if doc_id and doc_title and citation_id.startswith('cs_'):
                                # Store essential citation data for display
                                # Store only necessary fields to optimize memory usage
                                citation_data = {
                                    'id': citation_id,
                                    'doc_id': doc_id,
                                    'doc_title': doc_title,
                                    'source_id': content_item.get('source_id', 0)
                                }
                                
                                # Store in both legacy and thread-based storage
                                session_manager.add_tool_citation(citation_id, citation_data)
                                session_manager.add_thread_tool_citation(citation_id, citation_data)
                                
                                logger.debug(f"Stored tool result citation: {citation_id} -> {doc_title}")
                            else:
                                logger.debug("Not a citation - missing required fields or wrong format")
                        else:
                            logger.debug("Not a dict - skipping content item")
                    
                    # Display text and SQL if found
                    logger.debug(f"Tool result extracted text: {tool_text[:100] if tool_text else None}")
                    logger.debug(f"Tool result extracted SQL length: {len(tool_sql) if tool_sql else 0}")
                    
                    if tool_text or tool_sql:
                        with st.status("Tool Result", expanded=True):
                            if tool_text:
                                st.write(tool_text)
                            if tool_sql:
                                st.code(tool_sql, language="sql")
                    else:
                        logger.debug("Tool result - No text or SQL found to display")
                    
                    logger.debug(f"Tool result - Total stored citations: {len(session_manager.get_tool_citations())}")
                    
                    # Store complete tool result in thread-based session state for later reference
                    # This allows subsequent requests in the conversation to access previous tool results
                    tool_use_id = event_data.get("tool_use_id")
                    if tool_use_id:
                        # Store the complete tool result data per API docs
                        complete_tool_result = {
                            "content_index": event_data.get("content_index", 0),
                            "tool_use_id": tool_use_id,
                            "type": event_data.get("type", "unknown"),
                            "name": event_data.get("name", "unknown"),
                            "content": event_data.get("content", []),
                            "status": event_data.get("status", "unknown"),
                            "timestamp": __import__('time').time()  # Add timestamp for debugging
                        }
                        
                        # Store in thread-based storage for conversation persistence
                        session_manager.add_thread_tool_result(tool_use_id, complete_tool_result)
                        logger.debug(f"Stored complete tool result: {tool_use_id} ({complete_tool_result['type']}) in thread storage")
                    else:
                        logger.warning("Tool result missing tool_use_id - cannot store for later reference")
                    
                    # Note: No post-processing needed since tool results always come before text deltas
                    
                    # Handle tool completion and get updated status
                    tool_name = event_data.get("name", "Unknown Tool")
                    tool_status = event_data.get("status", "unknown")
                    
                    # Update status to show tool completion
                    if tool_status.lower() == "error":
                        new_label = f":material/error: Tool Failed: {tool_name}"
                        single_status_container.update(
                            label=new_label, 
                            state="error", 
                            expanded=True
                        )
                    else:
                        new_label = f":material/check_circle: Tool Complete: {tool_name}"
                        single_status_container.update(
                            label=new_label, 
                            state="running", 
                            expanded=True
                        )
                    
                    current_status_label = new_label
                    
                    # Show detailed tool result content
                    _handle_tool_result_event(data, event_data, single_status_container, current_status_label, debug_mode)
                
                case "response.tool_result.status":
                    # Specific tool execution status updates
                    # Per API docs: status events use 'tool_type' field, not 'name'
                    tool_type = event_data.get("tool_type", "Unknown Tool")
                    status = event_data.get("status", "unknown") 
                    message = event_data.get("message", "")  # More descriptive status message
                    
                    if status == "success":
                        new_label = f":material/check_circle: Tool Success: {tool_type}"
                    elif status == "error":
                        new_label = f":material/error: Tool Error: {tool_type}"
                    else:
                        # Use the descriptive message if available, otherwise use status
                        status_text = message if message else status
                        new_label = f":material/info: {tool_type}: {status_text}"
                    
                    single_status_container.update(
                        label=new_label,
                        state="running" if status != "error" else "error",
                        expanded=True
                    )
                
                case "response.tool_result.analyst.delta":
                    # Incremental analyst tool results
                    content_idx = event_data.get("content_index", 0)
                    analyst_key = (current_request_id, content_idx)
                    delta_content = event_data.get("delta", "")
                    if delta_content:
                        buffers[analyst_key] += delta_content
                        content_map[analyst_key].markdown(buffers[analyst_key], unsafe_allow_html=True)
                
                case "response.tool_result.sql_explanation.delta":
                    # Incremental SQL explanation updates
                    content_idx = event_data.get("content_index", 0)
                    explanation_key = (current_request_id, content_idx)
                    explanation_delta = event_data.get("delta", "")
                    if explanation_delta:
                        # Display SQL explanations in a special format within status
                        with single_status_container:
                            st.markdown("**:material/info: SQL Explanation:**")
                            if explanation_key not in buffers:
                                buffers[explanation_key] = ""
                            buffers[explanation_key] += explanation_delta
                            st.code(buffers[explanation_key], language="text")
                    
                case "response.table":
                    data = TableEventData.from_json(event_data)
                    logger.debug("Table event received", 
                              content_index=getattr(data, 'content_index', 0),
                              rows=len(data.result_set.data) if hasattr(data, 'result_set') and hasattr(data.result_set, 'data') else 0,
                              columns=len(data.result_set.result_set_meta_data.row_type) if hasattr(data, 'result_set') and hasattr(data.result_set, 'result_set_meta_data') and hasattr(data.result_set.result_set_meta_data, 'row_type') else 0)
                    _handle_table_event(data, get_content_container, current_request_id)
                    
                case "response.chart":
                    data = ChartEventData.from_json(event_data)
                    logger.debug("Chart event received", 
                              content_index=getattr(data, 'content_index', 0),
                              chart_spec_length=len(getattr(data, 'chart_spec', '')) if hasattr(data, 'chart_spec') else 0)
                    _handle_chart_event(data, get_content_container, charts, current_request_id)
                    
                case "response.error":
                    data = ErrorEventData.from_json(event_data)
                    _handle_error_event(data, single_status_container)
                
                case "error":
                    # Top-level error event (not response.error)
                    error_message = event_data.get("message", "Unknown error occurred")
                    error_code = event_data.get("code", "")
                    
                    single_status_container.update(
                        label=f":material/error: Error: {error_code}" if error_code else ":material/error: Request failed",
                        state="error",
                        expanded=True
                    )
                    
                    with single_status_container:
                        st.error(f":material/error: {error_message}")
                        if error_code:
                            st.code(f"Error Code: {error_code}")
                    
                    # Stop processing on top-level error
                    break
                    
                case "execution_trace":
                    # Execution trace events - only capture and log in debug mode
                    if debug_mode:
                        logger.debug("Execution trace event", event_data=event_data)
                        # Store in consolidated debug data for debug interface
                        if consolidated_api_response and "execution_traces" not in consolidated_api_response:
                            consolidated_api_response["execution_traces"] = []
                        if consolidated_api_response:
                            consolidated_api_response["execution_traces"].append(event_data)
                    else:
                        # Completely ignore execution_trace events when not in debug mode
                        logger.debug("Skipping execution trace - debug mode disabled")
                    
                case "metadata":
                    # Metadata events contain message information including message_id
                    metadata = event_data.get("metadata", {})
                    message_id = metadata.get("message_id")
                    parent_id = metadata.get("parent_id") 
                    thread_id = metadata.get("thread_id")
                    
                    logger.debug(f"📋 METADATA EVENT - Message ID: {message_id}, Parent ID: {parent_id}, Thread ID: {thread_id}")
                    
                    # Store message ID in session state for the current assistant message
                    if message_id:
                        session_manager.response_state.current_assistant_message_id = message_id
                        logger.debug(f"Captured assistant message ID from API: {message_id}")
                
                case "response.done":
                    if spinner_active and spinner:
                        spinner.__exit__(None, None, None)
                        spinner_active = False
                    
                    # SMART BUFFERING: Now process citations for final display (current request only)
                    logger.debug(f"Completion: Processing citations for final display (request {current_request_id})")
                    for content_key, buffer_content in buffers.items():
                        # Only process content for the current request
                        if (isinstance(content_key, tuple) and content_key[0] == current_request_id and 
                            buffer_content and ('cs_' in buffer_content or '<cite>' in buffer_content)):
                            logger.debug(f"Completion: Processing citations for content_key {content_key}")
                            processed_content = process_citation_ids_in_text(buffer_content)
                            content_map[content_key].markdown(processed_content, unsafe_allow_html=True)
                            logger.debug("Completion: Updated display with processed citations")
                    
                    # Update THE SINGLE status container to show completion
                    single_status_container.update(
                        label=":material/check_circle: Request completed", 
                        state="complete", 
                        expanded=not status_collapsed_on_response  # Keep collapsed if already collapsed during response
                    )
                    break
                    
                case _:
                    # Handle unknown event types - only log/store in debug mode
                    if debug_mode:
                        logger.debug(f"Unknown event type: {event.event}", event_data=event_data)
                        # Store unknown events in debug data
                        if consolidated_api_response and "unknown_events" not in consolidated_api_response:
                            consolidated_api_response["unknown_events"] = []
                        if consolidated_api_response:
                            consolidated_api_response["unknown_events"].append({
                                "event_type": event.event,
                                "data": event_data
                            })
                    else:
                        # Silently ignore unknown events when not in debug mode
                        logger.debug(f"Ignoring unknown event: {event.event} - debug mode disabled")
                    
                    # Don't break - continue processing other events
        
        # Ensure spinner is properly closed and status container shows completion
        if spinner_active and spinner:
            spinner.__exit__(None, None, None)
            spinner_active = False
        
        # Final status update - ensure completion is shown even if "response.done" wasn't received
        if single_status_container is not None:
            single_status_container.update(
                label=":material/check_circle: Request completed", 
                state="complete", 
                expanded=not status_collapsed_on_response  # Keep collapsed if already collapsed during response
            )
            
            # SMART BUFFERING: Fallback citation processing if response.done wasn't received (current request only)
            logger.debug(f"Fallback: Checking if citation processing needed for request {current_request_id}")
            for content_key, buffer_content in buffers.items():
                # Only process content for the current request
                if (isinstance(content_key, tuple) and content_key[0] == current_request_id and 
                    buffer_content and ('cs_' in buffer_content or '<cite>' in buffer_content)):
                    logger.debug(f"Fallback: Processing citations for content_key {content_key}")
                    processed_content = process_citation_ids_in_text(buffer_content)
                    content_map[content_key].markdown(processed_content, unsafe_allow_html=True)
                    logger.debug("Fallback: Updated display with processed citations")
        
        # Store consolidated debug data if debug mode is enabled
        if debug_mode and consolidated_api_response:
            consolidated_api_response["event_summary"]["total_events"] = len(all_events)
            consolidated_api_response["event_summary"]["event_types"] = event_types
            session_manager.debug_state.debug_consolidated_response = consolidated_api_response
            
            # Convert to format expected by debug interface
            session_manager.debug_state.debug_request_json_str = json.dumps(
                session_manager.debug_state.debug_request_body, 
                indent=2, 
                ensure_ascii=False
            )
            session_manager.debug_state.debug_response_json_str = json.dumps(
                consolidated_api_response, 
                indent=2, 
                ensure_ascii=False
            )
            session_manager.debug_state.debug_event_count = len(all_events)
            session_manager.debug_state.debug_event_types = event_types
            
            logger.debug(f"🔧 DEBUG DATA PREPARED: {len(all_events)} events, {len(event_types)} types")
            
        elif debug_mode:
            st.warning(f"🔧 Debug: Debug mode active but no consolidated response data available")
        
        # SMART BUFFERING: Process the final bot_text_message for return (citations processed)
        logger.debug("Smart buffering: Processing final message for return")
        logger.debug(f"Final message length: {len(bot_text_message) if bot_text_message else 0}")
        
        if bot_text_message and ('<cite>' in bot_text_message or 'cs_' in bot_text_message):
            logger.debug("Final message: Processing citations in return message")
            bot_text_message = process_citation_ids_in_text(bot_text_message)
            logger.debug(f"Final message: Processed citations, mapping has {len(session_manager.tool_state.citation_id_mapping)} entries")
        else:
            logger.debug("Final message: No citations to process in return message")
        
        # Check if agent mentioned tables but no table events occurred
        _handle_missing_table_references()
        
        # Display citations at the end of streaming (not during) - always happens regardless of debug mode
        display_post_completion_citations()
        
        # Always show debug interface after streaming if debug mode is active
        if debug_mode:
            logger.debug(f"Showing debug interface - debug mode: {debug_mode}")
            from modules.ui.debug_interface import display_debug_interface_now
            display_debug_interface_now()
        else:
            logger.debug(f"Skipping debug interface - debug mode: {debug_mode}")
                    
    except Exception as e:
        st.error(f"Streaming error: {str(e)}")
        if spinner_active and spinner:
            spinner.__exit__(None, None, None)
        
        # Mark THE SINGLE status container as error when streaming fails
        if single_status_container is not None:
            single_status_container.update(
                label=":material/error: Request failed", 
                state="error", 
                expanded=True
            )
    
    # Debug mode cleanup - no special handling needed anymore
    if debug_mode:
        logger.debug("Debug mode completed successfully")
    else:
        logger.debug("Standard mode completed successfully")
    
    # Return the accumulated assistant response text (now properly processed for citations)
    return bot_text_message

# Helper functions for event handling
def _handle_tool_use_event(data: ToolUseEventData, event_data: dict, single_status_container, current_status_label: str, debug_mode: bool):
    """Handle tool use event display with detailed context"""
    session_manager = get_session_manager()
    
    # Extract tool information - name is directly in event_data
    tool_name = event_data.get("name", "Unknown Tool")
    tool_input = event_data.get("input", {})
    tool_type = event_data.get("type", "")
    tool_use_id = event_data.get("tool_use_id", "")
    
    # Store tool input data for later use in tool_result handler
    if tool_use_id:
        session_manager.tool_state.current_tool_inputs[tool_use_id] = tool_input
    
    # Status label is already updated in the main event handler, just show content
    
    # Show basic tool information for all users (not just debug mode)
    with single_status_container:
        if tool_input:
            query_text = tool_input.get("query", "")
            sql_query = tool_input.get("sql", "")
            reference_vqrs = tool_input.get("reference_vqrs", [])
            
            if query_text:
                st.markdown("**:material/psychology_alt: Query:**")
                # Show truncated query for readability
                display_query = query_text[:200] + "..." if len(query_text) > 200 else query_text
                st.code(display_query, language="text")
            elif sql_query:
                st.markdown("**:material/settings: SQL Query:**")
                # Show full SQL query with enhanced display
                st.code(sql_query, language="sql", height=250, line_numbers=True)
            elif reference_vqrs:
                # Show reference SQL queries if available
                st.markdown("**:material/settings: Reference SQL Query:**")
                for i, vqr in enumerate(reference_vqrs[:1]):  # Show only first one for non-debug
                    if isinstance(vqr, dict) and "sql" in vqr:
                        st.code(vqr["sql"], language="sql", height=250, line_numbers=True)
                        break
            elif tool_input.get("search_term"):
                search_term = tool_input.get("search_term", "")
                st.markdown(f"**Searching for:** {search_term}")
        
        # Show detailed tool information for debugging (additional UI without changing logic)
        if debug_mode:
            with st.expander(f"🔧 Debug: Tool Details - {tool_name}", expanded=False):
                st.markdown(f"**Tool:** `{tool_name}`")
                if tool_type:
                    st.markdown(f"**Type:** `{tool_type}`")
                if tool_input:
                    st.markdown("**Input Parameters:**")
                    # Extract and show the actual query being executed
                    query_text = tool_input.get("query", "")
                    if query_text:
                        st.markdown("**Query:**")
                        st.code(query_text, language="text")
                    
                    # Show reference VQRs if available
                    reference_vqrs = tool_input.get("reference_vqrs", [])
                    if reference_vqrs:
                        st.markdown("**🔗 Reference SQL:**")
                        for i, vqr in enumerate(reference_vqrs):
                            if isinstance(vqr, dict) and "sql" in vqr:
                                if len(reference_vqrs) > 1:
                                    st.markdown(f"*Reference Query {i+1}:*")
                                st.code(vqr["sql"], language="sql", height=200, line_numbers=True)
                                if "question" in vqr:
                                    st.caption(f"Related question: {vqr['question']}")
                    
                    # Show summary of other parameters (avoiding nested expanders)
                    other_params = {k: v for k, v in tool_input.items() if k not in ["query", "sql", "reference_vqrs"]}
                    if other_params:
                        st.markdown("**Other Parameters:**")
                        st.json(other_params)

def _extract_citations_from_tool_result(event_data: dict) -> None:
    """Extract and store citation data from tool result event."""
    session_manager = get_session_manager()
    try:
        content_items = event_data.get('content', [])
        logger.debug(f"🔧 Processing {len(content_items)} content items for citations")
        
        for content_item in content_items:
            if isinstance(content_item, dict) and 'json' in content_item:
                search_results = content_item['json'].get('search_results', [])
                logger.debug(f"🔧 Found {len(search_results)} search results")
                
                for citation_item in search_results:
                    if isinstance(citation_item, dict) and citation_item.get('doc_title') and citation_item.get('id', '').startswith('cs_'):
                        citation_id = citation_item.get('id')
                        citation_data = {
                            'id': citation_id,
                            'doc_id': citation_item.get('doc_id'),
                            'doc_title': citation_item.get('doc_title'),
                            'source_id': citation_item.get('source_id', 0)
                        }
                        
                        # Store in both legacy and thread-based storage
                        session_manager.add_tool_citation(citation_id, citation_data)
                        session_manager.add_thread_tool_citation(citation_id, citation_data)
                        
                        current_response_id = session_manager.response_state.current_response_id or 'unknown'
                        logger.debug(f"Stored citation for response {current_response_id}: {citation_id} -> {citation_item.get('doc_title')}")
                        
    except Exception as e:
        logger.warning(f"Error extracting citations from tool result: {e}")

def _extract_tool_metadata(event_data: dict) -> dict:
    """Extract tool metadata from event data."""
    return {
        'name': event_data.get("name", "Unknown Tool"),
        'type': event_data.get("type", ""),
        'status': event_data.get("status", "unknown"),
        'tool_use_id': event_data.get("tool_use_id", ""),
        'content_array': event_data.get("content", [])
    }

def _process_tool_content(content_array: list) -> dict:
    """Process tool content and extract SQL, text, and other information."""
    sql_queries = []
    text_content = []
    other_info = {}
    
    for content_item in content_array if isinstance(content_array, list) else []:
        if isinstance(content_item, dict):
            if content_item.get("type") == "json" and "json" in content_item:
                json_data = content_item["json"]
                
                # Extract SQL
                if "sql" in json_data:
                    sql_queries.append(json_data["sql"])
                
                # Extract text explanations
                if "text" in json_data and json_data["text"]:
                    text_content.append(json_data["text"])
                
                # Extract other meaningful fields
                for key, value in json_data.items():
                    if key not in ["sql", "text", "data", "resultSetMetaData"] and value is not None:
                        other_info[key] = value
            
            # Handle other content types
            elif "text" in content_item:
                text_content.append(content_item["text"])
            elif "sql" in content_item:
                sql_queries.append(content_item["sql"])
    
    return {
        'sql_queries': sql_queries,
        'text_content': text_content,
        'other_info': other_info
    }

def _process_embedded_table_data(content_array: list) -> None:
    """Process and display embedded table data from tool results."""
    for content_item in content_array if isinstance(content_array, list) else []:
        if isinstance(content_item, dict) and content_item.get("type") == "json" and "json" in content_item:
            json_data = content_item["json"]
            
            if "data" in json_data and "resultSetMetaData" in json_data:
                logger.debug("Found table data in tool result", 
                          rows=len(json_data["data"]) if isinstance(json_data["data"], list) else 0,
                          metadata_keys=list(json_data["resultSetMetaData"].keys()) if isinstance(json_data["resultSetMetaData"], dict) else "not dict")
                try:
                    table_data = json_data["data"]
                    metadata = json_data["resultSetMetaData"]
                    
                    # Get column names from metadata - try multiple possible structures
                    column_names = []
                    if "rowType" in metadata and isinstance(metadata["rowType"], list):
                        logger.debug("Using rowType for column names", rowType_count=len(metadata["rowType"]))
                        column_names = [col.get("name", f"col_{i}") if isinstance(col, dict) else str(col) 
                                      for i, col in enumerate(metadata["rowType"])]
                    elif "row_type" in metadata and isinstance(metadata["row_type"], list):
                        logger.debug("Using row_type for column names", row_type_count=len(metadata["row_type"]))
                        column_names = [col.get("name", f"col_{i}") if isinstance(col, dict) else str(col) 
                                      for i, col in enumerate(metadata["row_type"])]
                    elif "columns" in metadata:
                        logger.debug("Using columns for column names")
                        column_names = metadata["columns"]
                    else:
                        # Fallback: generate column names based on data width
                        first_row = table_data[0] if table_data and isinstance(table_data, list) else []
                        column_names = [f"col_{i}" for i in range(len(first_row))]
                        logger.warning("No column metadata found, using fallback names", fallback_count=len(column_names))
                    
                    # Create and display DataFrame
                    if table_data and column_names:
                        import numpy as np
                        data_array = np.array(table_data)
                        df = pd.DataFrame(data_array, columns=column_names)
                        
                        logger.debug("Displaying table from tool result", 
                                  rows=len(df), 
                                  columns=len(df.columns),
                                  column_names=column_names[:5])
                        
                        # Display the table in the main content area
                        st.subheader("Query Results")
                        st.data_editor(df, use_container_width=True, hide_index=True, disabled=True)
                        
                        # Store table data for persistence
                        # Response tables are always initialized via session manager
                        from modules.config.session_state import get_session_manager
                        session_manager = get_session_manager()
                        
                        tool_table_data = {
                            'data': df.values.tolist(),
                            'columns': column_names,
                            'title': "Query Results"
                        }
                        current_request_id = session_manager.response_state.current_response_id
                        session_manager.add_request_table(tool_table_data, current_request_id)
                        logger.debug("Tool result table data stored for persistence", 
                                   rows=len(df), 
                                   columns=len(df.columns),
                                   total_tables_in_response=len(session_manager.response_state.current_response_tables))
                        
                except Exception as e:
                    logger.error("Error processing table data from tool result", error=str(e))
                    st.error(f"Error displaying table: {e}")

def _display_debug_tool_result(tool_metadata: dict, content_data: dict) -> None:
    """Display debug information for tool results."""
    tool_name = tool_metadata['name']
    tool_status = tool_metadata['status']
    tool_type = tool_metadata['type']
    content_array = tool_metadata['content_array']
    sql_queries = content_data['sql_queries']
    text_content = content_data['text_content']
    other_info = content_data['other_info']
    
    with st.expander(f"🔧 Debug: Tool Result - {tool_name} ({tool_status})", expanded=False):
        # Display tool metadata
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Tool:** `{tool_name}`")
        with col2:
            st.markdown(f"**Status:** `{tool_status}`")
        with col3:
            if tool_type:
                st.markdown(f"**Type:** `{tool_type}`")
        
        if tool_status.lower() == "error":
            st.error("Tool execution failed")
            if content_array:
                st.write("Error details:", content_array)
        else:
            # Display text explanations first
            if text_content:
                st.markdown("**Tool Response:**")
                for text in text_content:
                    st.info(text)
            
            # Display generated SQL queries as code blocks
            if sql_queries:
                st.markdown("**🗃️ Generated SQL:**")
                for i, sql in enumerate(sql_queries):
                    if len(sql_queries) > 1:
                        st.markdown(f"*Query {i+1}:*")
                    st.code(sql, language="sql", height=200, line_numbers=True)
            
            # Display other information
            if other_info:
                st.markdown("**Additional Information:**")
                for key, value in other_info.items():
                    if key == "verified_query_used" and value:
                        st.success("Used verified query template")
                    elif isinstance(value, (str, int, float, bool)):
                        st.markdown(f"**{key.replace('_', ' ').title()}:** `{value}`")
                    else:
                        st.markdown(f"**{key.replace('_', ' ').title()}:**")
                        st.json(value)
            
            # If no content was found
            if not sql_queries and not text_content and not other_info:
                st.success("Tool executed successfully - results processed internally")

def _handle_tool_result_event(data: ToolResultEventData, event_data: dict, single_status_container, current_status_label: str, debug_mode: bool):
    """Handle tool result event display with detailed output - refactored for clarity."""
    
    # Debug logging for the overall event
    logger.debug(f"🔧 Processing tool result event")
    if debug_mode:
        try:
            with open("/tmp/citation_debug.log", "a") as f:
                f.write(f"\n=== TOOL RESULT EVENT ===\n")
                f.write(f"data: {data}\n")
                f.write(f"event_data: {event_data}\n")
                f.write(f"========================\n")
        except Exception as e:
            logger.warning(f"Could not write to debug log: {e}")
    
    # 1. Extract citations (core functionality - always runs)
    _extract_citations_from_tool_result(event_data)
    
    # 2. Extract tool metadata
    tool_metadata = _extract_tool_metadata(event_data)
    
    # 3. Process content (SQL, text, other info)
    content_data = _process_tool_content(tool_metadata['content_array'])
    
    # 4. Process and display embedded table data
    _process_embedded_table_data(tool_metadata['content_array'])
    
    # 5. Display tool response and generated SQL in status container (like query events)
    with single_status_container:
        tool_name = tool_metadata['name']
        tool_status = tool_metadata['status']
        sql_queries = content_data['sql_queries']
        text_content = content_data['text_content']
        
        # Show tool result summary
        if tool_status.lower() == "error":
            st.error(f":material/build: **Tool {tool_name} Failed**")
        else:
            st.write(f":material/build: **Tool {tool_name} Completed**")
        
        # Display tool response text FIRST (before SQL)
        if text_content:
            st.markdown("**:material/chat: Tool Response:**")
            for text in text_content:
                # Truncate long responses for readability in status container
                display_text = text[:300] + "..." if len(text) > 300 else text
                st.write(display_text)
        
        # Display generated SQL queries AFTER tool response
        if sql_queries:
            st.markdown("**:material/settings: Generated SQL:**")
            for i, sql in enumerate(sql_queries):
                if len(sql_queries) > 1:
                    st.markdown(f"*Query {i+1}:*")
                st.code(sql, language="sql", height=200, line_numbers=True)
    
    # 6. Show detailed debug information in expander if debug mode is enabled
    if debug_mode:
        _display_debug_tool_result(tool_metadata, content_data)

def _handle_table_event(data: TableEventData, get_content_container, request_id: str):
    """
    Process and display table data from response.table events.
    
    Handles the complete table processing pipeline including:
    - Column metadata extraction with multiple fallback strategies
    - Data array conversion and validation  
    - DataFrame creation and display
    - Session state persistence for conversation history
    
    Args:
        data: TableEventData object containing result_set with data and metadata
        content_map: Mapping of content indices to Streamlit containers
        
    Note:
        Uses robust column name extraction to handle various metadata formats
        from different Snowflake API responses. Stores table data in session
        state for persistence across conversation turns.
    """
    content_idx = data.content_index if hasattr(data, 'content_index') else 0
    logger.debug("Processing table event", content_index=content_idx)
    
    # Initialize session manager for table storage
    session_manager = get_session_manager()
    
    try:
        import numpy as np
        data_array = np.array(data.result_set.data)
        logger.debug("Table data array created", shape=data_array.shape)
        
        # Extract column names from model with robust handling
        metadata = data.result_set.result_set_meta_data
        logger.debug("Full metadata structure", 
                   metadata_type=type(metadata),
                   metadata_attrs=dir(metadata) if hasattr(metadata, '__dict__') else 'no attrs',
                   metadata_dict=metadata.__dict__ if hasattr(metadata, '__dict__') else 'no dict')
        
        # Try different possible property names for column metadata
        row_type = None
        if hasattr(metadata, 'row_type'):
            row_type = metadata.row_type
            logger.debug("Found row_type", row_type_length=len(row_type) if row_type else 0)
        elif hasattr(metadata, 'rowType'):
            row_type = metadata.rowType  
            logger.debug("Found rowType", rowType_length=len(row_type) if row_type else 0)
        elif hasattr(metadata, 'columns'):
            row_type = metadata.columns
            logger.debug("Found columns", columns_length=len(row_type) if row_type else 0)
        
        logger.debug("Raw row_type structure", 
                   row_type_type=type(row_type), 
                   row_type_length=len(row_type) if row_type else 0,
                   first_item=row_type[0] if row_type and len(row_type) > 0 else None)
        
        column_names = []
        if row_type and len(row_type) > 0:
            # Try different extraction methods
            for i, col in enumerate(row_type):
                if isinstance(col, dict):
                    # Method 1: Standard dict with 'name' key
                    if "name" in col:
                        column_names.append(col["name"])
                    # Method 2: Check for other possible name fields
                    elif "NAME" in col:
                        column_names.append(col["NAME"])
                    elif "column_name" in col:
                        column_names.append(col["column_name"])
                    else:
                        logger.warning("Column dict missing name field", column_dict=col)
                        column_names.append(f"col_{i}")
                else:
                    # Method 3: Direct string value
                    column_names.append(str(col))
        
        # Fallback: generate column names if extraction failed
        if not column_names or len(column_names) != data_array.shape[1]:
            logger.warning("Column name extraction failed, using defaults", 
                         extracted_count=len(column_names),
                         expected_count=data_array.shape[1])
            column_names = [f"col_{i}" for i in range(data_array.shape[1])]
        
        logger.debug("Table columns extracted", columns=column_names[:5])  # Log first 5 column names
            
        # Create and display the dataframe
        df = pd.DataFrame(data_array, columns=column_names)
        logger.debug("DataFrame created successfully", rows=len(df), columns=len(df.columns))
        
        # Use request-scoped content key to prevent cross-request interference
        table_key = (request_id, content_idx)
        get_content_container(table_key).dataframe(df)
        logger.debug("Table displayed successfully in content container", content_index=content_idx, request_id=request_id)
        
        # Store table data in session state for conversation history persistence
        # Defensive initialization - should already be set by session state defaults
        # Response tables are always initialized via session manager
        
        # Protect against memory issues - limit table accumulation
        current_tables = session_manager.response_state.current_response_tables
        if len(current_tables) > 10:
            logger.warning("Too many tables in current response, clearing old data", count=len(current_tables))
            session_manager.response_state.current_response_tables = current_tables[-5:]  # Keep last 5
        
        # Convert DataFrame back to raw data for storage
        table_data = {
            'data': df.values.tolist(),
            'columns': column_names,
            'title': None  # Could be enhanced to extract title from response
        }
        session_manager.add_request_table(table_data, request_id)
        logger.debug("Table data stored for persistence", 
                   rows=len(df), 
                   columns=len(df.columns),
                   total_tables_in_response=len(session_manager.response_state.current_response_tables))
        
    except Exception as e:
        logger.error("Error displaying table", error=str(e), content_index=content_idx, request_id=request_id)
        table_key = (request_id, content_idx)
        get_content_container(table_key).error(f"Error displaying table: {e}")

def _detect_and_handle_table_references(text_buffer: str) -> None:
    """
    Detect when the agent mentions showing tables but doesn't emit table events.
    
    This handles cases where the agent says "Please find the requested table below"
    or references previous tool results but doesn't actually emit new table data.
    """
    session_manager = get_session_manager()
    # Skip empty or very short buffers
    if not text_buffer or len(text_buffer.strip()) < 5:
        return
    
    # Patterns that indicate the agent intends to show a table
    table_reference_patterns = [
        "please find the requested table below",
        "here is the table",
        "the table below shows",
        "find the table below",
        "requested table below",
        "show the table",
        "display the table",
        "table that shows",
        "see the table",
        "table data",
        "show you the data in a table"
    ]
    
    text_lower = text_buffer.lower()
    
    # Log text processing for table reference detection
    logger.debug(f"Checking text for table references: '{text_lower[:100]}...'")
    
    # Check if the agent mentions showing a table
    for pattern in table_reference_patterns:
        if pattern in text_lower:
            logger.warning(f"Table reference detected with pattern '{pattern}' in text: {text_buffer[:100]}...")
            
            # Mark that a table was referenced for potential future handling
            current_request_id = session_manager.response_state.current_response_id
            session_manager.set_request_table_referenced(True, current_request_id)
            logger.warning("Table reference flagged - agent mentioned showing table but no table event detected")
            break
    
    # Check for tool result ID patterns (like "tool result ID: toolu_...")
    import re
    tool_result_pattern = r'tool result ID:\s*([a-zA-Z0-9_]+)'
    tool_matches = re.findall(tool_result_pattern, text_buffer)
    
    if tool_matches:
        logger.warning(f"🔧 TOOL RESULT REFERENCE DETECTED: {tool_matches}")
        # Store referenced tool IDs for potential table extraction
        current_request_id = session_manager.response_state.current_response_id
        for tool_id in tool_matches:
            session_manager.add_request_tool_id(tool_id, current_request_id)


def _handle_missing_table_references() -> None:
    """
    Handle cases where the agent mentioned showing tables but no table events were emitted.
    
    This occurs when agents reference previous tool results containing table data
    without re-emitting the actual table events.
    """
    session_manager = get_session_manager()
    current_request_id = session_manager.response_state.current_response_id
    
    # Use request-scoped data to check for missing tables
    table_referenced = session_manager.response_state.request_table_referenced.get(current_request_id, False)
    tables_in_response = len(session_manager.get_request_tables(current_request_id))
    referenced_tool_ids = session_manager.response_state.request_tool_ids.get(current_request_id, [])
    
    if table_referenced and tables_in_response == 0:
        logger.warning("Missing table: Agent mentioned showing table but no table events detected")
        logger.debug(f"Referenced tool IDs: {referenced_tool_ids}")
        
        # Display enhanced helpful guidance to the user
        with st.container():
            st.warning("**Table Reference Detected**: The agent mentioned showing a table, but the table data was not included in this response.")
            
            with st.expander("**Why is this happening?**", expanded=False):
                st.markdown("""
                **This occurs when:**
                - The agent references previous query results instead of re-running them
                - Previous tool results contain table data but aren't re-emitted
                - The agent mentions tables but doesn't include actual table events
                
                **How to get the table:**
                """)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("Ask agent to re-run query", key="rerun_query"):
                        session_manager.agent_state.suggested_prompt = "Please re-run the query and show me the table data again"
                        st.rerun()
                
                with col2:
                    if st.button("Request fresh table", key="fresh_table"):
                        session_manager.agent_state.suggested_prompt = "Can you execute the query again and display the table?"
                        st.rerun()
        
        if referenced_tool_ids:
            st.info(f"**Technical Details**: The agent referenced tool results: {', '.join(referenced_tool_ids)}")
    
    # Clean up request-scoped flags for next response (handled by request clearing)


def _handle_chart_event(data: ChartEventData, get_content_container, charts: list, request_id: str):
    """
    Process and display chart visualizations from response.chart events.
    
    Handles Vega-Lite chart specification parsing and rendering including:
    - JSON chart specification parsing and validation
    - Nested chart structure unwrapping for complex specifications  
    - Streamlit vega_lite_chart display with container width settings
    - Session state persistence for conversation history and re-display
    
    Args:
        data: ChartEventData object containing chart_spec with Vega-Lite JSON
        content_map: Mapping of content indices to Streamlit containers
        charts: List to accumulate chart specifications for the current response
        request_id: Request ID for content scoping
        
    Note:
        Supports both flat and nested chart specification formats.
        Automatically handles memory management by limiting stored charts.
    """
    content_idx = data.content_index if hasattr(data, 'content_index') else 0
    chart_spec = data.chart_spec if hasattr(data, 'chart_spec') else "{}"
    
    # Initialize session manager for chart storage
    session_manager = get_session_manager()
    
    try:
        # Parse the chart specification
        import json
        spec = json.loads(chart_spec)
        
        # Handle nested chart structure
        if isinstance(spec, dict) and "charts" in spec:
            charts_array = spec["charts"]
            if isinstance(charts_array, list) and len(charts_array) > 0:
                first_chart = charts_array[0]
                if isinstance(first_chart, str):
                    spec = json.loads(first_chart)
                else:
                    spec = first_chart
        
        # Use request-scoped content key to prevent cross-request interference
        chart_key = (request_id, content_idx)
        get_content_container(chart_key).vega_lite_chart(spec, use_container_width=True)
        charts.append(spec)
        
        # CRITICAL: Store chart data for persistence (like tables)
        # This ensures charts also persist in conversation history
        # Response charts are always initialized via session manager
        
        # Protect against memory issues - limit chart accumulation
        current_charts = session_manager.response_state.current_response_charts
        if len(current_charts) > 10:
            logger.warning("Too many charts in current response, clearing old data", count=len(current_charts))
            session_manager.response_state.current_response_charts = current_charts[-5:]  # Keep last 5
        
        # Store chart specification for persistence with request scoping
        chart_data = {
            'spec': spec,
            'title': None  # Could be enhanced to extract title from chart spec
        }
        session_manager.add_request_chart(chart_data, request_id)
        logger.debug("Chart data stored for persistence", 
                   total_charts_in_response=len(session_manager.response_state.current_response_charts))
        
    except (json.JSONDecodeError, KeyError) as e:
        chart_key = (request_id, content_idx)
        get_content_container(chart_key).error(f"Error parsing chart: {e}")
        logger.error("Error processing chart data", error=str(e), content_index=content_idx, request_id=request_id)

def _handle_error_event(data: ErrorEventData, single_status_container):
    """Handle error event display"""
    single_status_container.update(
        label=":material/error: Request failed", 
        state="error", 
        expanded=True
    )
    error_message = data.message if hasattr(data, 'message') else 'Unknown error'
    st.error(f":material/error: {error_message}")
