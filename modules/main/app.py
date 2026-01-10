"""
Main Application Logic for Cortex Agent External Integration

This module contains the core application logic, including the main function
that orchestrates the entire Streamlit application flow.
"""

import os
import json
import pandas as pd
import streamlit as st

# Session state management
from modules.config.session_state import get_session_manager

# Core data models for API communication
from modules.models import (
    TextContentItem,
    TableContentItem,
    ChartContentItem,
    MessageContentItem, 
    Message
)

# Configuration and session management
from config import ASSISTANT_AVATAR, USER_AVATAR
from modules.config.app_config import (
    API_TIMEOUT,
    MAX_DATAFRAME_ROWS,
    THREAD_BASE_ENDPOINT,
    ENABLE_FILE_PREVIEW,
    ENABLE_CITATIONS,
    ENABLE_SUGGESTIONS,
    MAX_PDF_PAGES,
    ENABLE_DEBUG_MODE,
    SHOW_FIRST_TOOL_USE_ONLY
)

# Structured logging infrastructure
from modules.logging import (
    setup_structured_logging,
    get_logger,
    LoggingContext,
    log_performance,
    log_api_call
)

# Snowflake authentication configuration
from modules.config.snowflake_config import SnowflakeConfig

# HTTP client utilities
from modules.api.http_client import execute_curl_request

# Authentication management
from modules.authentication.token_provider import (
    generate_jwt_token,
    get_auth_token,
    get_auth_token_for_agents,
    oauth_connection
)
from modules.authentication.okta_oauth import (
    get_oauth_provider,
    is_oauth_enabled,
    require_authentication
)

# Core Snowflake functionality
from modules.snowflake.client import ExternalSnowflakeClient
from modules.snowflake.agents import get_available_agents, format_sample_questions_for_ui

# Thread management
from modules.threads.management import create_thread, get_thread_messages, delete_thread, get_or_create_thread

# API integration and streaming
from modules.api.cortex_integration import agent_run_streaming, stream_events_realtime

# File management utilities
from modules.files.management import download_file_from_stage, get_presigned_url, get_pdf, display_file_with_scrollbar

# Text processing and data utilities
from modules.utils.text_processing import parse_file_references_new, bot_retrieve_sql_results

# UI components
from modules.ui import (
    config_options,
    display_agent_status,
    clear_conversation_state,
    validate_agent_selection,
    display_debug_interface_now,
    display_debug_interface_if_available
)

from modules.config.session_state import ensure_session_state_defaults

# ------------------------------------------------------------------------------
# Global Configuration and Client (Lazy Initialization)
# ------------------------------------------------------------------------------
# These are initialized lazily inside main() to ensure .env is loaded first
# Do NOT initialize at module level - OAuth env vars won't be available yet
snowflake_client = None
snowflake_config = None


def get_snowflake_client(ssl_verify: bool = None):
    """Get Snowflake client instance with SSL verification setting"""
    config = SnowflakeConfig()
    
    # Use the ssl_verify parameter to override config's SSL setting
    if ssl_verify is not None:
        config.ssl_verify = ssl_verify
    
    return ExternalSnowflakeClient(config), config

# ------------------------------------------------------------------------------
# Initialize DataFrame Options
# ------------------------------------------------------------------------------
pd.set_option("max_colwidth", None)

# Set up structured logging (do this early)
setup_structured_logging()

# ------------------------------------------------------------------------------
# Core Application Functions
# ------------------------------------------------------------------------------

