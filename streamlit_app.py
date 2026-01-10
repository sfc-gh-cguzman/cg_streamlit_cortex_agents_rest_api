"""
Cortex Agent - External Integration Demo

This is the main entry point for the Cortex Agent external Streamlit application.
The application demonstrates how to integrate Snowflake's Agentic AI Experience
within any external application using the Cortex Agent REST API.

All functionality has been modularized into organized packages:
- modules/models: Data models for API requests/responses and events
- modules/config: Configuration management and session state
- modules/logging: Structured logging infrastructure
- modules/authentication: Token generation and authentication
- modules/api: HTTP client and Cortex Agent API integration
- modules/snowflake: Snowflake client and agent management
- modules/threads: Thread management for conversations
- modules/files: File handling and document processing
- modules/utils: Text processing and utility functions
- modules/ui: User interface components and debug tools

Run with: streamlit run streamlit_app.py
"""

# Load environment variables from .env file FIRST (before any other imports)
import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

# Import the main application function from the modular architecture
from modules.main import main
from config import PAGE_TITLE, PAGE_ICON, LAYOUT, SIDEBAR_STATE, LOGO_PATH

# Configure Streamlit page
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=LAYOUT,
    initial_sidebar_state=SIDEBAR_STATE
)

# Display the Snowflake logo in the sidebar navigation
st.logo(LOGO_PATH)

# Entry point - only execute main() when script is run directly (not imported)
if __name__ == "__main__":
    main()
