"""
Snowflake authentication configuration management.

This module provides the SnowflakeConfig class for managing Snowflake connection
authentication with support for multiple authentication methods and configuration
sources with a clear priority hierarchy.

Supported Authentication Methods:
- Okta OAuth token (recommended for external user authentication)
- RSA private key authentication (recommended for service accounts)
- Personal Access Token (PAT) authentication
- Password authentication (less secure, fallback only)

Configuration Source Priority:
1. Streamlit secrets [connections.snowflake] (highest priority)
2. JSON configuration file
3. Environment variables 
4. Default values (lowest priority)

    Configuration File Format:
    {
        "account": "orgname-accountname",
        "user": "your_username", 
        "pat": "your_personal_access_token",
    "warehouse": "your_warehouse",
    "database": "optional_database",
    "schema": "optional_schema",
    "rsa_key_path": "/path/to/private_key.pem",
    "ssl_verify": "true"
}

Environment Variables:
- SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PAT
- SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA
- SNOWFLAKE_PRIVATE_KEY_PATH, SNOWFLAKE_SSL_VERIFY

Okta OAuth Environment Variables:
- OKTA_ISSUER: Okta authorization server URL
- OKTA_CLIENT_ID: Okta application client ID
- OKTA_CLIENT_SECRET: Okta application client secret (optional)
- OKTA_REDIRECT_URI: OAuth callback URL
- OKTA_SCOPE: OAuth scopes (default: openid profile email session:role-any)

Usage:
    # Initialize with default config file location
    config = SnowflakeConfig()
    
    # Initialize with custom config file  
    config = SnowflakeConfig("/path/to/custom/config.json")
    
    # Access configuration values
    client = ExternalSnowflakeClient(config)
    
    # For OAuth authentication, set oauth_token dynamically
    config.oauth_token = oauth_provider.get_access_token()
"""
import os
import json
import streamlit as st
from typing import Optional

