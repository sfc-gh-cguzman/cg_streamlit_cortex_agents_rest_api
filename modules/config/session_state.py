"""
Centralized Streamlit session state management for Cortex Agent application.

This module provides a comprehensive session state manager that organizes state
into logical categories and provides type-safe access methods.
"""
import streamlit as st
from typing import Optional, Dict, List, Any, Union
from dataclasses import dataclass, field
from modules.logging import get_logger

logger = get_logger()

@dataclass
class AppConfigState:
    """Application configuration state."""
    use_chat_history: bool = True
    summarize_with_chat_history: bool = True
    cortex_search: bool = True
    response_instruction: str = ""
    show_first_tool_use_only: bool = True
    debug_payload_response: bool = False
    # Authentication method: "oauth", "pat", "rsa", "password"
    auth_method: str = "auto"


@dataclass
class OAuthState:
    """OAuth authentication state for Okta integration."""
    # OAuth flow state
    oauth_state: Optional[str] = None
    code_verifier: Optional[str] = None
    
    # Tokens
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    
    # Token metadata
    token_expiry: Optional[float] = None
    auth_time: Optional[float] = None
    
    # User information
    user_info: Optional[Dict] = None
    user_email: Optional[str] = None
    
    # Snowflake session token (derived from OAuth token exchange)
    snowflake_token: Optional[str] = None
    snowflake_token_expiry: Optional[float] = None

@dataclass
class ThreadState:
    """Thread management state."""
    thread_id: Optional[str] = None
    thread_messages: List[Any] = field(default_factory=list)  # Changed to Any to support Message objects
    create_new_thread: bool = False
    origin_application: str = "CortexAgentDemo"  # Store origin_application since API doesn't return it in retrieval
    last_user_message: Optional[str] = None
    last_user_timestamp: Optional[str] = None
    last_message_agent_id: Optional[str] = None  # Track which agent was used for last message
    can_regenerate: bool = False

@dataclass
class AgentState:
    """Agent selection and interaction state with proper scoping."""
    # Session-scoped (persists across threads and agents)
    selected_agent: Optional[Dict] = None
    
    # Thread-scoped (persists across requests within conversation)  
    suggestions: List[str] = field(default_factory=list)
    
    # Request-scoped (isolated per request within thread)
    request_sample_questions: Dict[str, str] = field(default_factory=dict)  # request_id -> question
    request_suggestions: Dict[str, str] = field(default_factory=dict)  # request_id -> suggestion
    request_prompts: Dict[str, str] = field(default_factory=dict)  # request_id -> prompt
    
    # Legacy fields (deprecated - use request-scoped methods)
    active_sample_question: Optional[str] = None
    active_suggestion: Optional[str] = None
    suggested_prompt: Optional[str] = None

@dataclass
class ResponseState:
    """Current response processing state with request-scoped isolation."""
    # Request-scoped storage (isolated per request within thread)
    request_tables: Dict[str, List[Dict]] = field(default_factory=dict)  # request_id -> tables
    request_charts: Dict[str, List[Dict]] = field(default_factory=dict)  # request_id -> charts
    request_table_referenced: Dict[str, bool] = field(default_factory=dict)  # request_id -> bool
    request_tool_ids: Dict[str, List[str]] = field(default_factory=dict)  # request_id -> tool_ids
    
    # Current request tracking
    current_response_id: Optional[str] = None
    current_assistant_message_id: Optional[int] = None  # Message ID from Snowflake API metadata events
    
    # Legacy fields (deprecated - use request-scoped methods)
    current_response_tables: List[Dict] = field(default_factory=list)
    current_response_charts: List[Dict] = field(default_factory=list)
    table_referenced_in_response: bool = False
    referenced_tool_ids: List[str] = field(default_factory=list)

@dataclass
class ToolState:
    """Tool execution and result state with thread-based isolation."""
    # Thread-based citation storage (persistent across requests)
    thread_citations: Dict[str, List[Dict]] = field(default_factory=dict)
    thread_tool_citations: Dict[str, Dict[str, Dict]] = field(default_factory=dict)
    
    # Thread-based tool results storage (persistent across requests in conversation)
    thread_tool_results: Dict[str, Dict[str, Dict]] = field(default_factory=dict)
    
    # Request-based citation state (resets each request within thread)
    current_request_citation_mapping: Dict[str, int] = field(default_factory=dict)
    current_request_citation_counter: int = 0
    
    # Current active thread state
    current_thread_id: Optional[str] = None
    
    # Legacy compatibility (deprecated - use thread-based methods)
    tool_result_citations: Dict[str, Dict] = field(default_factory=dict)
    citation_id_mapping: Dict[str, Any] = field(default_factory=dict)
    current_tool_inputs: Dict[str, Dict] = field(default_factory=dict)
    streaming_citations: List[Dict] = field(default_factory=list)
    citation_counter: int = 0

