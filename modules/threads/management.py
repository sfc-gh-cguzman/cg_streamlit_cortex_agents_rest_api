"""
Thread management utilities for Cortex Agent conversations.

This module provides CRUD operations for Snowflake Cortex Agent threads:
- Thread creation with proper authentication
- Thread message retrieval with pagination support
- Thread deletion with error handling
- Thread state management with session integration

Key Features:
- CURL-based HTTP requests following test_thread_curl.sh patterns
- Complete thread lifecycle management
- Proper authentication token handling (PAT/JWT)
- Streamlit session state integration
- Error handling and debug output support
"""
import json
import streamlit as st
from typing import Optional, List
from modules.config.session_state import get_session_manager

from modules.api.http_client import execute_curl_request
from modules.authentication.token_provider import get_auth_token_for_agents
from modules.models.threads import ThreadMetadata, ThreadMessage, ThreadResponse

def create_thread(snowflake_config, snowflake_client=None) -> Optional[str]:
    """
    Create a new thread for agent conversations using CURL
    API: POST /api/v2/cortex/threads
    Reference: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-threads-rest-api
    
    Args:
        snowflake_config: SnowflakeConfig instance with authentication details
        snowflake_client: ExternalSnowflakeClient instance (for JWT generation)
        
    Returns:
        Thread ID string if successful, None if failed
    """
    try:
        # Get auth token - OAuth token takes priority, then PAT
        if hasattr(snowflake_config, 'oauth_token') and snowflake_config.oauth_token:
            auth_token = snowflake_config.oauth_token
        elif snowflake_config.pat:
            auth_token = snowflake_config.pat
        else:
            # No token available - this shouldn't happen if auth flow is correct
            return None
        
        # Build URL following official API spec
        url = f"https://{snowflake_config.account}.snowflakecomputing.com/api/v2/cortex/threads"
        
        # Request body as per official spec - origin_application is optional (max 16 bytes)
        payload = {
            "origin_application": "CortexAgentDemo"  # Shortened to fit 16 byte limit
        }
        
        # Execute CURL request using the working test_thread_curl.sh pattern
        result = execute_curl_request(
            method="POST",
            url=url,
            auth_token=auth_token,
            payload=payload,
            timeout=30
        )
        
        if result["status"] == 200:
            # Parse JSON response to extract thread_id (same as working test_thread_curl.sh)
            try:
                response_data = json.loads(result["content"])
                
                # Debug: Show the full creation response
                if get_session_manager().is_debug_mode():
                    st.write("Thread creation response:", response_data)
                    st.write("Sent origin_application:", payload.get("origin_application"))
                
                thread_id = response_data.get("thread_id")
                if thread_id:
                    # Store the origin_application value since API doesn't return it in retrieval
                    session_manager = get_session_manager()
                    session_manager.thread_state.origin_application = payload.get("origin_application", "")
                    
                    return str(thread_id)  # Convert to string for consistency
                else:
                    st.error(":material/error: No thread_id in response")
                    return None
            except json.JSONDecodeError as e:
                st.error(f":material/error: Failed to parse thread response as JSON: {e}")
                return None
        else:
            st.error(f":material/error: Failed to create thread: HTTP {result['status']}")
            if result.get('error'):
                st.error(f"Details: {result['error']}")
            return None
                
    except Exception as e:
        st.error(f":material/error: Exception creating thread: {str(e)}")
        return None