def init_messages(clear_conversation):
    """
    Initialize conversation messages and thread management.
    
    Args:
        clear_conversation (bool): If True, clears existing conversation state and creates new thread.
                                 If False, preserves existing messages and loads from API if needed.
    """
    logger = get_logger()
    session_manager = get_session_manager()
    if clear_conversation:
        # Use the modular function to clear conversation state
        clear_conversation_state(snowflake_config, snowflake_client)
        
        # Create new thread
        get_or_create_thread(snowflake_config, snowflake_client)
    else:
        # Get or create thread and load messages
        thread_id = get_or_create_thread(snowflake_config, snowflake_client)
        if thread_id:
            # Preserve processed content when loading thread messages
            # Only load missing messages from API, don't overwrite processed content
            existing_messages = session_manager.get_thread_messages()
            
            # Log session state for debugging thread message persistence
            logger.debug(f"Loading thread messages - Thread ID: {thread_id}")
            logger.debug(f"Existing messages count: {len(existing_messages) if existing_messages else 0}")
            
            
            if existing_messages:
                # Analyze existing messages for processed content (charts/tables)
                processed_count = 0
                chart_count = 0
                table_count = 0
                for i, msg in enumerate(existing_messages):
                    if hasattr(msg, 'is_processed') and msg.is_processed:
                        processed_count += 1
                    if hasattr(msg, 'processed_content') and msg.processed_content:
                        for item in msg.processed_content:
                            if hasattr(item, 'actual_instance'):
                                if hasattr(item.actual_instance, 'spec'):  # Chart
                                    chart_count += 1
                                elif hasattr(item.actual_instance, 'data'):  # Table
                                    table_count += 1
                logger.debug(f"Processed messages: {processed_count}, Charts: {chart_count}, Tables: {table_count}")
            
            if not existing_messages:
                # No messages in session state, load from API
                logger.debug("No existing messages - Loading from API (note: processed content will need regeneration)")
                thread_response = get_thread_messages(thread_id, snowflake_config, snowflake_client)
                if thread_response:
                    ui_messages = []
                    for thread_msg in thread_response.messages:
                        # Convert ThreadMessage to UI Message for display
                        # Parse message_payload to get the actual content
                        try:
                            payload_data = json.loads(thread_msg.message_payload) if thread_msg.message_payload else {}
                            text = payload_data.get("text", thread_msg.message_payload)
                        except:
                            text = thread_msg.message_payload
                        
                        # Create UI Message object with raw content
                        # Note: These are from API so they won't have processed content yet
                        text_content = TextContentItem(type="text", text=text)
                        content_item = MessageContentItem(actual_instance=text_content)
                        ui_message = Message(role=thread_msg.role, content=[content_item])
                        ui_message.text = text  # For easy access
                        ui_message.raw_text = text  # Store raw text for API compatibility
                        # Don't mark as processed since this is raw API data
                        ui_messages.append(ui_message)
                    
                    session_manager.thread_state.thread_messages = ui_messages
                    logger.debug(f"Loaded {len(ui_messages)} messages from thread API (raw content only)")
                else:
                    session_manager.clear_thread_messages()
            else:
                # Messages exist in session state - preserve them to maintain processed content
                # This prevents reformatting of messages that have already been processed
                logger.debug(f"Preserved {len(existing_messages)} existing messages with processed content")
                
                # Note: Future enhancement could implement smart merging to add new API messages
                # while preserving existing processed content


