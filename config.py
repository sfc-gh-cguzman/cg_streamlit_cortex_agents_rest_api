"""
Cortex Agent External Integration - Main Configuration File

This module contains all configurable settings for the Streamlit application,
including API settings, UI configuration, feature flags, and branding options.

Configuration Categories:
- Application Identification: API client identification
- API Settings: Timeouts, SSL, and connection parameters
- UI Settings: Layout, avatars, and visual configuration  
- Feature Flags: Enable/disable application features
- Display Limits: Data size and pagination controls

Usage:
    Import configuration constants in other modules:
    
    from config import PAGE_TITLE, API_TIMEOUT_MS, ENABLE_DEBUG_MODE
"""

# =============================================================================
# Application Identification
# =============================================================================

# Application identifier for API requests and Snowflake telemetry
# Used to identify your application in Snowflake logs, metrics, and audit trails
# REQUIREMENT: Must be 16 characters or less per Snowflake API specification
ORIGIN_APPLICATION = "ExtAgentApp"

# =============================================================================
# Feature Flags & UI Configuration
# =============================================================================

# Citation System: Enable post-response citation display with hyperlinks
ENABLE_CITATIONS = True

# Debug Interface: Enable comprehensive debug mode with API event tracking  
ENABLE_DEBUG_MODE = True

# Regenerate Button: Enable regenerate last question functionality
ENABLE_REGENERATE_BUTTON = True

# Display Behavior: Show only first tool use in UI vs all tool invocations
SHOW_FIRST_TOOL_USE_ONLY = False

# =============================================================================
# API Configuration & Limits
# =============================================================================

# HTTP Request Timeout: Maximum wait time for Cortex Agent API responses
API_TIMEOUT_MS = 50000  # 50 seconds in milliseconds

# Data Processing Limits: Maximum rows for DataFrame operations and display
MAX_DATAFRAME_ROWS = 1000

# File Processing Configuration: PDF preview and file handling settings
MAX_PDF_PAGES = 2                     # Maximum pages to display in PDF previews
ENABLE_FILE_PREVIEW = True           # Enable file preview capabilities
ENABLE_SUGGESTIONS = True            # Enable follow-up suggestions display

# =============================================================================
# Security Configuration  
# =============================================================================

# SSL Certificate Verification: Enable for production, disable for development/testing
SNOWFLAKE_SSL_VERIFY = True

# =============================================================================
# Streamlit Page Configuration
# =============================================================================

# Page Metadata: Browser tab title and icon
PAGE_TITLE = "Cortex Agent API - Demo"
PAGE_ICON = ":material/bolt:"

# Layout Settings: Page width and sidebar behavior  
LAYOUT = "wide"               # Use full browser width for better data display
SIDEBAR_STATE = "expanded"    # Show sidebar by default for easy agent selection

# Application Branding: Logo and visual identity
LOGO_PATH = "img/logo.png"    # Displayed in sidebar header

# =============================================================================
# Chat Interface Configuration
# =============================================================================

# Chat Avatars: Visual identifiers for conversation participants
ASSISTANT_AVATAR = ":material/robot_2:"  # Snowflake Cortex Agent avatar  
USER_AVATAR = ":material/face:"          # User avatar for chat messages

# Debug Mode: Enable comprehensive debugging UI and logging
ENABLE_DEBUG_MODE = False  # Set to True to show debug information in UI

# SSL Configuration: Snowflake connection security settings
SNOWFLAKE_SSL_VERIFY = True  # Enable SSL certificate verification for Snowflake connections

# =============================================================================
# Notes for Future Configuration Expansion
# =============================================================================

# Additional settings can be added here as needed:
# 
# Examples of potential future configuration options:
# - Company branding (logos, colors, themes)
# - Performance tuning (caching, request limits) 
# - Advanced logging and analytics options
# - API endpoint customization (if needed)
#
# When adding new settings:
# 1. Add the constant to this file with a descriptive comment
# 2. Import it in modules/config/app_config.py if needed by multiple modules
# 3. Update config.example to document the new setting
# 4. Update documentation in docs/ as appropriate
