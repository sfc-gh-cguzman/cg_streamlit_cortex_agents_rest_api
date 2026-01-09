"""
JWT token generation and authentication utilities.

This module provides multiple authentication methods for Snowflake including:
- Okta OAuth token authentication (recommended for external users)
- JWT token generation with RSA private key signatures
- Personal Access Token (PAT) authentication support
- Basic authentication with username/password (fallback)

Key Features:
- OAuth token support via Okta integration
- JWT token generation with RSA private key signatures
- Personal Access Token (PAT) authentication support
- Basic authentication with username/password (fallback)
- Error handling and authentication method prioritization
- Proper token expiration and payload formatting

Authentication Priority:
1. OAuth token (if user authenticated via Okta)
2. RSA private key (JWT)
3. Personal Access Token (PAT)
4. Password (basic auth - not recommended)
"""
import time
import base64
import streamlit as st
from typing import Optional
from modules.logging import get_logger
import os
import snowflake.connector
from snowflake.snowpark import Session


def connection(token) -> snowflake.connector.SnowflakeConnection:
    """
    Create Snowflake connection using OAuth token.
    
    This function establishes a connection to Snowflake using an OAuth token
    (either from SPCS or Okta OAuth) and returns both the session and headers
    for REST API calls.
    
    Args:
        token: OAuth access token from Okta or SPCS
        
    Returns:
        Tuple of (Session, headers dict) for API calls
    """
    logger = get_logger()
    logger.debug("Creating Snowflake connection with OAuth token")

    # Get connection parameters from environment or config
    host = os.getenv('SNOWFLAKE_HOST')
    account = os.getenv('SNOWFLAKE_ACCOUNT')
    warehouse = os.getenv('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH')
    database = os.getenv('SNOWFLAKE_DATABASE', os.getenv('SF_DB'))
    schema = os.getenv('SNOWFLAKE_SCHEMA', os.getenv('SF_SCHEMA'))
    
    creds = {
        'account': account,
        'authenticator': "oauth",
        'token': token,
        'warehouse': warehouse,
        'client_session_keep_alive': True
    }
    
    # Add optional host if specified
    if host:
        creds['host'] = host
    
    # Add optional port if specified
    port = os.getenv('SNOWFLAKE_PORT')
    if port:
        creds['port'] = port
        creds['protocol'] = "https"
    
    # Add database and schema if specified
    if database:
        creds['database'] = database
    if schema:
        creds['schema'] = schema

    connection = snowflake.connector.connect(**creds)
    
    session = Session.builder.configs({"connection": connection}).create()
    rest_token = session.connection._rest.token

    headers = {
        "Authorization": f'Snowflake Token="{rest_token}"',
        "Content-Type": "application/json",
    }
    
    logger.debug("Snowflake OAuth connection established successfully")
    return session, headers


def oauth_connection(oauth_token: str, config) -> tuple:
    """
    Create Snowflake connection using Okta OAuth token.
    
    This is the primary connection method when using Okta OAuth authentication.
    It uses the OAuth token to authenticate with Snowflake via the oauth authenticator.
    
    Args:
        oauth_token: Access token from Okta OAuth
        config: SnowflakeConfig instance with connection details
        
    Returns:
        Tuple of (Session, headers dict) for API calls
    """
    logger = get_logger()
    logger.debug("Creating Snowflake connection with Okta OAuth token")
    
    # Get user email from config (set by OAuth provider)
    user = config.oauth_user_email or config.user or 'oauth_user'
    
    creds = {
        'account': config.account,
        'user': user,
        'authenticator': 'oauth',
        'token': oauth_token,
        'warehouse': config.warehouse,
        'client_session_keep_alive': True
    }
    
    # Add database and schema if specified
    if config.database:
        creds['database'] = config.database
    if config.schema:
        creds['schema'] = config.schema
    if config.role:
        creds['role'] = config.role
    
    try:
        conn = snowflake.connector.connect(**creds)
        session = Session.builder.configs({"connection": conn}).create()
        rest_token = session.connection._rest.token
        
        headers = {
            "Authorization": f'Snowflake Token="{rest_token}"',
            "Content-Type": "application/json",
        }
        
        logger.info(f"Okta OAuth connection established for user: {user}")
        return session, headers
        
    except Exception as e:
        logger.error(f"Okta OAuth connection failed: {str(e)}")
        raise