def process_new_message_with_thread(prompt: str) -> None:
    """
    Process a new user message using thread-based conversation management.
    
    This function handles the complete lifecycle of processing a user message:
    - Creates/retrieves the conversation thread
    - Sends user message to the Cortex Agent API
    - Streams the assistant response in real-time
    - Stores processed content for conversation persistence
    
    Args:
        prompt (str): The user's input message to process
    """
    global snowflake_client, snowflake_config
    logger = get_logger()
    session_manager = get_session_manager()
    
    # Log user interaction with key metadata
    logger.info(
        "User message received",
        message_length=len(prompt),
        thread_id=session_manager.get_thread_id(),
        agent_name=session_manager.get_selected_agent().get("name", "unknown") if session_manager.has_selected_agent() else "unknown",
        user_prompt_preview=prompt[:100] + "..." if len(prompt) > 100 else prompt
    )
    
    # Store user message for potential regeneration and disable regeneration during processing
    session_manager.set_last_user_message(prompt)
    session_manager.disable_regeneration()
    
    thread_id = get_or_create_thread(snowflake_config, snowflake_client)
    if not thread_id:
        logger.error("Failed to create or get thread for user message")
        st.error("Failed to create or get thread")
        return
    
    # Create user message using proper Message model structure
    user_text_content = TextContentItem(type="text", text=prompt)
    user_content_item = MessageContentItem(actual_instance=user_text_content)
    user_message = Message(role="user", content=[user_content_item])
    
    # Store additional metadata for UI display and compatibility
    user_message.text = prompt  # For easy access
    user_message.timestamp = pd.Timestamp.now().strftime('%H:%M:%S')
    
    # Add user message to conversation history for persistence
    session_manager.add_thread_message(user_message)
    
    # Process assistant response with real-time streaming
    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        # Use streaming mode for real-time response and debug capabilities
        with st.spinner("Sending request..."):
            response = agent_run_streaming(thread_id, prompt, snowflake_config, snowflake_client)
        
        if response:
            # Display request ID in debug mode for troubleshooting
            request_id = response.headers.get('X-Snowflake-Request-Id')
            if request_id and session_manager.is_debug_mode():
                st.toast(f":material/assignment: Request ID: {request_id}", icon=":material/assignment:")
            # Store client reference for citation processing
            st.session_state.snowflake_client = snowflake_client
            
            # Process real-time streaming and capture assistant response
            try:
                assistant_response = stream_events_realtime(response, session_manager.is_debug_mode())
                    
            except Exception as streaming_error:
                get_logger().error("Streaming failed, cleaning up table data", error=str(streaming_error))
                # Clear any orphaned response data from failed streaming
                session_manager.clear_response_content()
                st.error(f"Streaming failed: {streaming_error}")
                return
            
            # Store assistant response in session state for conversation history
            if assistant_response:
                    # Start with text content from streaming response
                    content_items = [MessageContentItem(actual_instance=TextContentItem(text=assistant_response))]
                    
                    # Capture table and chart data for conversation history persistence
                    current_request_id = session_manager.response_state.current_response_id
                    
                    # Smart content retrieval: Find request IDs that actually contain content
                    # Charts and tables may be stored under different request IDs than the current one
                    all_request_tables = session_manager.response_state.request_tables
                    all_request_charts = session_manager.response_state.request_charts
                    
                    # Locate the most recent request containing charts
                    chart_request_id = None
                    if all_request_charts:
                        chart_request_ids = [rid for rid, charts in all_request_charts.items() if charts]
                        if chart_request_ids:
                            chart_request_id = chart_request_ids[-1]
                    
                    # Locate the most recent request containing tables
                    table_request_id = None
                    if all_request_tables:
                        table_request_ids = [rid for rid, tables in all_request_tables.items() if tables]
                        if table_request_ids:
                            table_request_id = table_request_ids[-1]
                    
                    # Use content-specific request IDs or fallback to current request
                    effective_chart_request_id = chart_request_id or current_request_id
                    effective_table_request_id = table_request_id or current_request_id
                    
                    # Retrieve content using the appropriate request IDs
                    retrieved_tables = session_manager.get_request_tables(effective_table_request_id)
                    retrieved_charts = session_manager.get_request_charts(effective_chart_request_id)
                    tables_data = list(retrieved_tables) if retrieved_tables else None
                    charts_data = list(retrieved_charts) if retrieved_charts else None
                    
                    # Process table data captured during streaming
                    if tables_data:
                        for table_data in tables_data:
                            table_content = TableContentItem(
                                data=table_data['data'],
                                columns=table_data['columns'],
                                title=table_data.get('title')
                            )
                            content_items.append(MessageContentItem(actual_instance=table_content))
                        
                        # Clear table data for next response
                        table_count = len(tables_data) if tables_data else 0
                    
                    # Process chart data captured during streaming
                    if charts_data:
                        for chart_data in charts_data:
                            chart_content = ChartContentItem(
                                spec=chart_data['spec'],
                                title=chart_data.get('title')
                            )
                            content_items.append(MessageContentItem(actual_instance=chart_content))
                        
                        # Clear chart data for next response
                        chart_count = len(charts_data) if charts_data else 0
                    
                    assistant_message = Message(
                        role="assistant",
                        content=content_items
                    )
                    
                    # Set message ID from API metadata response (captured during streaming)
                    if hasattr(session_manager.response_state, 'current_assistant_message_id') and session_manager.response_state.current_assistant_message_id:
                        assistant_message.id = str(session_manager.response_state.current_assistant_message_id)
                    
                    # Store processed content to prevent thread reformatting
                    # The assistant_response already contains processed text with citations ([1], [2], etc.)
                    # Store this processed content so thread continuations display consistently
                    
                    # Include citation section in processed content to prevent reformatting
                    from modules.citations.display import generate_citation_html_for_processed_content
                    citation_html = generate_citation_html_for_processed_content()
                    
                    # Combine text and citation section for complete processed content
                    complete_processed_text = assistant_response + citation_html
                    
                    assistant_message.store_processed_content(
                        processed_text=complete_processed_text,  # Text + citation section
                        tables=tables_data,  # Table data captured before clearing
                        charts=charts_data   # Chart data captured before clearing  
                    )
                    
                    # Store citations with this message for persistence
                    thread_citations = session_manager.get_thread_citations()
                    if thread_citations:
                        # Copy current citations and attach to this message
                        message_citations = list(thread_citations)
                        assistant_message.citations = message_citations
                    
                    # Add assistant message to conversation history
                    session_manager.add_thread_message(assistant_message)
                    
                    # Enable regeneration after successful response
                    session_manager.enable_regeneration()
                    # Note: No immediate rerun to prevent chart flashing - regenerate button will appear on next interaction
                    
                    # Clear the captured message ID for next response
                    session_manager.response_state.current_assistant_message_id = None


