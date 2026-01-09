"""
Authentication module for Cortex Agent application.

This module provides authentication utilities including:
- JWT token generation for RSA key authentication
- OAuth token management for Okta integration
- Authentication method management and prioritization
- Secure credential handling

Usage:
    from modules.authentication import get_auth_token, generate_jwt_token
    
    # Get authentication token with automatic method selection
    token = get_auth_token(config)
    
    # Generate JWT token directly
    jwt_token = generate_jwt_token(private_key, account, user)
    
    # Use OAuth authentication
    from modules.authentication import get_oauth_provider, is_oauth_enabled
    if is_oauth_enabled():
        oauth = get_oauth_provider()
        if oauth.is_authenticated():
            access_token = oauth.get_access_token()
"""

from .token_provider import (
    generate_jwt_token,
    generate_basic_auth_token,
    get_auth_token,
    get_auth_token_for_agents,
    connection,
    oauth_connection
)

from .okta_oauth import (
    OktaOAuthProvider,
    OktaConfig,
    get_oauth_provider,
    is_oauth_enabled,
    require_authentication,
    show_token_debug_panel,
    decode_jwt_token,
    decode_jwt_header,
    format_timestamp,
    get_token_expiry_status
)

# Export all authentication utilities
__all__ = [
    # Token providers
    "generate_jwt_token",
    "generate_basic_auth_token", 
    "get_auth_token",
    "get_auth_token_for_agents",
    "connection",
    "oauth_connection",
    # OAuth
    "OktaOAuthProvider",
    "OktaConfig",
    "get_oauth_provider",
    "is_oauth_enabled",
    "require_authentication",
    "show_token_debug_panel",
    # JWT utilities
    "decode_jwt_token",
    "decode_jwt_header",
    "format_timestamp",
    "get_token_expiry_status"
]