class SnowflakeConfig:
    """Simple authentication configuration management for external Snowflake connection"""
    
    def __init__(self, config_file: str = "/Library/Application Support/Snowflake/config.json"):
        """
        Initialize authentication configuration from simple JSON file with fallback to environment variables
        
        Args:
            config_file: Path to JSON configuration file
        """
        self.config_data = {}
        
        # Try to load from JSON file first
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    self.config_data = json.load(f)
                # Configuration loaded successfully
            except Exception as e:
                st.warning(f":material/warning: Failed to load {config_file}: {str(e)}. Falling back to environment variables.")
        else:
            # No config file found, will use environment variables/secrets
            pass
        
        # Load authentication details with simple key lookup
        self.account = self._get_config('account', 'SNOWFLAKE_ACCOUNT')
        # User is optional at load time - OAuth may provide user identity
        self.user = self._get_config('user', 'SNOWFLAKE_USER', required=False)
        self.password = self._get_config('password', 'SNOWFLAKE_PASSWORD', required=False)
        self.pat = self._get_config('pat', 'SNOWFLAKE_PAT', required=False)
        
        # Handle case where PAT is stored as 'password' in [connections.snowflake] format
        if not self.pat and self.password and self.password.startswith('eyJ'):
            # If password looks like a JWT token, treat it as PAT
            self.pat = self.password
            self.password = None
        
        # PAT token validation
        if not self.pat:
            pass  # Will fall back to RSA key authentication if needed
        self.rsa_key_path = self._get_config('rsa_key_path', 'SNOWFLAKE_PRIVATE_KEY_PATH', required=False)
        self.warehouse = self._get_config('warehouse', 'SNOWFLAKE_WAREHOUSE')
        self.database = self._get_config('database', 'SNOWFLAKE_DATABASE', required=False)
        self.schema = self._get_config('schema', 'SNOWFLAKE_SCHEMA', required=False)
        self.role = self._get_config('role', 'SNOWFLAKE_ROLE', required=False)
        
        # SSL verification setting (default from config.py for security, can be disabled for dev/testing)
        from modules.config.app_config import SNOWFLAKE_SSL_VERIFY
        default_ssl_verify = 'true' if SNOWFLAKE_SSL_VERIFY else 'false'
        ssl_verify_str = self._get_config('ssl_verify', 'SNOWFLAKE_SSL_VERIFY', default=default_ssl_verify, required=False)
        self.ssl_verify = ssl_verify_str.lower() in ('true', 'yes', '1')
        
        # Load RSA key from file if path is provided
        self.private_key = None
        if self.rsa_key_path:
            self.private_key = self._load_rsa_key_from_file()
        
        # OAuth token support - can be set dynamically after initialization
        # This is set by the OAuth provider when user authenticates via Okta
        self.oauth_token = None
        self.oauth_user_email = None
        
        # Validate required configuration
        self._validate_config()
        
    def _get_config(self, json_key: str, env_key: str, default: Optional[str] = None, required: bool = True) -> str:
        """
        Get configuration value with priority: Streamlit [connections.snowflake] > JSON config > Environment variables > Default
        
        Args:
            json_key: Simple key for JSON config (e.g., 'account')
            env_key: Environment variable key
            default: Default value if not found
            required: Whether the value is required
        """
        value = None
        
        # 1. Try streamlit [connections.snowflake] format first (HIGHEST PRIORITY)
        if hasattr(st, 'secrets'):
            # Check if secrets.toml file exists to avoid Streamlit warnings
            secrets_paths = [
                os.path.expanduser("~/.streamlit/secrets.toml"),
                os.path.join(os.getcwd(), ".streamlit/secrets.toml")
            ]
            if any(os.path.exists(path) for path in secrets_paths):
                try:
                    # Try [connections.snowflake] format first (highest priority)
                    if hasattr(st.secrets, 'connections') and hasattr(st.secrets.connections, 'snowflake'):
                        snowflake_config = st.secrets.connections.snowflake
                        if hasattr(snowflake_config, json_key):
                            value = getattr(snowflake_config, json_key)
                    # Fallback to environment variable format in secrets
                    elif env_key in st.secrets:
                        value = st.secrets[env_key]
                except Exception:
                    # Ignore secrets access errors
                    pass
        
        # 2. Try JSON configuration file
        if not value and self.config_data and json_key in self.config_data:
            value = self.config_data[json_key]
        
        # 3. Try environment variables (FALLBACK)
        if not value:
            value = os.environ.get(env_key)
        
        # 4. Use default if provided
        if not value and default is not None:
            value = default
            
        # 5. Check if required
        if required and not value:
            st.error(f"Missing required authentication: {json_key} (or {env_key})")
            st.stop()
            
        return str(value) if value is not None else None
    
    def _load_rsa_key_from_file(self) -> str:
        """Load RSA private key from file path"""
        try:
            if not os.path.exists(self.rsa_key_path):
                st.error(f":material/error: RSA key file not found: {self.rsa_key_path}")
                return None
                
            with open(self.rsa_key_path, 'r') as f:
                key_content = f.read()
            
            # RSA key loaded successfully
            return key_content
            
        except Exception as e:
            st.error(f":material/error: Failed to load RSA key from {self.rsa_key_path}: {str(e)}")
            return None
    
    def _validate_config(self):
        """Validate that all required authentication is present"""
        # Check if OAuth is enabled - if so, some validations are deferred
        oauth_enabled = self._is_oauth_enabled()
        
        required_fields = [
            ('account', 'Snowflake account identifier'),
            ('warehouse', 'Snowflake warehouse')
        ]
        
        # User is required unless OAuth is enabled (OAuth provides user identity)
        if not oauth_enabled:
            required_fields.append(('user', 'Snowflake username'))
        
        missing = []
        for field, description in required_fields:
            if not getattr(self, field, None):
                missing.append(f"{field} ({description})")
        
        if missing:
            st.error(":material/error: Missing required authentication fields:")
            for field in missing:
                st.error(f"  • {field}")
            st.error("Please check your config.json file or environment variables.")
            st.stop()
        
        # Validate authentication method - OAuth is also valid
        if not self.private_key and not self.password and not self.pat and not oauth_enabled:
            st.error(":material/error: No authentication method configured. Please provide either:")
            st.error("  • Okta OAuth (configure OKTA_ISSUER and OKTA_CLIENT_ID)")
            st.error("  • rsa_key_path (RSA Private Key file path) - RECOMMENDED")
            st.error("  • pat (Personal Access Token)")
            st.error("  • password (less secure)")
            st.stop()
    
    def _is_oauth_enabled(self) -> bool:
        """Check if Okta OAuth is configured."""
        # Check environment variables
        okta_issuer = os.environ.get('OKTA_ISSUER')
        okta_client_id = os.environ.get('OKTA_CLIENT_ID')
        
        if okta_issuer and okta_client_id:
            return True
        
        # Check Streamlit secrets
        if hasattr(st, 'secrets'):
            try:
                if 'okta' in st.secrets:
                    okta_config = st.secrets.okta
                    if okta_config.get('issuer') and okta_config.get('client_id'):
                        return True
            except Exception:
                pass
        
        return False
    
    def set_oauth_token(self, token: str, user_email: str = None):
        """
        Set OAuth token for authentication.
        
        Args:
            token: OAuth access token from Okta
            user_email: User's email from Okta user info
        """
        self.oauth_token = token
        if user_email:
            self.oauth_user_email = user_email
            # Update user field with OAuth user email
            self.user = user_email
    
    def get_auth_method(self) -> str:
        """
        Get the active authentication method.
        
        Returns:
            String identifying auth method: 'oauth', 'rsa', 'pat', 'password', or 'none'
        """
        if self.oauth_token:
            return 'oauth'
        elif self.private_key:
            return 'rsa'
        elif self.pat:
            return 'pat'
        elif self.password:
            return 'password'
        return 'none'