def main():
    """
    Main application function that orchestrates the Streamlit UI and conversation flow.
    
    This function handles:
    - OAuth authentication (if configured) - FIRST before anything else
    - Session state initialization and management
    - UI configuration and agent selection
    - Conversation history display with rich content (tables, charts, citations)
    - User input processing and response generation
    - Debug interface display when enabled
    """
    global snowflake_client, snowflake_config
    logger = get_logger()
    
    # ==========================================================================
    # STEP 0: Initialize Snowflake Config (must happen after .env is loaded)
    # ==========================================================================
    # This is done here (not at module level) to ensure .env variables are loaded
    ssl_verify_env = os.environ.get('SNOWFLAKE_SSL_VERIFY', 'true').lower() in ('true', 'yes', '1')
    snowflake_client, snowflake_config = get_snowflake_client(ssl_verify=ssl_verify_env)
    
    # ==========================================================================
    # STEP 1: OAuth Authentication (MUST be first - before any other UI)
    # ==========================================================================
    if is_oauth_enabled():
        oauth_provider = get_oauth_provider()
        
        # Handle OAuth callback if present in URL (from Okta redirect)
        oauth_provider.handle_callback()
        
        # Check if user is authenticated
        if not oauth_provider.is_authenticated():
            # Show login page and stop - NOTHING else loads until authenticated
            oauth_provider.show_login_page()
            st.stop()
            return
        
        # Check if user wants to see their profile/token info page
        if st.session_state.get('show_oauth_profile', False):
            oauth_provider.show_landing_page()
            st.stop()
            return
        
        # User is authenticated - get tokens and user info
        access_token = oauth_provider.get_access_token()
        user_info = oauth_provider.get_current_user()
        
        if access_token:
            # Update snowflake config with OAuth token for API calls
            snowflake_config.set_oauth_token(
                token=access_token,
                user_email=user_info.get('email') if user_info else None
            )
            
            logger.info(f"OAuth user authenticated: {user_info.get('email') if user_info else 'unknown'}")
        else:
            # Token expired or invalid - force re-login
            logger.warning("OAuth token not available - forcing re-authentication")
            oauth_provider.logout()
            oauth_provider.show_login_page()
            st.stop()
            return
        
        # Show user info in sidebar (compact user info at top)
        oauth_provider.show_user_info_sidebar()
    
    # ==========================================================================
    # STEP 2: Initialize Session State (after authentication)
    # ==========================================================================
    ensure_session_state_defaults()
    session_manager = get_session_manager()
    
    # Store OAuth state in session manager if OAuth is enabled
    if is_oauth_enabled():
        oauth_provider = get_oauth_provider()
        access_token = oauth_provider.get_access_token()
        user_info = oauth_provider.get_current_user()
        
        if access_token:
            # Get refresh token from session state
            refresh_token = st.session_state.get(oauth_provider.REFRESH_TOKEN_KEY)
            
            # Store tokens in session manager for other modules to access
            session_manager.set_oauth_tokens(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=3600
            )
            if user_info:
                session_manager.set_oauth_user_info(user_info)
    
    # ==========================================================================
    # STEP 3: Initialize UI and Agent Selection
    # ==========================================================================
    clear_conversation, regenerate_clicked = config_options(snowflake_config, snowflake_client)
    init_messages(clear_conversation)
    
    # Handle regenerate button from sidebar - Works exactly like clicking a sample question
    if regenerate_clicked:
        last_message = session_manager.get_last_user_message()
        if last_message:
            # Set the last user message as active sample question - this makes it work 
            # exactly like clicking a sample question button
            session_manager.agent_state.active_sample_question = last_message
            st.rerun()
            return
    
    # Custom CSS for gradient text effect (much simpler now)
    st.markdown("""
    <style>
    /* Gradient text styling for div-based title (no anchor links generated) */
    #agent-title-heading,
    div#agent-title-heading,
    .gradient-title {
        background: linear-gradient(90deg, #89b4fa 0%, #b4a5f5 50%, #cba6f7 100%) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        background-clip: text !important;
        font-size: 2.5rem !important;
        font-weight: 600 !important;
        margin: 0 0 1.5rem 0 !important;
        padding: 0 !important;
        font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif !important;
        line-height: 1.1 !important;
        letter-spacing: -0.02em !important;
        display: block !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Dynamic title based on selected agent (using div to avoid anchor links)  
    if session_manager.has_selected_agent():
        selected_agent = session_manager.get_selected_agent()
        # Using div instead of h1 to completely avoid anchor link generation
        st.markdown(f'''
        <div id="agent-title-heading" class="gradient-title" style="
            background: linear-gradient(90deg, #89b4fa 0%, #b4a5f5 50%, #cba6f7 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-size: 2.5rem;
            font-weight: 600;
            margin: 0 0 1.5rem 0;
            padding: 0;
            font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.1;
            letter-spacing: -0.02em;
        ">{selected_agent["display_name"]}</div>
        ''', unsafe_allow_html=True)
    else:
        st.markdown('''
        <div id="agent-title-heading" class="gradient-title" style="
            background: linear-gradient(90deg, #89b4fa 0%, #b4a5f5 50%, #cba6f7 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-size: 2.5rem;
            font-weight: 600;
            margin: 0 0 1.5rem 0;
            padding: 0;
            font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.1;
            letter-spacing: -0.02em;
        ">Cortex Agent - External Integration Demo</div>
        ''', unsafe_allow_html=True)
    
    # Display agent status information and selection warnings
    display_agent_status()

    # Display conversation history from session state
    # This ensures previous messages persist across Streamlit reruns
    if session_manager.get_thread_messages():
        # Track content types for debugging purposes
        total_messages = len(session_manager.get_thread_messages())
        chart_count = 0
        table_count = 0
        processed_count = 0
        
        
        # Display each message and track content types
        for message in session_manager.get_thread_messages():
            role = message.role if hasattr(message, 'role') else 'user'
            
            # Count content types in this message for analytics
            if hasattr(message, 'processed_content') and message.processed_content:
                if hasattr(message, 'is_processed') and message.is_processed:
                    processed_count += 1
                for item in message.processed_content:
                    if hasattr(item, 'actual_instance'):
                        if hasattr(item.actual_instance, 'spec'):  # Chart
                            chart_count += 1
                        elif hasattr(item.actual_instance, 'data'):  # Table
                            table_count += 1
            
            # Use processed content when available to prevent reformatting
            # This ensures consistent display by using processed content instead of re-processing
            if hasattr(message, 'get_display_content'):
                content = message.get_display_content()
            else:
                # Fallback for messages without the new methods
                content = message.content if hasattr(message, 'content') else str(message)
            
            # Set avatar based on role
            avatar = ASSISTANT_AVATAR if role == "assistant" else USER_AVATAR
            with st.chat_message(role, avatar=avatar):
                # Handle mixed content (text and tables)
                if isinstance(content, list):
                    for item in content:
                        if hasattr(item, 'actual_instance'):
                            # Handle different content types
                            if isinstance(item.actual_instance, TextContentItem):
                                st.markdown(item.actual_instance.text, unsafe_allow_html=True)
                            elif isinstance(item.actual_instance, TableContentItem):
                                # Display table from stored data
                                table_content = item.actual_instance
                                if table_content.data and table_content.columns:
                                    df = pd.DataFrame(table_content.data, columns=table_content.columns)
                                    if table_content.title:
                                        st.subheader(table_content.title)
                                    st.data_editor(df, use_container_width=True, hide_index=True, disabled=True)
                            elif isinstance(item.actual_instance, ChartContentItem):
                                # Display chart from stored data
                                chart_content = item.actual_instance
                                if chart_content.spec:
                                    if chart_content.title:
                                        st.subheader(chart_content.title)
                                    st.vega_lite_chart(chart_content.spec, use_container_width=True)
                        elif hasattr(item, 'text'):
                            # Legacy text content
                            st.markdown(item.text, unsafe_allow_html=True)
                        else:
                            st.markdown(str(item), unsafe_allow_html=True)
                else:
                    # Single content item (legacy format)
                    st.markdown(content, unsafe_allow_html=True)
                
                # Skip individual citation re-display for processed messages
                # Processed messages already contain the complete display including citations
                skip_citation_redisplay = (hasattr(message, 'is_processed') and message.is_processed)
                
                # Re-display citations only for unprocessed messages (legacy compatibility)
                if (role == "assistant" and hasattr(message, 'citations') and message.citations 
                    and not skip_citation_redisplay):
                    for citation in message.citations:
                        citation_type = citation.get('citation_type', 'unknown')
                        
                        if citation_type == 'documentation':
                            # Re-display documentation citations as hyperlinks
                            doc_id = citation.get('doc_id')
                            doc_title = citation.get('doc_title')
                            if doc_id and doc_title:
                                st.markdown(f"📎 **Citation:** [{doc_title}]({doc_id})")
                        
                        elif citation_type == 'file':
                            # Re-display file citations with preview
                            file_path = citation.get('file_path')
                            file_type = citation.get('file_type')
                            citation_id = citation.get('citation_id', 'historical')
                            
                            if file_path and file_type:
                                # Get session for file operations
                                snowflake_client = st.session_state.get('snowflake_client')
                                if snowflake_client and hasattr(snowflake_client, 'session'):
                                    from modules.files.management import display_file_with_scrollbar
                                    session = snowflake_client.session
                                    st.markdown("### 📎 Citation")
                                    display_file_with_scrollbar(
                                        relative_path=file_path,
                                        session=session,
                                        file_type=file_type,
                                        citation_id=f"history_{citation_id}"
                                    )
                                else:
                                    st.info(f"📎 Citation: {file_path} ({file_type})")
        
        # Log conversation content summary for debugging
        logger.debug(f"Conversation display - Total messages: {total_messages}, Processed: {processed_count}, Charts: {chart_count}, Tables: {table_count}")

    # Display persistent debug interface if available
    display_debug_interface_if_available()

    # Check if user selected a sample question, suggested prompt, or typed a new question
    user_input = st.chat_input("Ask a question..")
    sample_question = session_manager.agent_state.active_sample_question
    if sample_question:
        session_manager.agent_state.active_sample_question = None
    suggested_prompt = session_manager.agent_state.suggested_prompt
    if suggested_prompt:
        session_manager.agent_state.suggested_prompt = None
    
    # Priority: suggested prompt > sample question > user input
    question = suggested_prompt if suggested_prompt else (sample_question if sample_question else (user_input.strip() if user_input else None))

    # Process new user question
    if question:
        # Check if an agent is selected using modular function
        if not validate_agent_selection():
            return
        
        selected_agent = session_manager.get_selected_agent()
        
        # Display user question
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(question)
        
        # Process with thread-based approach using selected agent
        agent_name = selected_agent['display_name']
        with st.spinner(f":blue[**{agent_name}**] is evaluating your question..."):
            process_new_message_with_thread(question)
    
    # ==========================================================================
    # FINAL: Add logout button at bottom of sidebar (if OAuth enabled)
    # ==========================================================================
    if is_oauth_enabled():
        oauth_provider = get_oauth_provider()
        if oauth_provider and oauth_provider.is_authenticated():
            oauth_provider.show_logout_button_sidebar()