def get_thread_messages(thread_id: str, snowflake_config, snowflake_client, 
                       page_size: int = 20, last_message_id: Optional[str] = None) -> Optional[ThreadResponse]:
    """
    Get messages from thread using CURL, returns ThreadResponse object
    API: GET /api/v2/cortex/threads/{id}
    Reference: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-threads-rest-api
    
    Args:
        thread_id: Thread identifier
        snowflake_config: SnowflakeConfig instance with authentication details
        snowflake_client: ExternalSnowflakeClient instance (for JWT generation)
        page_size: Number of messages to retrieve (max 100)
        last_message_id: Last message ID for pagination
        
    Returns:
        ThreadResponse object if successful, None if failed
    """
    try:
        # Get auth token - OAuth token takes priority, then PAT, then RSA
        if hasattr(snowflake_config, 'oauth_token') and snowflake_config.oauth_token:
            auth_token = snowflake_config.oauth_token
        elif snowflake_config.pat:
            auth_token = snowflake_config.pat
        elif snowflake_config.private_key:
            # Generate JWT token if using RSA key
            auth_token = get_auth_token_for_agents(snowflake_config, snowflake_client)
        else:
            return None
        
        # Build URL following official API spec
        # Max page_size is 100 according to documentation
        page_size = min(page_size, 100)
        url = f"https://{snowflake_config.account}.snowflakecomputing.com/api/v2/cortex/threads/{thread_id}?page_size={page_size}"
        
        # Add last_message_id if provided for pagination
        if last_message_id:
            url += f"&last_message_id={last_message_id}"
        
        # Execute CURL request
        result = execute_curl_request(
            method="GET",
            url=url,
            auth_token=auth_token,
            payload=None,
            timeout=30
        )
        
        if result["status"] == 200:
            thread_data = json.loads(result["content"]) if result["content"] else {}
            # API returns both metadata and messages according to documentation
            messages_data = thread_data.get("messages", [])
            metadata_data = thread_data.get("metadata", {})
            
            # Create ThreadMetadata object
            # Note: API doesn't return origin_application in retrieval, so use stored value
            session_manager = get_session_manager()
            stored_origin_application = session_manager.thread_state.origin_application
            
            # Debug: Show what fields are actually in the metadata response
            if get_session_manager().is_debug_mode():
                st.write("Raw metadata_data from API:", metadata_data)
                st.write("Available metadata fields:", list(metadata_data.keys()))
                st.write("Using stored origin_application:", stored_origin_application)
            
            metadata = ThreadMetadata(
                thread_id=metadata_data.get("thread_id", thread_id),
                thread_name=metadata_data.get("thread_name", ""),
                origin_application=metadata_data.get("origin_application", stored_origin_application),
                created_on=metadata_data.get("created_on", 0),
                updated_on=metadata_data.get("updated_on", 0)
            )
            
            # Create ThreadMessage objects
            messages = []
            for msg_data in messages_data:
                thread_message = ThreadMessage(
                    message_id=msg_data.get("message_id", 0),
                    parent_id=msg_data.get("parent_id"),
                    created_on=msg_data.get("created_on", 0),
                    role=msg_data.get("role", ""),
                    message_payload=msg_data.get("message_payload", ""),
                    request_id=msg_data.get("request_id", "")
                )
                messages.append(thread_message)
            
            # Create ThreadResponse object
            thread_response = ThreadResponse(metadata=metadata, messages=messages)
            
            if get_session_manager().is_debug_mode():
                st.write("Thread metadata:", metadata)
                st.write(f"Retrieved {len(messages)} messages")
                
            return thread_response
        else:
            st.error(f":material/error: Failed to get thread messages: HTTP {result['status']}")
            if result.get('error'):
                st.error(f"Details: {result['error']}")
            return None
            
    except Exception as e:
        st.error(f":material/error: Exception getting thread messages: {str(e)}")
        return None

