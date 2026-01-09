"""
Debug Interface Components for Cortex Agent API Development

This module provides comprehensive debugging tools for Cortex Agent API integration,
enabling developers to inspect, analyze, and export complete API interactions.

Key Features:
- Real-time API request/response JSON display
- Event stream statistics and type analysis
- Download functionality with timestamped filenames
- Tabbed interface for organized data viewing
- Session state integration for persistent debug data
- Browser-based file downloads with one-click access

Debug Interface Types:
- Immediate: Displays debug data right after streaming completes
- Persistent: Shows debug data from session state for continuous access

Usage:
    # Display debug interface immediately after API response
    display_debug_interface_now()
    
    # Show persistent debug interface if data available
    display_debug_interface_if_available()
    
    # Clear debug session state 
    clear_debug_session_state()
"""

import json
import os
import streamlit as st
from datetime import datetime


def display_debug_interface_now():
    """Display debug interface immediately after streaming completes"""
    # Get debug data from session manager
    from modules.config.session_state import get_session_manager
    
    session_manager = get_session_manager()
    display_request_json = session_manager.debug_state.debug_request_json_str or '{}'
    display_response_json = session_manager.debug_state.debug_response_json_str or '{}'
    display_event_count = session_manager.debug_state.debug_event_count
    display_event_types = session_manager.debug_state.debug_event_types
    
    if display_request_json != '{}' and display_response_json != '{}':
        # Display debug JSONs with save options
        st.success(":material/description: **Debug JSONs Ready for Download**")
        st.info(f":material/analytics: **Captured {display_event_count} events** across {len(display_event_types)} event types: {', '.join(display_event_types.keys())}")
        
        # Download options
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        col1, col2 = st.columns([1, 1])
        
        with col1:
            request_filename = f"cortex_agent_request_{timestamp}.json"
            st.download_button(
                label=":material/download: Download Request JSON",
                data=display_request_json,
                file_name=request_filename,
                mime="application/json",
                help="Download the request JSON to your browser's download folder",
                key="download_request_immediate"
            )
            
        with col2:
            response_filename = f"cortex_agent_response_{timestamp}.json"
            st.download_button(
                label=":material/download: Download Response JSON",
                data=display_response_json,
                file_name=response_filename,
                mime="application/json",
                help="Download the response JSON to your browser's download folder",
                key="download_response_immediate"
            )
        
        # Create tabs for viewing JSON content
        tab1, tab2 = st.tabs([":material/upload: Request JSON", ":material/download: Response JSON"])
        
        with tab1:
            st.subheader("Complete Request Payload")
            st.write("**Request JSON Content:**")
            try:
                request_data = json.loads(display_request_json)
                st.json(request_data)
            except json.JSONDecodeError:
                st.error("Invalid JSON format in request data")
                st.code(display_request_json, language="json")
            
        with tab2:
            st.subheader(":material/wifi: Complete Response Stream")
            st.write("**Response JSON Content:**")
            try:
                response_data = json.loads(display_response_json)
                st.json(response_data)
            except json.JSONDecodeError:
                st.error("Invalid JSON format in response data")
                st.code(display_response_json, language="json")


def display_debug_interface_if_available():
    """Display persistent debug interface if debug JSONs are available in session state"""
    # Get session manager
    from modules.config.session_state import get_session_manager
    session_manager = get_session_manager()
    
    # Only show if debug mode is active and we have debug JSONs
    if (session_manager.is_debug_mode() and 
        session_manager.debug_state.debug_request_json_str):
        
        # Get debug data from session manager
        display_request_json = session_manager.debug_state.debug_request_json_str or '{}'
        display_response_json = session_manager.debug_state.debug_response_json_str or '{}'
        display_event_count = session_manager.debug_state.debug_event_count
        display_event_types = session_manager.debug_state.debug_event_types
        
        # Display debug JSONs with download and copy options
        st.success(":material/description: **Debug JSONs Ready for Download**")
        st.info(f":material/analytics: **Captured {display_event_count} events** across {len(display_event_types)} event types: {', '.join(display_event_types.keys())}")
        
        # Download options
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        col1, col2 = st.columns([1, 1])
        
        with col1:
            request_filename = f"cortex_agent_request_{timestamp}.json"
            st.download_button(
                label=":material/download: Download Request JSON",
                data=display_request_json,
                file_name=request_filename,
                mime="application/json",
                help="Download the request JSON to your browser's download folder",
                key="download_request_persistent"
            )
            
        with col2:
            response_filename = f"cortex_agent_response_{timestamp}.json"
            st.download_button(
                label=":material/download: Download Response JSON",
                data=display_response_json,
                file_name=response_filename,
                mime="application/json",
                help="Download the response JSON to your browser's download folder",
                key="download_response_persistent"
            )
        
        # Create tabs for viewing JSON content
        tab1, tab2 = st.tabs([":material/upload: Request JSON", ":material/download: Response JSON"])
        
        with tab1:
            st.subheader("Complete Request Payload")
            st.write("**Request JSON Content:**")
            try:
                request_data = json.loads(display_request_json)
                st.json(request_data)
            except json.JSONDecodeError:
                st.error("Invalid JSON format in request data")
                st.code(display_request_json, language="json")
        
        with tab2:
            st.subheader(":material/wifi: Complete Response Stream")
            st.write("**Response JSON Content:**")
            try:
                response_data = json.loads(display_response_json)
                st.json(response_data)
            except json.JSONDecodeError:
                st.error("Invalid JSON format in response data")
                st.code(display_response_json, language="json")


def clear_debug_session_state():
    """Clear all debug-related session state variables"""
    from modules.config.session_state import get_session_manager
    
    session_manager = get_session_manager()
    session_manager.clear_debug_state()


# initialize_debug_mode function removed - SessionStateManager handles initialization
