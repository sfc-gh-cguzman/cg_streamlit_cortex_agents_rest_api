"""
Configuration UI Components for Cortex Agent Application

This module provides the main configuration interface including agent selection,
sample questions, conversation management, and advanced settings.
"""

import streamlit as st
from config import ASSISTANT_AVATAR, ENABLE_REGENERATE_BUTTON
from modules.config.session_state import ensure_session_state_defaults, get_session_manager
from modules.authentication import get_auth_token_for_agents  
from modules.snowflake import get_available_agents, format_sample_questions_for_ui
from modules.threads import delete_thread
from modules.logging import get_logger
from modules.ui.debug_interface import clear_debug_session_state

logger = get_logger()


def config_options(snowflake_config, snowflake_client):
    """
    Configure sidebar options, sample questions, and settings in session state.
    
    Args:
        snowflake_config: SnowflakeConfig instance with connection details
        snowflake_client: ExternalSnowflakeClient instance for database operations
        
    Returns:
        (bool) True if 'Start New Conversation' was pressed.
    """
    ensure_session_state_defaults()
    session_manager = get_session_manager()
    
    # --- Agent Selection ---
    with st.sidebar:
        with st.container():
            st.subheader(f"{ASSISTANT_AVATAR} Cortex Agent Selection")
            
            # Get available agents
            try:
                with st.spinner(":material/explore: Discovering available agents..."):
                    auth_token = get_auth_token_for_agents(snowflake_config, snowflake_client)
                    # Get session for SQL-based discovery (discovers ALL agents in account)
                    session = snowflake_client.get_session() if hasattr(snowflake_client, 'get_session') else None
                    available_agents = get_available_agents(
                        snowflake_config.account, 
                        auth_token, 
                        snowflake_config.ssl_verify,
                        _session=session
                    )
                
                if available_agents:
                    # Create agent options for dropdown
                    agent_options = []
                    agent_mapping = {}
                    
                    for agent in available_agents:
                        display_name = f"{agent['display_name']} ({agent['tools_count']} tools)"
                        agent_options.append(display_name)
                        agent_mapping[display_name] = agent
                    
                    # Initialize selectbox session state if needed
                    if "selected_agent_display" not in st.session_state and agent_options:
                        st.session_state.selected_agent_display = agent_options[0]
                    
                    # Ensure the selectbox has a valid option selected
                    if st.session_state.get("selected_agent_display") not in agent_options and agent_options:
                        st.session_state.selected_agent_display = agent_options[0]
                    
                    selected_agent_display = st.selectbox(
                        "Select Cortex Agent",
                        agent_options,
                        key="selected_agent_display",
                        help="Choose the Cortex Agent to interact with.",
                        label_visibility="collapsed"
                    )
                    
                    # Update the selected agent when selectbox changes
                    if selected_agent_display and selected_agent_display in agent_mapping:
                        selected_agent = agent_mapping[selected_agent_display]
                        # Only update if it's actually different to avoid unnecessary re-runs
                        if (session_manager.get_selected_agent() is None or 
                            session_manager.get_selected_agent().get('name') != selected_agent.get('name')):
                            
                            # Clear conversation when switching to a different agent
                            if session_manager.has_selected_agent():
                                # Delete existing thread and create new one
                                if session_manager.get_thread_id():
                                    delete_thread(session_manager.get_thread_id(), snowflake_config, snowflake_client)
                                session_manager.thread_state.create_new_thread = True
                                session_manager.clear_thread_messages()
                                session_manager.agent_state.suggestions = []
                                session_manager.agent_state.active_suggestion = None
                                
                                # Clear request-scoped agent data
                                session_manager.agent_state.request_sample_questions.clear()
                                session_manager.agent_state.request_suggestions.clear()
                                session_manager.agent_state.request_prompts.clear()
                                session_manager.debug_state.api_history = []
                                
                                # Clear debug JSON session state when switching agents
                                clear_debug_session_state()
                            
                            session_manager.set_selected_agent(selected_agent)
                        
                else:
                    st.error(":material/error: No accessible agents found in your account")
                    session_manager.clear_selected_agent()
                    
            except Exception as e:
                st.error(f":material/error: Error loading agents: {str(e)}")
                session_manager.clear_selected_agent()

    # Note: Always using streaming mode for consistent experience and debug functionality

    # Start New Conversation Button with Static Gradient
    with st.sidebar:
        # Custom CSS for static gradient background on the Start New Conversation button
        st.markdown("""
        <style>
        /* Animated glowing border keyframes using Catppuccin Mocha colors */
        @keyframes glowingBorder {
            0% { background-position: 0 0; }
            50% { background-position: 400% 0; }
            100% { background-position: 0 0; }
        }
        
        /* Target the button using multiple possible selectors within the key container */
        .st-key-start_over_btn button,
        .st-key-start_over_btn > div > button,
        .st-key-start_over_btn div[data-testid="stButton"] button,
        .st-key-start_over_btn [role="button"],
        .st-key-start_over_btn * button {
            background: linear-gradient(-45deg, #cba6f7, #89b4fa, #74c7ec, #94e2d5) !important;
            border: none !important;
            color: #1a1a1a !important;
            font-weight: 700 !important;
            text-shadow: 0 1px 2px rgba(255, 255, 255, 0.3) !important;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
            position: relative !important;
            z-index: 0 !important;
            border-radius: 10px !important;
            cursor: pointer !important;
            transition: transform 0.2s ease-in-out !important;
        }
        
        /* Add lift effect on hover */
        .st-key-start_over_btn button:hover,
        .st-key-start_over_btn > div > button:hover,
        .st-key-start_over_btn div[data-testid="stButton"] button:hover,
        .st-key-start_over_btn [role="button"]:hover,
        .st-key-start_over_btn * button:hover {
            transform: translateY(-2px) !important;
        }
        
        /* Animated glowing border - hidden by default, more subtle */
        .st-key-start_over_btn button:before,
        .st-key-start_over_btn > div > button:before,
        .st-key-start_over_btn div[data-testid="stButton"] button:before,
        .st-key-start_over_btn [role="button"]:before,
        .st-key-start_over_btn * button:before {
            content: '' !important;
            background: linear-gradient(45deg, #cba6f7, #89b4fa, #74c7ec, #94e2d5, #89dceb, #f5c2e7, #cba6f7, #89b4fa, #74c7ec, #94e2d5) !important;
            position: absolute !important;
            top: -1px !important;
            left: -1px !important;
            background-size: 300% 300% !important;
            z-index: -1 !important;
            filter: blur(3px) !important;
            width: calc(100% + 2px) !important;
            height: calc(100% + 2px) !important;
            opacity: 0 !important;
            transition: opacity 0.4s ease-in-out !important;
            border-radius: 10px !important;
        }
        
        /* Apply animation and show border when hovering - more subtle */
        .st-key-start_over_btn button:hover:before,
        .st-key-start_over_btn > div > button:hover:before,
        .st-key-start_over_btn div[data-testid="stButton"] button:hover:before,
        .st-key-start_over_btn [role="button"]:hover:before,
        .st-key-start_over_btn * button:hover:before {
            opacity: 0.6 !important;
            animation: glowingBorder 5s linear infinite !important;
        }
        
        /* Background layer to maintain button appearance */
        .st-key-start_over_btn button:after,
        .st-key-start_over_btn > div > button:after,
        .st-key-start_over_btn div[data-testid="stButton"] button:after,
        .st-key-start_over_btn [role="button"]:after,
        .st-key-start_over_btn * button:after {
            z-index: -1 !important;
            content: '' !important;
            position: absolute !important;
            width: 100% !important;
            height: 100% !important;
            background: linear-gradient(-45deg, #cba6f7, #89b4fa, #74c7ec, #94e2d5) !important;
            left: 0 !important;
            top: 0 !important;
            border-radius: 10px !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        clear_conversation = st.button(":material/forum: Start New Conversation", key="start_over_btn", 
                                     help="Clear the conversation and start fresh.",
                                     use_container_width=True,
                                     type="primary")
        
        # Regenerate Last Response Button
        regenerate_clicked = render_regenerate_button_sidebar()
            
    st.sidebar.divider()

    # --- Examples Section ---
    st.sidebar.subheader(":material/chat: Ask me questions like...")
    
    # Get sample questions from selected agent
    sample_questions_list = []
    if session_manager.has_selected_agent():
        selected_agent = session_manager.get_selected_agent()
        agent_sample_questions = selected_agent.get('sample_questions', [])
        
        if agent_sample_questions:
            sample_questions_list = format_sample_questions_for_ui(agent_sample_questions)
            
            for question_obj in sample_questions_list:
                # Clean sample question button without emoji numbers
                if st.sidebar.button(
                    question_obj['text'], 
                    key=question_obj['key'],
                    help="Click to use this sample question",
                    use_container_width=True
                ):
                    session_manager.agent_state.active_sample_question = question_obj['text']
        else:
            st.sidebar.info(":material/info: No sample questions configured for this agent")
    else:
        st.sidebar.warning(":material/warning: Please select an agent to see sample questions")

    st.sidebar.divider()

    # --- Advanced Section (at bottom) ---
    with st.sidebar:
        with st.expander(":material/engineering: Advanced", expanded=False):
            # Application Description
            st.markdown(
                """This application allows you to interact with **any Cortex Agent** in your Snowflake account. 
                Demonstrating how you can integrate :blue[**Snowflake's**] **Agentic AI Experience** within any external application using :blue[**[Cortex Agent REST API](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-rest-api)**]."""
            )
            
            st.divider()
            
            # Debug Mode Toggle
            # Note: Debug mode initialization handled by SessionStateManager
            
            # Store current debug mode state to prevent infinite loops
            current_debug_mode = session_manager.is_debug_mode()
            
            new_debug_mode = st.toggle(
                "Activate Debug Mode", 
                value=current_debug_mode,
                help="Show API payloads and responses for debugging."
            )
            
            # Update log level if debug mode changed (avoid infinite loop)
            if new_debug_mode != current_debug_mode:
                if new_debug_mode:
                    session_manager.enable_debug_mode()
                else:
                    session_manager.disable_debug_mode()
                from modules.logging import update_log_level
                update_log_level()
                # Note: Removed st.rerun() to prevent infinite loop - state change will trigger natural rerun
            
            st.divider()
            
            # Refresh Agents Button
            if st.button(
                ":material/refresh: Refresh Agents", 
                help="Clear the agent cache and reload available agents from Snowflake",
                use_container_width=True
            ):
                # Clear the agent cache
                get_available_agents.clear()
                # Clear selected agent to force re-selection
                session_manager.clear_selected_agent()
                st.success("Agent cache cleared! The agent list will refresh on next load.")
                st.rerun()
            
            # Clear Application State Button
            if st.button(
                ":material/delete_sweep: Clear Application State",
                help="WARNING: Completely resets the application by clearing ALL data including conversation history, selected agent, citations, debug state, captured logs, and module caches. This cannot be undone!",
                use_container_width=True,
                type="secondary"
            ):
                # Log session state before clearing for validation
                keys_before = list(st.session_state.keys())
                logger.info(f"Clearing all application state - Found {len(keys_before)} session keys to delete")
                logger.debug(f"Session state keys before clearing: {keys_before}")
                
                # Step 1: Clear module-level caches first
                try:
                    # Clear agent discovery cache
                    get_available_agents.clear()
                    
                    # Clear file management caches
                    from modules.files.management import download_file_from_stage, get_presigned_url, get_pdf
                    download_file_from_stage.clear()
                    get_presigned_url.clear()
                    get_pdf.clear()
                    
                    # Clear text processing caches
                    from modules.utils.text_processing import bot_retrieve_sql_results
                    bot_retrieve_sql_results.clear()
                    
                    logger.info("Cleared all module-level caches (agents, files, SQL results)")
                except Exception as e:
                    logger.warning(f"Failed to clear module caches: {e}")
                
                # Step 2: Clear comprehensive session manager state
                try:
                    session_manager = get_session_manager()
                    session_manager.clear_debug_state()
                    session_manager.clear_response_content()
                    session_manager.clear_tool_citations()
                    session_manager.clear_thread_messages()
                    session_manager.clear_thread_id()
                    session_manager.clear_selected_agent()
                    
                    # Clear thread-based storage
                    current_thread_id = session_manager.get_thread_id()
                    if current_thread_id:
                        session_manager.clear_thread_citations(current_thread_id)
                        session_manager.clear_thread_tool_results(current_thread_id)
                    
                    # Clear all thread data by resetting the storage completely
                    session_manager.tool_state.thread_citations.clear()
                    session_manager.tool_state.thread_tool_citations.clear()
                    session_manager.tool_state.thread_tool_results.clear()
                    session_manager.tool_state.current_thread_id = None
                    
                    session_manager.cleanup_memory()
                    logger.info("Cleared comprehensive session manager state and thread storage")
                except Exception as e:
                    logger.warning(f"Failed to clear session manager state: {e}")
                
                # Step 3: Clear citation utils state
                try:
                    from modules.citations.utils import clear_citation_state
                    clear_citation_state()
                    logger.info("Cleared citation utility state")
                except Exception as e:
                    logger.warning(f"Failed to clear citation state: {e}")
                
                # Step 4: Clear debug interface state
                try:
                    clear_debug_session_state()
                    logger.info("Cleared debug interface state")
                except Exception as e:
                    logger.warning(f"Failed to clear debug interface state: {e}")
                
                # Step 5: Brute force clear any remaining session state keys
                keys_to_delete = list(st.session_state.keys())
                deleted_count = 0
                failed_deletions = []
                
                for key in keys_to_delete:
                    try:
                        del st.session_state[key]
                        deleted_count += 1
                    except KeyError as e:
                        failed_deletions.append(key)
                        logger.warning(f"Failed to delete session state key: {key} - {e}")
                
                # Verify clearing was successful
                keys_after = list(st.session_state.keys())
                logger.info(f"Application state cleared - Deleted: {deleted_count}, Failed: {len(failed_deletions)}, Remaining: {len(keys_after)}")
                
                if keys_after:
                    logger.warning(f"Remaining keys after clear: {keys_after}")
                    st.warning(f"Application state partially cleared. {len(keys_after)} keys remain: {keys_after[:5]}{'...' if len(keys_after) > 5 else ''}")
                else:
                    logger.info("All application state successfully cleared")
                    clear_items = ["conversation history", "selected agent", "debug state", "captured logs", "citations", "module caches", "tool results"]
                    st.success(f"All application state cleared! This includes: {', '.join(clear_items)}. Application will completely reinitialize.")
                
                st.rerun()
            
            # Debug: Show current session state keys (when debug mode is on)
            if session_manager.is_debug_mode():
                st.divider()
                with st.expander("Session State Debug Info", expanded=False):
                    current_keys = list(st.session_state.keys())
                    st.write(f"**Session State Keys ({len(current_keys)}):**")
                    if current_keys:
                        # Group keys by category for better readability
                        categories = {
                            "Citations": [k for k in current_keys if 'citation' in k.lower()],
                            "Threads": [k for k in current_keys if 'thread' in k.lower()],
                            "Debug": [k for k in current_keys if 'debug' in k.lower() or 'payload' in k.lower()],
                            "UI State": [k for k in current_keys if any(x in k.lower() for x in ['selected', 'expanded', 'collapsed'])],
                            "Other": [k for k in current_keys if not any(cat in k.lower() for cat in ['citation', 'thread', 'debug', 'payload', 'selected', 'expanded', 'collapsed'])]
                        }
                        
                        for category, keys in categories.items():
                            if keys:
                                st.write(f"**{category}:** {', '.join(keys)}")
                    else:
                        st.write("*No session state keys found*")
            
            # Agent Details (if agent is selected)
            if session_manager.has_selected_agent():
                selected_agent = session_manager.get_selected_agent()
                
                st.divider()
                st.markdown("**Agent Details**")
                st.markdown(f"**Database**: {selected_agent['database']}")
                st.markdown(f"**Schema**: {selected_agent['schema']}")
                st.markdown(f"**Owner**: {selected_agent['owner']}")
                # Show available tools
                tools = selected_agent.get('full_spec', {}).get('tools', [])
                if tools:
                    tool_names = [tool.get('tool_spec', {}).get('name', 'Unknown') for tool in tools]
                    st.markdown(f"**Tools**: {', '.join(tool_names)}")
                else:
                    st.markdown("**Tools**: None")
                
                # Show orchestration model from agent spec
                orchestration_model = selected_agent.get('models', {}).get('orchestration', 'auto')
                st.markdown(f"**Model**: {orchestration_model}")
    
    return clear_conversation, regenerate_clicked


def render_regenerate_button_sidebar() -> bool:
    """
    Render the regenerate button in the sidebar if regeneration is available.
    
    Returns:
        bool: True if regenerate button was clicked, False otherwise
    """
    if not ENABLE_REGENERATE_BUTTON:
        return False
        
    session_manager = get_session_manager()
    
    if session_manager.can_regenerate_last_message():
        last_message = session_manager.get_last_user_message()
        preview = last_message[:40] + "..." if len(last_message) > 40 else last_message
        
        regenerate_clicked = st.button(
            ":material/refresh: Regenerate Last Response",
            help=f"Regenerate response for: '{preview}'",
            use_container_width=True,
            type="secondary",
            key="regenerate_sidebar_btn"
        )
        
        if regenerate_clicked:
            return True
    
    return False


def display_agent_status():
    """Display agent comment/model info and warning when no agent is selected"""
    session_manager = get_session_manager()
    if session_manager.has_selected_agent():
        selected_agent = session_manager.get_selected_agent()
        
        # Display agent comment (often contains model info) without redundant agent name
        agent_comment = selected_agent.get('comment')
        if agent_comment:
            st.info(f":material/auto_awesome: {agent_comment}")
        
        # Also display model info from agent spec if available
        models = selected_agent.get('models', {})
        if models:
            orchestration_model = models.get('orchestration', 'auto')
            if orchestration_model and orchestration_model != 'auto':
                st.caption(f"Model: {orchestration_model}")
    else:
        st.warning(":material/warning: **No Agent Selected** - Please select a Cortex Agent from the sidebar to begin.")


def clear_conversation_state(snowflake_config, snowflake_client):
    """Clear conversation state and start fresh thread (no API deletion)"""
    session_manager = get_session_manager()
    logger = get_logger()
    
    # Get current thread ID before clearing for comprehensive cleanup
    current_thread_id = session_manager.get_thread_id()
    
    # Clear all conversation-related session state
    session_manager.clear_thread_messages()
    session_manager.agent_state.suggestions = []
    session_manager.agent_state.active_suggestion = None
    
    # Clear request-scoped agent data
    session_manager.agent_state.request_sample_questions.clear()
    session_manager.agent_state.request_suggestions.clear()
    session_manager.agent_state.request_prompts.clear()
    session_manager.debug_state.api_history = []
    
    # Clear regeneration state
    session_manager.disable_regeneration()
    session_manager.thread_state.last_user_message = None
    session_manager.thread_state.last_user_timestamp = None
    session_manager.thread_state.last_message_agent_id = None
    
    # Clear table and chart data for new conversation
    session_manager.clear_response_content()
    
    # Clear any pending messages that might redisplay
    if "pending_assistant_message" in st.session_state:
        del st.session_state.pending_assistant_message
    
    # Clear thread_id to force creation of new thread
    session_manager.clear_thread_id()
    
    # COMPREHENSIVE THREAD DATA CLEANUP: Clear all thread-specific data
    if current_thread_id:
        # Clear thread-specific citations and tool results
        session_manager.clear_thread_citations(current_thread_id)
        session_manager.clear_thread_tool_results(current_thread_id)
        logger.debug(f"Cleared thread-specific data for thread: {current_thread_id}")
    
    # Clear all thread storage completely for new conversation
    session_manager.tool_state.thread_citations.clear()
    session_manager.tool_state.thread_tool_citations.clear()
    session_manager.tool_state.thread_tool_results.clear()
    session_manager.tool_state.current_thread_id = None
    
    # Reset request-scoped citation state
    session_manager.reset_request_citations()
    
    # Flag to create new thread on next interaction
    session_manager.thread_state.create_new_thread = True
    
    # Clear debug JSON session state when starting over
    clear_debug_session_state()
    
    # Clear citation tracking for new conversation
    from modules.citations.utils import clear_citation_state
    clear_citation_state()
    
    # Force immediate Streamlit rerun to refresh UI
    logger.info("Complete conversation state cleared - all thread data removed, triggering UI refresh")
    st.rerun()


def validate_agent_selection():
    """Validate that an agent is selected before proceeding"""
    session_manager = get_session_manager()
    if not session_manager.has_selected_agent():
        st.error(":material/error: Please select a Cortex Agent from the sidebar before asking questions.")
        return False
    return True