def delete_thread(thread_id: str, snowflake_config, snowflake_client) -> bool:
    """
    Delete a thread and all its messages using CURL
    API: DELETE /api/v2/cortex/threads/{id}
    Reference: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-threads-rest-api
    
    Args:
        thread_id: Thread identifier
        snowflake_config: SnowflakeConfig instance with authentication details
        snowflake_client: ExternalSnowflakeClient instance (for JWT generation)
        
    Returns:
        True if successful, False if failed
    """
    try:
        # Get auth token - OAuth token takes priority, then PAT, then RSA
        if hasattr(snowflake_config, 'oauth_token') and snowflake_config.oauth_token:
            auth_token = snowflake_config.oauth_token
        elif snowflake_config.pat:
            auth_token = snowflake_config.pat
        elif snowflake_config.private_key:
            # Generate JWT token if using RSA key
            auth_token = get_auth_token_for_agents(snowflake_config, snowflake_client)
        else:
            return False
        
        # Build URL following official API spec
        url = f"https://{snowflake_config.account}.snowflakecomputing.com/api/v2/cortex/threads/{thread_id}"
        
        # Execute CURL request
        result = execute_curl_request(
            method="DELETE",
            url=url,
            auth_token=auth_token,
            payload=None,
            timeout=30
        )
        
        if result["status"] == 200:
            # HTTP 200 indicates successful deletion
            try:
                response_data = json.loads(result["content"]) if result["content"] else {}
                success = response_data.get("success", True)  # Default to True for 200 status
                if success:
                    if get_session_manager().is_debug_mode():
                        st.toast(f":material/check_circle: Deleted thread: {thread_id}", icon=":material/check_circle:")
                    return True
                else:
                    # Provide more informative error message
                    error_msg = response_data.get("message", "Unknown error")
                    st.error(f":material/error: Delete failed: {error_msg}")
                    return False
            except json.JSONDecodeError:
                # If response is not JSON, consider success based on status code
                if get_session_manager().is_debug_mode():
                    st.toast(f":material/check_circle: Deleted thread: {thread_id}", icon=":material/check_circle:")
                return True
        else:
            st.error(f":material/error: Failed to delete thread: HTTP {result['status']}")
            if result.get('error'):
                st.error(f"Details: {result['error']}")
            return False
        
    except Exception as e:
        st.error(f":material/error: Exception deleting thread: {str(e)}")
        return False

def update_thread(thread_id: str, thread_name: str, snowflake_config, snowflake_client) -> bool:
    """
    Update a thread's properties (primarily thread name)
    API: POST /api/v2/cortex/threads/{id}
    Reference: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-threads-rest-api
    
    Args:
        thread_id: Thread identifier
        thread_name: New name for the thread
        snowflake_config: SnowflakeConfig instance with authentication details
        snowflake_client: ExternalSnowflakeClient instance (for JWT generation)
        
    Returns:
        True if successful, False if failed
    """
    try:
        # Get auth token - OAuth token takes priority, then PAT, then RSA
        if hasattr(snowflake_config, 'oauth_token') and snowflake_config.oauth_token:
            auth_token = snowflake_config.oauth_token
        elif snowflake_config.pat:
            auth_token = snowflake_config.pat
        elif snowflake_config.private_key:
            # Generate JWT token if using RSA key
            auth_token = get_auth_token_for_agents(snowflake_config, snowflake_client)
        else:
            return False
        
        # Build URL following official API spec
        url = f"https://{snowflake_config.account}.snowflakecomputing.com/api/v2/cortex/threads/{thread_id}"
        
        # Request body as per official spec
        payload = {
            "thread_name": thread_name
        }
        
        # Execute CURL request
        result = execute_curl_request(
            method="POST",
            url=url,
            auth_token=auth_token,
            payload=payload,
            timeout=30
        )
        
        if result["status"] == 200:
            # Parse response to confirm success
            try:
                response_data = json.loads(result["content"]) if result["content"] else {}
                status_message = response_data.get("status", "")
                if "successfully updated" in status_message.lower():
                    if get_session_manager().is_debug_mode():
                        st.toast(f":material/check_circle: Updated thread: {thread_name}", icon=":material/check_circle:")
                    return True
                else:
                    st.error(f":material/error: Update failed: {status_message}")
                    return False
            except json.JSONDecodeError:
                # If response is not JSON, consider success based on status code
                if get_session_manager().is_debug_mode():
                    st.toast(f":material/check_circle: Updated thread: {thread_name}", icon=":material/check_circle:")
                return True
        else:
            st.error(f":material/error: Failed to update thread: HTTP {result['status']}")
            if result.get('error'):
                st.error(f"Details: {result['error']}")
            return False
            
    except Exception as e:
        st.error(f":material/error: Exception updating thread: {str(e)}")
        return False