@dataclass
class DebugState:
    """Debug and development state with request-scoped isolation."""
    # Request-scoped debug data (isolated per request within thread)
    request_debug_bodies: Dict[str, Dict] = field(default_factory=dict)  # request_id -> debug_body
    request_debug_responses: Dict[str, Dict] = field(default_factory=dict)  # request_id -> debug_response
    request_debug_json_str: Dict[str, str] = field(default_factory=dict)  # request_id -> json_str
    request_event_counts: Dict[str, int] = field(default_factory=dict)  # request_id -> event_count
    request_event_types: Dict[str, List[str]] = field(default_factory=dict)  # request_id -> event_types
    
    # Thread-scoped debug data (persistent across requests in conversation)
    api_history: List[Dict] = field(default_factory=list)
    
    # Legacy fields (deprecated - use request-scoped methods)
    debug_request_body: Dict = field(default_factory=dict)
    debug_consolidated_response: Dict = field(default_factory=dict)
    debug_request_json_str: str = ""
    debug_response_json_str: str = ""
    debug_event_count: int = 0
    debug_event_types: List[str] = field(default_factory=list)

class SessionStateManager:
    """Centralized session state manager with type-safe access methods."""

    def __init__(self):
        """Initialize session state manager and ensure defaults are set."""
        self.ensure_defaults()

    def ensure_defaults(self):
        """Ensure all required session state keys are set with default values."""
        # Initialize all state categories
        if 'app_config' not in st.session_state:
            st.session_state.app_config = AppConfigState()
        if 'thread_state' not in st.session_state:
            st.session_state.thread_state = ThreadState()
        if 'agent_state' not in st.session_state:
            st.session_state.agent_state = AgentState()
        if 'response_state' not in st.session_state:
            st.session_state.response_state = ResponseState()
        if 'tool_state' not in st.session_state:
            st.session_state.tool_state = ToolState()
        if 'debug_state' not in st.session_state:
            st.session_state.debug_state = DebugState()
        if 'oauth_state' not in st.session_state:
            st.session_state.oauth_state = OAuthState()
        
        # One-time migration of any existing legacy keys
        self._migrate_legacy_state()
        
        logger.debug("Session state defaults ensured with centralized manager")
    
    def _migrate_legacy_state(self):
        """One-time migration of existing session state keys to new centralized structure."""
        migrations = {
            # App config migrations
            'use_chat_history': ('app_config', 'use_chat_history'),
            'summarize_with_chat_history': ('app_config', 'summarize_with_chat_history'),
            'cortex_search': ('app_config', 'cortex_search'),
            'response_instruction': ('app_config', 'response_instruction'),
            'show_first_tool_use_only': ('app_config', 'show_first_tool_use_only'),
            'debug_payload_response': ('app_config', 'debug_payload_response'),
            
            # Thread state migrations
            'thread_id': ('thread_state', 'thread_id'),
            'thread_messages': ('thread_state', 'thread_messages'),
            'create_new_thread': ('thread_state', 'create_new_thread'),
            
            # Agent state migrations
            'selected_agent': ('agent_state', 'selected_agent'),
            'active_sample_question': ('agent_state', 'active_sample_question'),
            'suggestions': ('agent_state', 'suggestions'),
            'active_suggestion': ('agent_state', 'active_suggestion'),
            'suggested_prompt': ('agent_state', 'suggested_prompt'),
            'request_sample_questions': ('agent_state', 'request_sample_questions'),
            'request_suggestions': ('agent_state', 'request_suggestions'),
            'request_prompts': ('agent_state', 'request_prompts'),
            
            # Response state migrations
            'current_response_tables': ('response_state', 'current_response_tables'),
            'current_response_charts': ('response_state', 'current_response_charts'),
            'table_referenced_in_response': ('response_state', 'table_referenced_in_response'),
            'referenced_tool_ids': ('response_state', 'referenced_tool_ids'),
            'current_response_id': ('response_state', 'current_response_id'),
            'request_tables': ('response_state', 'request_tables'),
            'request_charts': ('response_state', 'request_charts'),
            'request_table_referenced': ('response_state', 'request_table_referenced'),
            'request_tool_ids': ('response_state', 'request_tool_ids'),
            
            # Tool state migrations
            'tool_result_citations': ('tool_state', 'tool_result_citations'),
            'citation_id_mapping': ('tool_state', 'citation_id_mapping'),
            'current_tool_inputs': ('tool_state', 'current_tool_inputs'),
            
            # Debug state migrations
            'debug_request_body': ('debug_state', 'debug_request_body'),
            'debug_consolidated_response': ('debug_state', 'debug_consolidated_response'),
            'debug_request_json_str': ('debug_state', 'debug_request_json_str'),
            'debug_response_json_str': ('debug_state', 'debug_response_json_str'),
            'debug_event_count': ('debug_state', 'debug_event_count'),
            'debug_event_types': ('debug_state', 'debug_event_types'),
            'api_history': ('debug_state', 'api_history'),
            'request_debug_bodies': ('debug_state', 'request_debug_bodies'),
            'request_debug_responses': ('debug_state', 'request_debug_responses'),
            'request_debug_json_str': ('debug_state', 'request_debug_json_str'),
            'request_event_counts': ('debug_state', 'request_event_counts'),
            'request_event_types': ('debug_state', 'request_event_types'),
        }
        
        # One-time migration of existing values to structured format
        for legacy_key, (category, new_key) in migrations.items():
            if legacy_key in st.session_state:
                value = st.session_state[legacy_key]
                setattr(st.session_state[category], new_key, value)
                # Remove legacy key after migration
                del st.session_state[legacy_key]
                logger.debug(f"Migrated {legacy_key} -> {category}.{new_key}")
    
    # State Category Access Methods
    @property
    def app_config(self) -> AppConfigState:
        """Get application configuration state."""
        return st.session_state.app_config

    @property
    def thread_state(self) -> ThreadState:
        """Get thread management state."""
        return st.session_state.thread_state
    
    @property
    def agent_state(self) -> AgentState:
        """Get agent selection and interaction state."""
        return st.session_state.agent_state
    
    @property
    def response_state(self) -> ResponseState:
        """Get current response processing state."""
        return st.session_state.response_state
    
    @property
    def tool_state(self) -> ToolState:
        """Get tool execution and result state."""
        return st.session_state.tool_state
    
    @property
    def debug_state(self) -> DebugState:
        """Get debug and development state."""
        return st.session_state.debug_state
    
    @property
    def oauth_state(self) -> OAuthState:
        """Get OAuth authentication state."""
        return st.session_state.oauth_state
    
    # OAuth Methods
    def is_oauth_authenticated(self) -> bool:
        """Check if user is authenticated via OAuth."""
        import time
        if not self.oauth_state.access_token:
            return False
        
        # Check token expiry
        if self.oauth_state.token_expiry and time.time() > self.oauth_state.token_expiry:
            return False
        
        return True
    
    def get_oauth_access_token(self) -> Optional[str]:
        """Get OAuth access token if authenticated."""
        if self.is_oauth_authenticated():
            return self.oauth_state.access_token
        return None
    
    def get_oauth_user_email(self) -> Optional[str]:
        """Get authenticated user's email from OAuth."""
        if self.oauth_state.user_info:
            return self.oauth_state.user_info.get('email')
        return self.oauth_state.user_email
    
    def set_oauth_tokens(self, access_token: str, refresh_token: Optional[str] = None, 
                         id_token: Optional[str] = None, expires_in: int = 3600):
        """Set OAuth tokens and calculate expiry."""
        import time
        self.oauth_state.access_token = access_token
        self.oauth_state.refresh_token = refresh_token
        self.oauth_state.id_token = id_token
        self.oauth_state.auth_time = time.time()
        self.oauth_state.token_expiry = time.time() + expires_in
        logger.debug("OAuth tokens updated")
    
    def set_oauth_user_info(self, user_info: Dict):
        """Set OAuth user information."""
        self.oauth_state.user_info = user_info
        self.oauth_state.user_email = user_info.get('email')
        logger.debug(f"OAuth user info set: {user_info.get('email', 'unknown')}")
    
    def clear_oauth_state(self):
        """Clear all OAuth authentication state."""
        self.oauth_state.oauth_state = None
        self.oauth_state.code_verifier = None
        self.oauth_state.access_token = None
        self.oauth_state.refresh_token = None
        self.oauth_state.id_token = None
        self.oauth_state.token_expiry = None
        self.oauth_state.auth_time = None
        self.oauth_state.user_info = None
        self.oauth_state.user_email = None
        self.oauth_state.snowflake_token = None
        self.oauth_state.snowflake_token_expiry = None
        logger.debug("OAuth state cleared")
    
    def get_authentication_method(self) -> str:
        """Get the current authentication method in use."""
        if self.is_oauth_authenticated():
            return "oauth"
        return self.app_config.auth_method
    
    # App Configuration Methods
    def is_debug_mode(self) -> bool:
        """Check if debug mode is enabled."""
        return self.app_config.debug_payload_response
    
    def enable_debug_mode(self):
        """Enable debug mode."""
        self.app_config.debug_payload_response = True
        logger.debug("Debug mode enabled")
    
    def disable_debug_mode(self):
        """Disable debug mode."""
        self.app_config.debug_payload_response = False
        logger.debug("Debug mode disabled")
    
    # Agent State Methods
    def get_selected_agent(self) -> Optional[Dict]:
        """Get currently selected agent."""
        return self.agent_state.selected_agent
    
    def set_selected_agent(self, agent: Dict):
        """Set currently selected agent."""
        old_agent_name = self.agent_state.selected_agent.get('name') if self.agent_state.selected_agent else None
        new_agent_name = agent.get('name', 'unknown')
        
        self.agent_state.selected_agent = agent
        logger.debug(f"Selected agent: {new_agent_name}")
        
        # Clear regeneration state when switching to a different agent
        if old_agent_name and old_agent_name != new_agent_name:
            self.clear_regeneration_on_agent_change()
            logger.debug(f"Cleared regeneration state when switching from '{old_agent_name}' to '{new_agent_name}'")
    
    def clear_selected_agent(self):
        """Clear currently selected agent."""
        self.agent_state.selected_agent = None
        logger.debug("Cleared selected agent")
    
    def has_selected_agent(self) -> bool:
        """Check if an agent is currently selected."""
        return self.agent_state.selected_agent is not None
    
    # Request-Scoped Agent Methods
    def set_request_sample_question(self, question: str, request_id: Optional[str] = None):
        """Set active sample question for a specific request."""
        target_request = request_id or self.response_state.current_response_id or 'unknown'
        self.agent_state.request_sample_questions[target_request] = question
        
        # Update legacy for compatibility
        self.agent_state.active_sample_question = question
        
        logger.debug(f"Set sample question for request {target_request}: {question[:50]}...")
    
    def get_request_sample_question(self, request_id: Optional[str] = None) -> Optional[str]:
        """Get active sample question for a specific request."""
        target_request = request_id or self.response_state.current_response_id
        if not target_request:
            return self.agent_state.active_sample_question  # Fallback to legacy
        return self.agent_state.request_sample_questions.get(target_request)
    
    def set_request_suggestion(self, suggestion: str, request_id: Optional[str] = None):
        """Set active suggestion for a specific request."""
        target_request = request_id or self.response_state.current_response_id or 'unknown'
        self.agent_state.request_suggestions[target_request] = suggestion
        
        # Update legacy for compatibility
        self.agent_state.active_suggestion = suggestion
        
        logger.debug(f"Set suggestion for request {target_request}: {suggestion[:50]}...")
    
    def set_request_prompt(self, prompt: str, request_id: Optional[str] = None):
        """Set suggested prompt for a specific request."""
        target_request = request_id or self.response_state.current_response_id or 'unknown'
        self.agent_state.request_prompts[target_request] = prompt
        
        # Update legacy for compatibility
        self.agent_state.suggested_prompt = prompt
        
        logger.debug(f"Set suggested prompt for request {target_request}: {prompt[:50]}...")
    
    def clear_request_agent_data(self, request_id: Optional[str] = None):
        """Clear agent data for a specific request."""
        target_request = request_id or self.response_state.current_response_id
        if not target_request:
            return
        
        self.agent_state.request_sample_questions.pop(target_request, None)
        self.agent_state.request_suggestions.pop(target_request, None)
        self.agent_state.request_prompts.pop(target_request, None)
        
        logger.debug(f"Cleared agent data for request {target_request}")
    
    # Thread State Methods
    def get_thread_id(self) -> Optional[str]:
        """Get current thread ID."""
        return self.thread_state.thread_id
    
    def set_thread_id(self, thread_id: str):
        """Set current thread ID and active thread for citations."""
        self.thread_state.thread_id = thread_id
        self.set_active_thread(thread_id)  # Also set as active thread for citations
        logger.debug(f"Set thread ID: {thread_id}")
    
    def clear_thread_id(self):
        """Clear current thread ID."""
        self.thread_state.thread_id = None
        logger.debug("Cleared thread ID")
    
    def get_thread_messages(self) -> List[Any]:
        """Get thread messages (Message objects)."""
        return self.thread_state.thread_messages
    
    def add_thread_message(self, message: Any):
        """Add a message to the thread (Message object with processed content)."""
        # Message IDs are provided by the Snowflake API, not generated client-side
        # The ID will be set from API responses (metadata events for streaming)
        
        self.thread_state.thread_messages.append(message)
        logger.debug(f"Added message to thread: role={getattr(message, 'role', 'unknown')}, id={getattr(message, 'id', 'not_set')}, processed={getattr(message, 'is_processed', False)}")
    
    def clear_thread_messages(self):
        """Clear all thread messages."""
        self.thread_state.thread_messages.clear()
        logger.debug("Cleared thread messages")
    
    # Regeneration State Methods
    def set_last_user_message(self, message: str):
        """Store the last user message for potential regeneration."""
        import pandas as pd
        self.thread_state.last_user_message = message
        self.thread_state.last_user_timestamp = pd.Timestamp.now().strftime('%H:%M:%S')
        
        # Store the current agent ID to ensure regeneration only works with same agent
        if self.has_selected_agent():
            agent_id = self.get_selected_agent().get('name', 'unknown')
            self.thread_state.last_message_agent_id = agent_id
            logger.debug(f"Set last user message for agent '{agent_id}': {message[:50]}...")
        else:
            self.thread_state.last_message_agent_id = None
            logger.debug(f"Set last user message (no agent selected): {message[:50]}...")
    
    def enable_regeneration(self):
        """Enable regeneration after successful assistant response."""
        self.thread_state.can_regenerate = True
        logger.info(f"Enabled regeneration capability - last_message: {self.thread_state.last_user_message is not None}")
    
    def disable_regeneration(self):
        """Disable regeneration during new message processing."""
        self.thread_state.can_regenerate = False
        logger.debug("Disabled regeneration capability")
    
    def can_regenerate_last_message(self) -> bool:
        """Check if regeneration is available with the same agent."""
        if not (self.thread_state.can_regenerate and 
                self.thread_state.last_user_message is not None):
            return False
        
        # Check if current agent matches the agent used for last message
        if not self.has_selected_agent():
            return False
            
        current_agent_id = self.get_selected_agent().get('name', 'unknown')
        last_message_agent_id = self.thread_state.last_message_agent_id
        
        # Only allow regeneration if same agent is selected
        return current_agent_id == last_message_agent_id
    
    def get_last_user_message(self) -> Optional[str]:
        """Get the last user message for regeneration."""
        return self.thread_state.last_user_message
    
    def clear_regeneration_on_agent_change(self):
        """Clear regeneration state when agent changes."""
        self.thread_state.can_regenerate = False
        logger.debug("Cleared regeneration state due to agent change")
    
    # Response State Methods - Request-Scoped
    def add_request_table(self, table: Dict, request_id: Optional[str] = None):
        """Add a table to current request with proper scoping."""
        target_request = request_id or self.response_state.current_response_id or 'unknown'
        
        if target_request not in self.response_state.request_tables:
            self.response_state.request_tables[target_request] = []
        
        self.response_state.request_tables[target_request].append(table)
        
        # Update legacy field for backward compatibility
        self.response_state.current_response_tables.append(table)
        
        logger.debug(f"Added table to request {target_request}")
    
    def add_request_chart(self, chart: Dict, request_id: Optional[str] = None):
        """Add a chart to current request with proper scoping."""
        target_request = request_id or self.response_state.current_response_id or 'unknown'
        
        if target_request not in self.response_state.request_charts:
            self.response_state.request_charts[target_request] = []
        
        self.response_state.request_charts[target_request].append(chart)
        
        # Update legacy field for backward compatibility
        self.response_state.current_response_charts.append(chart)
        
        logger.debug(f"Added chart to request {target_request}")
    
    def get_request_tables(self, request_id: Optional[str] = None) -> List[Dict]:
        """Get tables for a specific request."""
        target_request = request_id or self.response_state.current_response_id
        if not target_request:
            return []
        return self.response_state.request_tables.get(target_request, [])
    
    def get_request_charts(self, request_id: Optional[str] = None) -> List[Dict]:
        """Get charts for a specific request."""
        target_request = request_id or self.response_state.current_response_id
        if not target_request:
            return []
        return self.response_state.request_charts.get(target_request, [])
    
    def set_request_table_referenced(self, referenced: bool = True, request_id: Optional[str] = None):
        """Mark that a table was referenced in the current request."""
        target_request = request_id or self.response_state.current_response_id or 'unknown'
        self.response_state.request_table_referenced[target_request] = referenced
        
        # Update legacy field for backward compatibility
        self.response_state.table_referenced_in_response = referenced
        
        logger.debug(f"Set table referenced={referenced} for request {target_request}")
    
    def add_request_tool_id(self, tool_id: str, request_id: Optional[str] = None):
        """Add a tool ID to the current request's referenced tools."""
        target_request = request_id or self.response_state.current_response_id or 'unknown'
        
        if target_request not in self.response_state.request_tool_ids:
            self.response_state.request_tool_ids[target_request] = []
        
        if tool_id not in self.response_state.request_tool_ids[target_request]:
            self.response_state.request_tool_ids[target_request].append(tool_id)
            
            # Update legacy field for backward compatibility
            if tool_id not in self.response_state.referenced_tool_ids:
                self.response_state.referenced_tool_ids.append(tool_id)
            
            logger.debug(f"Added tool ID {tool_id} to request {target_request}")
    
    def clear_request_content(self, request_id: Optional[str] = None):
        """Clear content for a specific request."""
        target_request = request_id or self.response_state.current_response_id
        if not target_request:
            logger.warning("No request ID available for clearing content")
            return
        
        # Clear request-scoped data
        self.response_state.request_tables.pop(target_request, None)
        self.response_state.request_charts.pop(target_request, None)
        self.response_state.request_table_referenced.pop(target_request, None)
        self.response_state.request_tool_ids.pop(target_request, None)
        
        logger.debug(f"Cleared request content for {target_request}")
    
    def clear_response_content(self):
        """Clear current response tables and charts (legacy method + request-scoped)."""
        # Clear legacy fields
        self.response_state.current_response_tables.clear()
        self.response_state.current_response_charts.clear()
        self.response_state.table_referenced_in_response = False
        self.response_state.referenced_tool_ids.clear()
        self.response_state.current_assistant_message_id = None
        
        # Clear current request content if available
        if self.response_state.current_response_id:
            self.clear_request_content(self.response_state.current_response_id)
    
    # Legacy methods for backward compatibility
    def add_response_table(self, table: Dict):
        """Legacy method - use add_request_table instead."""
        self.add_request_table(table)
    
    def add_response_chart(self, chart: Dict):
        """Legacy method - use add_request_chart instead."""
        self.add_request_chart(chart)
    
    def set_response_id(self, response_id: str):
        """Set current response ID."""
        self.response_state.current_response_id = response_id
        logger.debug(f"Set response ID: {response_id}")
    
    # Tool State Methods
    def add_tool_citation(self, tool_id: str, citation: Dict):
        """Add citation for a tool result."""
        self.tool_state.tool_result_citations[tool_id] = citation
        logger.debug(f"Added citation for tool: {tool_id}")
    
    def get_tool_citations(self) -> Dict[str, Dict]:
        """Get all tool result citations."""
        return self.tool_state.tool_result_citations
    
    def clear_tool_citations(self):
        """Clear all tool citations."""
        self.tool_state.tool_result_citations.clear()
        self.tool_state.citation_id_mapping.clear()
        logger.debug("Cleared tool citations")
    
    # Thread-Based Citation Methods
    def set_active_thread(self, thread_id: str):
        """Set the active thread for citation management."""
        self.tool_state.current_thread_id = thread_id
        logger.debug(f"Set active thread for citations: {thread_id}")
    
    def get_thread_citations(self, thread_id: Optional[str] = None) -> List[Dict]:
        """Get citations for a specific thread (or current active thread)."""
        target_thread = thread_id or self.tool_state.current_thread_id
        if not target_thread:
            return []
        return self.tool_state.thread_citations.get(target_thread, [])
    
    def add_thread_citation(self, citation: Dict, thread_id: Optional[str] = None):
        """Add citation to a specific thread (or current active thread)."""
        target_thread = thread_id or self.tool_state.current_thread_id
        if not target_thread:
            logger.warning("No active thread for citation")
            return
        
        if target_thread not in self.tool_state.thread_citations:
            self.tool_state.thread_citations[target_thread] = []
        
        self.tool_state.thread_citations[target_thread].append(citation)
        logger.debug(f"Added citation to thread {target_thread}: {citation.get('doc_title', 'Unknown')}")
    
    def get_request_citation_mapping(self) -> Dict[str, int]:
        """Get citation ID mapping for current request."""
        return self.tool_state.current_request_citation_mapping
    
    def set_request_citation_number(self, citation_id: str, number: int):
        """Set citation number for a specific citation ID in current request."""
        self.tool_state.current_request_citation_mapping[citation_id] = number
        logger.debug(f"Set request citation mapping: {citation_id} -> [{number}]")
    
    def get_request_citation_counter(self) -> int:
        """Get citation counter for current request."""
        return self.tool_state.current_request_citation_counter
    
    def increment_request_citation_counter(self) -> int:
        """Increment and return citation counter for current request."""
        self.tool_state.current_request_citation_counter += 1
        counter = self.tool_state.current_request_citation_counter
        logger.debug(f"Incremented request citation counter: {counter}")
        return counter
    
    def reset_request_citations(self):
        """Reset citation state for a new request (counters restart at 1)."""
        self.tool_state.current_request_citation_mapping = {}
        self.tool_state.current_request_citation_counter = 0
        logger.debug("Reset request citation state - counters restart at 1")
    
    def add_thread_tool_citation(self, tool_id: str, citation: Dict, thread_id: Optional[str] = None):
        """Add tool citation to a specific thread."""
        target_thread = thread_id or self.tool_state.current_thread_id
        if not target_thread:
            logger.warning("No active thread for tool citation")
            return
        
        if target_thread not in self.tool_state.thread_tool_citations:
            self.tool_state.thread_tool_citations[target_thread] = {}
        
        self.tool_state.thread_tool_citations[target_thread][tool_id] = citation
        logger.debug(f"Added tool citation to thread {target_thread}: {tool_id}")
    
    def get_thread_tool_citations(self, thread_id: Optional[str] = None) -> Dict[str, Dict]:
        """Get tool citations for a specific thread."""
        target_thread = thread_id or self.tool_state.current_thread_id
        if not target_thread:
            return {}
        return self.tool_state.thread_tool_citations.get(target_thread, {})
    
    def clear_thread_citations(self, thread_id: Optional[str] = None):
        """Clear citations for a specific thread (or current active thread)."""
        target_thread = thread_id or self.tool_state.current_thread_id
        if not target_thread:
            logger.warning("No thread specified for citation clearing")
            return
        
        # Clear thread-scoped citation data and tool results
        self.tool_state.thread_citations.pop(target_thread, None)
        self.tool_state.thread_tool_citations.pop(target_thread, None)
        self.tool_state.thread_tool_results.pop(target_thread, None)
        
        # Also clear request-scoped data if it's the current thread
        if target_thread == self.tool_state.current_thread_id:
            self.reset_request_citations()
        
        logger.debug(f"Cleared citations for thread: {target_thread}")
    
    def reset_thread_citations(self, thread_id: Optional[str] = None):
        """Reset citation state for current response in a thread."""
        target_thread = thread_id or self.tool_state.current_thread_id
        if not target_thread:
            logger.warning("No thread specified for citation reset")
            return
        
        # Keep historical citations but reset current response state
        # This maintains citation history within the thread
        logger.debug(f"Reset citations for new response in thread: {target_thread}")
    
    # Thread-based Tool Results Methods
    def add_thread_tool_result(self, tool_use_id: str, tool_result: Dict, thread_id: Optional[str] = None):
        """Add complete tool result to a specific thread for later reference."""
        target_thread = thread_id or self.tool_state.current_thread_id
        if not target_thread:
            logger.warning("No active thread for tool result storage")
            return
        
        if target_thread not in self.tool_state.thread_tool_results:
            self.tool_state.thread_tool_results[target_thread] = {}
        
        self.tool_state.thread_tool_results[target_thread][tool_use_id] = tool_result
        logger.debug(f"Added tool result to thread {target_thread}: {tool_use_id} ({tool_result.get('type', 'unknown')})")
    
    def get_thread_tool_results(self, thread_id: Optional[str] = None) -> Dict[str, Dict]:
        """Get all tool results for a specific thread."""
        target_thread = thread_id or self.tool_state.current_thread_id
        if not target_thread:
            return {}
        return self.tool_state.thread_tool_results.get(target_thread, {})
    
    def get_thread_tool_result(self, tool_use_id: str, thread_id: Optional[str] = None) -> Optional[Dict]:
        """Get specific tool result by tool_use_id from a thread."""
        thread_results = self.get_thread_tool_results(thread_id)
        return thread_results.get(tool_use_id)
    
    def clear_thread_tool_results(self, thread_id: Optional[str] = None):
        """Clear tool results for a specific thread."""
        target_thread = thread_id or self.tool_state.current_thread_id
        if not target_thread:
            logger.warning("No thread specified for tool results clearing")
            return
        
        self.tool_state.thread_tool_results.pop(target_thread, None)
        logger.debug(f"Cleared tool results for thread: {target_thread}")
    
    # Debug State Methods
    def add_debug_event(self, event_type: str):
        """Add debug event type."""
        self.debug_state.debug_event_types.append(event_type)
        self.debug_state.debug_event_count += 1
        logger.debug(f"Added debug event: {event_type}")
    
    def add_api_history_entry(self, entry: Dict):
        """Add entry to API history."""
        self.debug_state.api_history.append(entry)
        logger.debug("Added API history entry")
    
    def clear_debug_state(self):
        """Clear all debug state including captured logs."""
        # Clear legacy debug state
        self.debug_state.debug_request_body.clear()
        self.debug_state.debug_consolidated_response.clear()
        self.debug_state.debug_request_json_str = ""
        self.debug_state.debug_response_json_str = ""
        self.debug_state.debug_event_count = 0
        self.debug_state.debug_event_types.clear()
        self.debug_state.api_history.clear()
        
        # Clear request-scoped debug state
        self.debug_state.request_debug_bodies.clear()
        self.debug_state.request_debug_responses.clear()
        self.debug_state.request_debug_json_str.clear()
        self.debug_state.request_event_counts.clear()
        self.debug_state.request_event_types.clear()
        
        logger.debug("Cleared debug state")
    
    # Request-Scoped Debug Methods
    def add_request_debug_event(self, event_type: str, request_id: Optional[str] = None):
        """Add debug event type for a specific request."""
        target_request = request_id or self.response_state.current_response_id or 'unknown'
        
        # Initialize request debug data if needed
        if target_request not in self.debug_state.request_event_types:
            self.debug_state.request_event_types[target_request] = []
        if target_request not in self.debug_state.request_event_counts:
            self.debug_state.request_event_counts[target_request] = 0
        
        # Add event
        self.debug_state.request_event_types[target_request].append(event_type)
        self.debug_state.request_event_counts[target_request] += 1
        
        # Update legacy for compatibility
        self.debug_state.debug_event_types.append(event_type)
        self.debug_state.debug_event_count += 1
        
        logger.debug(f"Added debug event for request {target_request}: {event_type}")
    
    def set_request_debug_body(self, debug_body: Dict, request_id: Optional[str] = None):
        """Set debug request body for a specific request."""
        target_request = request_id or self.response_state.current_response_id or 'unknown'
        self.debug_state.request_debug_bodies[target_request] = debug_body
        
        # Update legacy for compatibility
        self.debug_state.debug_request_body = debug_body
        
        logger.debug(f"Set debug request body for request {target_request}")
    
    def set_request_debug_response(self, debug_response: Dict, request_id: Optional[str] = None):
        """Set debug consolidated response for a specific request."""
        target_request = request_id or self.response_state.current_response_id or 'unknown'
        self.debug_state.request_debug_responses[target_request] = debug_response
        
        # Update legacy for compatibility
        self.debug_state.debug_consolidated_response = debug_response
        
        logger.debug(f"Set debug response for request {target_request}")
    
    def get_request_debug_data(self, request_id: Optional[str] = None) -> Dict:
        """Get debug data for a specific request."""
        target_request = request_id or self.response_state.current_response_id
        if not target_request:
            return {}
        
        return {
            'request_body': self.debug_state.request_debug_bodies.get(target_request, {}),
            'response': self.debug_state.request_debug_responses.get(target_request, {}),
            'event_count': self.debug_state.request_event_counts.get(target_request, 0),
            'event_types': self.debug_state.request_event_types.get(target_request, [])
        }
    
    def clear_request_debug_data(self, request_id: Optional[str] = None):
        """Clear debug data for a specific request."""
        target_request = request_id or self.response_state.current_response_id
        if not target_request:
            return
        
        self.debug_state.request_debug_bodies.pop(target_request, None)
        self.debug_state.request_debug_responses.pop(target_request, None)
        self.debug_state.request_debug_json_str.pop(target_request, None)
        self.debug_state.request_event_counts.pop(target_request, None)
        self.debug_state.request_event_types.pop(target_request, None)
        
        logger.debug(f"Cleared debug data for request {target_request}")
    
    # Legacy debug methods for backward compatibility
    def add_debug_event(self, event_type: str):
        """Legacy method - use add_request_debug_event instead."""
        self.add_request_debug_event(event_type)
    
    
    # Utility Methods
    def cleanup_memory(self):
        """Clean up session state to prevent memory issues."""
        # Clear large response data
        self.clear_response_content()
        
        # Limit debug history size
        if len(self.debug_state.api_history) > 100:
            self.debug_state.api_history = self.debug_state.api_history[-50:]
        
        # Limit event types list
        if len(self.debug_state.debug_event_types) > 1000:
            self.debug_state.debug_event_types = self.debug_state.debug_event_types[-500:]
        
        
        logger.debug("Cleaned up session state memory")
    
    def reset_conversation_state(self):
        """Reset all conversation-related state."""
        self.clear_thread_messages()
        self.clear_response_content()
        self.clear_tool_citations()
        logger.debug("Reset conversation state")
    
    def reset_citations(self):
        """Reset citation state for a new response while preserving historical data."""
        # Reset legacy citation state for backward compatibility
        self.tool_state.citation_id_mapping = {}
        self.tool_state.citation_counter = 0
        self.tool_state.streaming_citations = []
        
        # For thread-based citations, we don't reset - they accumulate within the thread
        # This maintains citation history throughout the conversation
        logger.debug("Reset legacy citations for new response (thread citations preserved)")
    
    def get_state_summary(self) -> Dict[str, Any]:
        """Get summary of current session state for debugging."""
        return {
            "has_selected_agent": self.has_selected_agent(),
            "agent_name": self.get_selected_agent().get('name') if self.has_selected_agent() else None,
            "thread_id": self.get_thread_id(),
            "thread_message_count": len(self.get_thread_messages()),
            "response_table_count": len(self.response_state.current_response_tables),
            "response_chart_count": len(self.response_state.current_response_charts),
            "tool_citation_count": len(self.get_tool_citations()),
            "debug_mode": self.is_debug_mode(),
            "debug_event_count": self.debug_state.debug_event_count,
            "api_history_count": len(self.debug_state.api_history)
        }

# Global session manager instance
_session_manager = None

def get_session_manager() -> SessionStateManager:
    """Get the global session state manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionStateManager()
    return _session_manager

def ensure_session_state_defaults():
    """Legacy function for backward compatibility - use get_session_manager() instead."""
    get_session_manager().ensure_defaults()