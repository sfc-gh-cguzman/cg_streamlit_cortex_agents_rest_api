"""
External Snowflake client for API calls and session management.

This module provides the core ExternalSnowflakeClient class that handles:
- Snowpark session creation and management
- Authentication with multiple methods (RSA, PAT, password)
- API request execution using CURL pattern
- Connection parameter configuration

Key Features:
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

class ExternalSnowflakeClient:
    """External Snowflake client for API calls and session management"""
    
    def __init__(self, config: SnowflakeConfig):
        self.config = config
        self._session = None
        self._connection = None
        self._base_url = f"https://{self.config.account}.snowflakecomputing.com"
        
    def get_session(self) -> Session:
        """Get or create Snowpark session"""
        if self._session is None:
            connection_params = {
                "account": self.config.account,
                "user": self.config.user,
                "warehouse": self.config.warehouse,
                # Use default database/schema since app works with any agent across different locations
                "database": getattr(self.config, 'database', 'SNOWFLAKE_INTELLIGENCE'),
                "schema": getattr(self.config, 'schema', 'PUBLIC'),
            }
            
            # Add authentication method - prioritize RSA key
            if self.config.private_key:
                # RSA Key authentication
                try:
                    # Load the private key
                    if isinstance(self.config.private_key, str):
                        private_key_bytes = self.config.private_key.encode('utf-8')
                    else:
                        private_key_bytes = self.config.private_key
                    
                    # Parse the private key (no passphrase)
                    private_key = load_pem_private_key(
                        private_key_bytes,
                        password=None,
                    )
                    
                    # Get the key in the format Snowflake expects
                    pkb = private_key.private_bytes(
                        encoding=serialization.Encoding.DER,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    )
                    
                    connection_params["private_key"] = pkb
                    
                except Exception as e:
                    st.error(f"Failed to load RSA private key: {str(e)}")
                    st.error("Please check your RSA key format and passphrase.")
                    st.stop()
                    
            elif self.config.password:
                connection_params["password"] = self.config.password
            elif self.config.pat:
                # For Snowpark, PAT might work as password in some cases
                connection_params["password"] = self.config.pat
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