def generate_jwt_token(private_key: str, account: str, user: str) -> str:
    """
    Generate JWT token using RSA private key for API authentication
    
    Args:
        private_key: RSA private key string (PEM format)
        account: Snowflake account identifier
        user: Snowflake username
        
    Returns:
        JWT token string with Bearer prefix
        
    Raises:
        Exception: If JWT generation fails
    """
    try:
        import jwt
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        
        # Load the private key
        if isinstance(private_key, str):
            private_key_bytes = private_key.encode('utf-8')
        else:
            private_key_bytes = private_key
        
        # Parse the private key (no passphrase)
        parsed_private_key = load_pem_private_key(
            private_key_bytes,
            password=None,
        )
        
        # Create JWT payload
        now = int(time.time())
        payload = {
            'iss': f"{account}.{user}",  # Issuer
            'sub': user,  # Subject
            'iat': now,  # Issued at
            'exp': now + 3600,  # Expires in 1 hour
        }
        
        # Generate JWT token
        token = jwt.encode(payload, parsed_private_key, algorithm='RS256')
        
        return f"Bearer {token}"
        
    except Exception as e:
        logger = get_logger()
        logger.error(
            "JWT token generation failed",
            error=str(e),
            account=account,
            user=user
        )
        raise Exception(f"Failed to generate JWT token: {str(e)}")

def generate_basic_auth_token(user: str, password: str) -> str:
    """
    Generate basic authentication token using username and password
    
    Args:
        user: Username
        password: Password
        
    Returns:
        Basic auth token string with Basic prefix
    """
    credentials = f"{user}:{password}"
    token = base64.b64encode(credentials.encode()).decode()
    return f"Basic {token}"

def get_auth_token(config) -> str:
    """
    Get authentication token with priority: OAuth > RSA Key > PAT > Password
    
    Args:
        config: SnowflakeConfig instance with authentication details
        
    Returns:
        Authentication token string with appropriate prefix (Bearer/Basic)
        
    Raises:
        SystemExit: If no valid authentication method is available
    """
    logger = get_logger()
    
    # Priority: OAuth > RSA Key > PAT > Password
    
    # Check for OAuth token first (highest priority when user is OAuth authenticated)
    if config.oauth_token:
        logger.info(
            "Using Okta OAuth authentication",
            user=config.oauth_user_email or config.user,
            account=config.account
        )
        return f"Bearer {config.oauth_token}"
    
    if config.private_key:
        # Generate JWT token using RSA key
        logger.info(
            "Using RSA key authentication",
            user=config.user,
            account=config.account
        )
        try:
            return generate_jwt_token(config.private_key, config.account, config.user)
        except Exception as e:
            logger.error("RSA authentication failed, trying fallback", error=str(e))
            st.error(f"Failed to generate JWT token: {str(e)}")
            st.error("Falling back to basic authentication if available")
            # Continue to fallback methods
            
    if config.pat:
        # Use Personal Access Token directly
        logger.info(
            "Using PAT authentication",
            user=config.user,
            account=config.account,
            pat_length=len(config.pat) if config.pat else 0
        )
        return f"Bearer {config.pat}"
        
    if config.password:
        # Simple base64 encoding for basic auth (not recommended for production)
        logger.warning(
            "Using password authentication (not recommended for production)",
            user=config.user,
            account=config.account
        )
        return generate_basic_auth_token(config.user, config.password)
    
    # No valid authentication method found
    logger.error(
        "No valid authentication method available",
        user=config.user,
        account=config.account,
        has_oauth_token=bool(config.oauth_token),
        has_private_key=bool(config.private_key),
        has_pat=bool(config.pat),
        has_password=bool(config.password)
    )
    st.error("No valid authentication method available")
    st.stop()

def get_auth_token_for_agents(config, snowflake_client) -> str:
    """
    Get authentication token for agent API calls
    
    Args:
        config: SnowflakeConfig instance
        snowflake_client: ExternalSnowflakeClient instance
        
    Returns:
        Auth token string without Bearer prefix for agent API calls
        
    Raises:
        ValueError: If no authentication token is available
    """
    # Priority: OAuth > PAT > RSA Key
    if config.oauth_token:
        return config.oauth_token
    elif config.pat:
        return config.pat
    elif config.private_key:
        # Generate JWT and remove 'Bearer ' prefix
        jwt_token = generate_jwt_token(config.private_key, config.account, config.user)
        return jwt_token[7:]  # Remove 'Bearer ' prefix
    else:
        raise ValueError("No authentication token available - need OAuth token, PAT, or private key")