def list_threads(snowflake_config, snowflake_client, origin_application: Optional[str] = None) -> Optional[List[ThreadMetadata]]:
    """
    List all threads belonging to the user
    API: GET /api/v2/cortex/threads
    Reference: https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-threads-rest-api
    
    Args:
        snowflake_config: SnowflakeConfig instance with authentication details
        snowflake_client: ExternalSnowflakeClient instance (for JWT generation)
        origin_application: Optional filter for threads by origin application
        
    Returns:
        List of ThreadMetadata objects if successful, None if failed
    """
    try:
        # Get auth token - OAuth token takes priority, then PAT, then RSA
        if hasattr(snowflake_config, 'oauth_token') and snowflake_config.oauth_token:
            auth_token = snowflake_config.oauth_token
        elif snowflake_config.pat:
            auth_token = snowflake_config.pat
        elif snowflake_config.private_key:
            # Generate JWT token if using RSA key
            auth_token = get_auth_token_for_agents(snowflake_config, snowflake_client)
        else:
            return None
        
        # Build URL following official API spec
        url = f"https://{snowflake_config.account}.snowflakecomputing.com/api/v2/cortex/threads"
        
        # Add origin_application filter if provided
        if origin_application:
            url += f"?origin_application={origin_application}"
        
        # Execute CURL request
        result = execute_curl_request(
            method="GET",
            url=url,
            auth_token=auth_token,
            payload=None,
            timeout=30
        )
        
        if result["status"] == 200:
            # Parse response to extract thread metadata array
            try:
                threads_data = json.loads(result["content"]) if result["content"] else []
                thread_list = []
                
                # Process each thread metadata object
                for thread_data in threads_data:
                    # Note: API may not return origin_application in list, so use stored or default value
                    session_manager = get_session_manager()
                    default_origin_application = session_manager.thread_state.origin_application
                    
                    metadata = ThreadMetadata(
                        thread_id=str(thread_data.get("thread_id", "")),
                        thread_name=thread_data.get("thread_name", ""),
                        origin_application=thread_data.get("origin_application", default_origin_application),
                        created_on=thread_data.get("created_on", 0),
                        updated_on=thread_data.get("updated_on", 0)
                    )
                    thread_list.append(metadata)
                
                if get_session_manager().is_debug_mode():
                    st.write(f"Retrieved {len(thread_list)} threads")
                    if origin_application:
                        st.write(f"Filtered by origin_application: {origin_application}")
                        
                return thread_list
                
            except json.JSONDecodeError as e:
                st.error(f":material/error: Failed to parse threads response as JSON: {e}")
                return None
        else:
            st.error(f":material/error: Failed to list threads: HTTP {result['status']}")
            if result.get('error'):
                st.error(f"Details: {result['error']}")
            return None
            
    except Exception as e:
        st.error(f":material/error: Exception listing threads: {str(e)}")
        return None

def get_or_create_thread(snowflake_config, snowflake_client=None) -> Optional[str]:
    """
    Get existing thread or create a new one
    
    Args:
        snowflake_config: SnowflakeConfig instance with authentication details
        snowflake_client: ExternalSnowflakeClient instance (for JWT generation)
        
    Returns:
        Thread ID string if successful, None if failed
    """
    session_manager = get_session_manager()
    
    if not session_manager.get_thread_id() or session_manager.thread_state.create_new_thread:
        thread_id = create_thread(snowflake_config, snowflake_client)
        if thread_id:
            session_manager.set_thread_id(thread_id)
            session_manager.thread_state.create_new_thread = False
            session_manager.clear_thread_messages()
        return thread_id
    return session_manager.get_thread_id()
