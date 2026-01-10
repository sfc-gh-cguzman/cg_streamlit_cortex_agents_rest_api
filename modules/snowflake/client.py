"""
External Snowflake client for API calls and session management.

This module provides the core ExternalSnowflakeClient class that handles:
- Snowpark session creation and management
- Authentication with multiple methods (OAuth, RSA, PAT, password)
- API request execution using CURL pattern
- Connection parameter configuration

Key Features:
- OAuth authentication support (Okta)
- Session caching and reuse
- Private key authentication with proper DER encoding
- API request wrapper with authentication token handling
- Error handling and Streamlit integration
"""
import streamlit as st
from snowflake.snowpark import Session
from typing import Dict, Optional
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from modules.config.snowflake_config import SnowflakeConfig
from modules.config.app_config import API_TIMEOUT
from modules.authentication.token_provider import get_auth_token
from modules.api.http_client import execute_curl_request
from modules.logging import get_logger

logger = get_logger()


class ExternalSnowflakeClient:
    """External Snowflake client for API calls and session management"""
    
    def __init__(self, config: SnowflakeConfig):
        self.config = config
        self._session = None
        self._oauth_session = None  # Separate session for OAuth
        self._connection = None
        self._base_url = f"https://{self.config.account}.snowflakecomputing.com"
    
    def get_session(self, oauth_token: str = None) -> Session:
        """
        Get or create Snowpark session.
        
        Args:
            oauth_token: Optional OAuth access token. If provided, creates an OAuth session.
                        If not provided, uses config-based authentication.
        
        Returns:
            Snowpark Session
        """
        # If OAuth token is provided, use OAuth session
        if oauth_token or self.config.oauth_token:
            return self._get_oauth_session(oauth_token or self.config.oauth_token)
        
        # Otherwise use traditional authentication
        return self._get_traditional_session()
    
    def _get_oauth_session(self, oauth_token: str) -> Session:
        """Create a Snowpark session using OAuth authentication."""
        # Check if we need to create/recreate the OAuth session
        # (token might have been refreshed)
        if self._oauth_session is None:
            logger.info("Creating new OAuth Snowpark session")
            
            connection_params = {
                "account": self.config.account,
                "authenticator": "oauth",
                "token": oauth_token,
                "warehouse": self.config.warehouse,
                "database": getattr(self.config, 'database', 'SNOWFLAKE_INTELLIGENCE'),
                "schema": getattr(self.config, 'schema', 'PUBLIC'),
            }
            
            # Add user if available (from OAuth user info)
            if self.config.oauth_user_email:
                connection_params["user"] = self.config.oauth_user_email
            elif self.config.user:
                connection_params["user"] = self.config.user
            
            try:
                self._oauth_session = Session.builder.configs(connection_params).create()
                logger.info("OAuth Snowpark session created successfully")
            except Exception as e:
                logger.error(f"Failed to create OAuth Snowpark session: {e}")
                st.error(f"Failed to create Snowpark session with OAuth: {str(e)}")
                st.error("Please ensure your Okta integration is properly configured with Snowflake.")
                st.stop()
        
        return self._oauth_session
    
    def _get_traditional_session(self) -> Session:
        """Create a Snowpark session using traditional authentication (RSA, PAT, password)."""
        if self._session is None:
            connection_params = {
                "account": self.config.account,
                "user": self.config.user,
                "warehouse": self.config.warehouse,
                "database": getattr(self.config, 'database', 'SNOWFLAKE_INTELLIGENCE'),
                "schema": getattr(self.config, 'schema', 'PUBLIC'),
            }
            
            # Add authentication method - prioritize RSA key
            if self.config.private_key:
                # RSA Key authentication
                try:
                    if isinstance(self.config.private_key, str):
                        private_key_bytes = self.config.private_key.encode('utf-8')
                    else:
                        private_key_bytes = self.config.private_key
                    
                    private_key = load_pem_private_key(
                        private_key_bytes,
                        password=None,
                    )
                    
                    pkb = private_key.private_bytes(
                        encoding=serialization.Encoding.DER,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    )
                    
                    connection_params["private_key"] = pkb
                    logger.info("Using RSA key authentication for Snowpark session")
                    
                except Exception as e:
                    st.error(f"Failed to load RSA private key: {str(e)}")
                    st.error("Please check your RSA key format and passphrase.")
                    st.stop()
                    
            elif self.config.password:
                connection_params["password"] = self.config.password
                logger.info("Using password authentication for Snowpark session")
            elif self.config.pat:
                connection_params["password"] = self.config.pat
                logger.info("Using PAT authentication for Snowpark session")
            else:
                st.error("No valid authentication method configured")
                st.stop()
            
            try:
                self._session = Session.builder.configs(connection_params).create()
            except Exception as e:
                st.error(f"Failed to create Snowpark session: {str(e)}")
                st.error("Please check your credentials and network connectivity.")
                st.stop()
                
        return self._session
    
    def clear_oauth_session(self):
        """Clear the OAuth session (e.g., after token refresh or logout)."""
        if self._oauth_session is not None:
            try:
                self._oauth_session.close()
            except:
                pass
            self._oauth_session = None
            logger.info("OAuth session cleared")
    
    def get_auth_token(self) -> str:
        """Get authentication token for API calls"""
        return get_auth_token(self.config)
    
    def send_api_request(self, method: str, endpoint: str, headers: Dict = None, 
                        params: Dict = None, payload: Dict = None, 
                        request_guid: str = None, timeout_ms: int = None) -> Dict:
        """Send API request to Snowflake using CURL (following test_thread_curl.sh pattern)"""
        
        # Get authentication token
        auth_token = self.get_auth_token()
        if auth_token.startswith('Bearer '):
            auth_token = auth_token[7:]  # Remove 'Bearer ' prefix for curl helper
        
        # Build full URL
        url = f"{self._base_url}{endpoint}"
        
        # Convert timeout from milliseconds to seconds
        timeout_seconds = (timeout_ms or API_TIMEOUT) / 1000
        
        # Execute curl request following test_thread_curl.sh pattern
        result = execute_curl_request(
            method=method,
            url=url,
            auth_token=auth_token,
            payload=payload,
            timeout=int(timeout_seconds)
        )
        
        # Convert to expected format
        return {
            "status": result["status"],
            "content": result["content"],
            "headers": result["headers"],
            "reason": result.get("error", None)
        }
