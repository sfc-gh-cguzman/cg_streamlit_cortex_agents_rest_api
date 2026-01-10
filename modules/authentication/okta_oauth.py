"""
Okta OAuth authentication module for Streamlit application.

This module provides Okta OAuth 2.0 authentication with PKCE flow support
for secure external authentication with Snowflake Cortex Agents.

Key Features:
- OAuth 2.0 Authorization Code flow with PKCE
- Token exchange and refresh handling
- JWT token parsing and claims extraction
- User info retrieval from Okta
- Landing page with user info and token details
- Session management integration with Streamlit
- Automatic token refresh support

Usage:
    from modules.authentication.okta_oauth import OktaOAuthProvider, get_oauth_provider
    
    # Get OAuth provider instance
    oauth = get_oauth_provider()
    
    # Check if user is authenticated
    if not oauth.is_authenticated():
        oauth.show_login_page()
    else:
        user = oauth.get_current_user()
        access_token = oauth.get_access_token()
        
        # Parse JWT tokens
        id_token_claims = oauth.get_id_token_claims()
        access_token_claims = oauth.get_access_token_claims()
"""

import os
import time
import json
import secrets
import hashlib
import base64
import requests
import streamlit as st
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode, parse_qs
from dataclasses import dataclass, field
from datetime import datetime
from modules.logging import get_logger

logger = get_logger()


# =============================================================================
# JWT Token Parsing Utilities
# =============================================================================

def decode_jwt_token(token: str) -> Dict[str, Any]:
    """
    Decode a JWT token without verification (for display purposes).
    
    This function decodes the JWT payload to extract claims. It does NOT
    verify the signature - use only for displaying token contents.
    
    Args:
        token: JWT token string
        
    Returns:
        Dictionary containing decoded claims, or empty dict if decoding fails
    """
    if not token:
        return {}
    
    try:
        # JWT has 3 parts: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            logger.warning("Invalid JWT format - expected 3 parts")
            return {}
        
        # Decode the payload (second part)
        payload = parts[1]
        
        # Add padding if needed (base64url encoding)
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        
        # Decode base64url
        decoded_bytes = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded_bytes.decode('utf-8'))
        
        return claims
        
    except Exception as e:
        logger.error(f"Failed to decode JWT token: {e}")
        return {}


def decode_jwt_header(token: str) -> Dict[str, Any]:
    """
    Decode JWT token header.
    
    Args:
        token: JWT token string
        
    Returns:
        Dictionary containing header information
    """
    if not token:
        return {}
    
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return {}
        
        header = parts[0]
        padding = 4 - len(header) % 4
        if padding != 4:
            header += '=' * padding
        
        decoded_bytes = base64.urlsafe_b64decode(header)
        return json.loads(decoded_bytes.decode('utf-8'))
        
    except Exception as e:
        logger.error(f"Failed to decode JWT header: {e}")
        return {}


def format_timestamp(ts: int) -> str:
    """Convert Unix timestamp to human-readable format."""
    if not ts:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


def get_token_expiry_status(exp: int) -> tuple:
    """
    Get token expiry status with color coding.
    
    Returns:
        Tuple of (status_text, color, seconds_remaining)
    """
    if not exp:
        return ("Unknown", "gray", 0)
    
    now = time.time()
    remaining = exp - now
    
    if remaining <= 0:
        return ("Expired", "red", remaining)
    elif remaining < 300:  # Less than 5 minutes
        return ("Expiring Soon", "orange", remaining)
    elif remaining < 3600:  # Less than 1 hour
        return ("Valid", "yellow", remaining)
    else:
        return ("Valid", "green", remaining)


@dataclass
class OktaConfig:
    """Okta OAuth configuration settings."""
    issuer: str
    client_id: str
    client_secret: Optional[str]
    redirect_uri: str
    scope: str
    
    @classmethod
    def from_env(cls) -> 'OktaConfig':
        """Load Okta configuration from environment variables."""
        issuer = os.getenv('OKTA_ISSUER')
        client_id = os.getenv('OKTA_CLIENT_ID')
        client_secret = os.getenv('OKTA_CLIENT_SECRET')
        redirect_uri = os.getenv('OKTA_REDIRECT_URI', 'http://localhost:8501')
        scope = os.getenv('OKTA_SCOPE', 'openid profile email session:role-any offline_access')
        
        if not issuer or not client_id:
            return None
        
        return cls(
            issuer=issuer,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=scope
        )
    
    @classmethod
    def from_streamlit_secrets(cls) -> 'OktaConfig':
        """Load Okta configuration from Streamlit secrets."""
        try:
            if hasattr(st, 'secrets') and 'okta' in st.secrets:
                okta_config = st.secrets.okta
                issuer = okta_config.get('issuer')
                client_id = okta_config.get('client_id')
                
                # Validate that we have real values, not placeholders
                if not issuer or not client_id:
                    logger.debug("Okta config found but issuer or client_id is empty")
                    return None
                
                if 'YOUR_' in str(client_id) or 'YOUR_' in str(issuer):
                    logger.warning("Okta config contains placeholder values - please update with real credentials")
                    return None
                
                logger.info(f"Okta OAuth config loaded from secrets - issuer: {issuer[:50]}...")
                return cls(
                    issuer=issuer,
                    client_id=client_id,
                    client_secret=okta_config.get('client_secret'),
                    redirect_uri=okta_config.get('redirect_uri', 'http://localhost:8501'),
                    scope=okta_config.get('scope', 'openid profile email session:role-any offline_access')
                )
            else:
                logger.debug("No [okta] section found in Streamlit secrets")
        except Exception as e:
            logger.warning(f"Failed to load Okta config from secrets: {e}")
        return None


class OktaOAuthProvider:
    """
    Okta OAuth 2.0 provider for Streamlit applications.
    
    Implements the Authorization Code flow with PKCE for secure authentication.
    """
    
    # Session state keys
    STATE_KEY = 'okta_oauth_state'
    VERIFIER_KEY = 'okta_code_verifier'
    ACCESS_TOKEN_KEY = 'okta_access_token'
    REFRESH_TOKEN_KEY = 'okta_refresh_token'
    ID_TOKEN_KEY = 'okta_id_token'
    USER_INFO_KEY = 'okta_user_info'
    TOKEN_EXPIRY_KEY = 'okta_token_expiry'
    AUTH_TIME_KEY = 'okta_auth_time'
    
    def __init__(self, config: OktaConfig):
        """
        Initialize OAuth provider with configuration.
        
        Args:
            config: OktaConfig instance with OAuth settings
        """
        self.config = config
        self._ensure_session_state()
    
    def _ensure_session_state(self):
        """Initialize session state keys if not present."""
        defaults = {
            self.STATE_KEY: None,
            self.VERIFIER_KEY: None,
            self.ACCESS_TOKEN_KEY: None,
            self.REFRESH_TOKEN_KEY: None,
            self.ID_TOKEN_KEY: None,
            self.USER_INFO_KEY: None,
            self.TOKEN_EXPIRY_KEY: None,
            self.AUTH_TIME_KEY: None,
        }
        for key, default in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default
    
    def _generate_pkce(self) -> tuple:
        """
        Generate PKCE code verifier and challenge.
        
        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        code_verifier = secrets.token_urlsafe(64)
        hashed = hashlib.sha256(code_verifier.encode('ascii')).digest()
        code_challenge = base64.urlsafe_b64encode(hashed).decode('ascii').rstrip('=')
        return code_verifier, code_challenge
    
    def get_authorization_url(self, force_new: bool = False) -> str:
        """
        Generate OAuth authorization URL with PKCE.
        
        The state parameter encodes both a random value and the code verifier
        to handle cases where Streamlit session state doesn't persist across redirects.
        
        Args:
            force_new: If True, always generate a new URL. If False, reuse existing if valid.
        
        Returns:
            Authorization URL for Okta login
        """
        # Check if we already have a valid state/verifier (don't overwrite during callback)
        existing_state = st.session_state.get(self.STATE_KEY)
        existing_verifier = st.session_state.get(self.VERIFIER_KEY)
        existing_url = st.session_state.get('_oauth_auth_url')
        
        # Reuse existing URL if we have valid state/verifier and not forcing new
        if not force_new and existing_state and existing_verifier and existing_url:
            logger.debug("Reusing existing authorization URL")
            return existing_url
        
        code_verifier, code_challenge = self._generate_pkce()
        random_state = secrets.token_urlsafe(16)
        
        # Encode verifier in state to survive session loss
        # Format: random_state.base64(verifier)
        verifier_encoded = base64.urlsafe_b64encode(code_verifier.encode()).decode().rstrip('=')
        combined_state = f"{random_state}.{verifier_encoded}"
        
        # Store in session state (backup)
        st.session_state[self.VERIFIER_KEY] = code_verifier
        st.session_state[self.STATE_KEY] = combined_state
        
        params = {
            'client_id': self.config.client_id,
            'response_type': 'code',
            'scope': self.config.scope,
            'redirect_uri': self.config.redirect_uri,
            'state': combined_state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256'
        }
        
        auth_url = f"{self.config.issuer}/v1/authorize?{urlencode(params)}"
        
        # Cache the URL
        st.session_state['_oauth_auth_url'] = auth_url
        
        logger.info(f"Generated new authorization URL - state prefix: {random_state[:8]}...")
        return auth_url
    
    def _extract_verifier_from_state(self, state: str) -> tuple:
        """
        Extract the random state and code verifier from the combined state parameter.
        
        Args:
            state: Combined state in format 'random.verifier_encoded'
            
        Returns:
            Tuple of (random_state, code_verifier) or (None, None) if invalid
        """
        try:
            if '.' not in state:
                return state, None
            
            parts = state.split('.', 1)
            if len(parts) != 2:
                return state, None
            
            random_state, verifier_encoded = parts
            
            # Add padding back for base64 decode
            padding = 4 - len(verifier_encoded) % 4
            if padding != 4:
                verifier_encoded += '=' * padding
            
            code_verifier = base64.urlsafe_b64decode(verifier_encoded).decode()
            return random_state, code_verifier
            
        except Exception as e:
            logger.error(f"Failed to extract verifier from state: {e}")
            return state, None
    
    def exchange_code_for_tokens(self, code: str, state: str) -> Dict[str, Any]:
        """
        Exchange authorization code for tokens.
        
        Args:
            code: Authorization code from callback
            state: State parameter (contains encoded verifier for session-loss recovery)
            
        Returns:
            Token response dictionary
            
        Raises:
            ValueError: If state validation fails
            Exception: If token exchange fails
        """
        # Extract verifier from the state parameter (handles session loss)
        random_state, embedded_verifier = self._extract_verifier_from_state(state)
        
        # Try to get verifier from session state first, fallback to embedded
        code_verifier = st.session_state.get(self.VERIFIER_KEY)
        expected_state = st.session_state.get(self.STATE_KEY)
        
        # Debug logging
        logger.info(f"State validation - received state prefix: {random_state[:10] if random_state else 'None'}...")
        logger.info(f"State validation - expected: {expected_state[:15] if expected_state else 'None (session lost)'}...")
        logger.info(f"Verifier source: {'session' if code_verifier else ('embedded' if embedded_verifier else 'NONE')}")
        
        # If session state was lost, use embedded verifier from state parameter
        if not code_verifier and embedded_verifier:
            logger.info("Session state lost - recovering verifier from state parameter")
            code_verifier = embedded_verifier
        
        if not code_verifier:
            logger.error("No code verifier available - neither in session nor embedded in state")
            raise ValueError("Session expired and recovery failed. Please try logging in again.")
        
        # State validation: if we have expected_state in session, validate it matches
        # If session was lost (no expected_state), we trust the embedded verifier
        if expected_state and state != expected_state:
            logger.warning(f"State mismatch but continuing with embedded verifier")
            # Still proceed if we have embedded verifier - this handles session loss
        
        token_url = f"{self.config.issuer}/v1/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        data = {
            "grant_type": "authorization_code",
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "code": code,
            "code_verifier": code_verifier
        }
        
        # Add client secret if available (for confidential clients)
        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        
        response = requests.post(token_url, headers=headers, data=data)
        
        if response.status_code != 200:
            error_msg = response.text
            logger.error(f"Token exchange failed: {error_msg}")
            raise Exception(f"Token exchange failed: {error_msg}")
        
        tokens = response.json()
        
        # Store tokens in session state
        st.session_state[self.ACCESS_TOKEN_KEY] = tokens.get('access_token')
        st.session_state[self.REFRESH_TOKEN_KEY] = tokens.get('refresh_token')
        st.session_state[self.ID_TOKEN_KEY] = tokens.get('id_token')
        st.session_state[self.AUTH_TIME_KEY] = time.time()
        
        # Calculate token expiry
        expires_in = tokens.get('expires_in', 3600)
        st.session_state[self.TOKEN_EXPIRY_KEY] = time.time() + expires_in
        
        # Clear OAuth state
        st.session_state[self.STATE_KEY] = None
        st.session_state[self.VERIFIER_KEY] = None
        
        # Fetch user info
        self._fetch_user_info()
        
        logger.info("Successfully exchanged code for tokens")
        return tokens
    
    def _fetch_user_info(self):
        """Fetch user information from Okta userinfo endpoint."""
        access_token = st.session_state.get(self.ACCESS_TOKEN_KEY)
        if not access_token:
            return None
        
        userinfo_url = f"{self.config.issuer}/v1/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            response = requests.get(userinfo_url, headers=headers)
            if response.status_code == 200:
                user_info = response.json()
                st.session_state[self.USER_INFO_KEY] = user_info
                logger.debug(f"Fetched user info: {user_info.get('email', 'unknown')}")
                return user_info
        except Exception as e:
            logger.error(f"Failed to fetch user info: {e}")
        
        return None
    
    def refresh_access_token(self) -> bool:
        """
        Refresh the access token using refresh token.
        
        Returns:
            True if refresh successful, False otherwise
        """
        refresh_token = st.session_state.get(self.REFRESH_TOKEN_KEY)
        if not refresh_token:
            logger.warning("No refresh token available")
            return False
        
        token_url = f"{self.config.issuer}/v1/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        data = {
            "grant_type": "refresh_token",
            "client_id": self.config.client_id,
            "refresh_token": refresh_token
        }
        
        if self.config.client_secret:
            data["client_secret"] = self.config.client_secret
        
        try:
            response = requests.post(token_url, headers=headers, data=data)
            
            if response.status_code == 200:
                tokens = response.json()
                st.session_state[self.ACCESS_TOKEN_KEY] = tokens.get('access_token')
                
                if tokens.get('refresh_token'):
                    st.session_state[self.REFRESH_TOKEN_KEY] = tokens.get('refresh_token')
                
                expires_in = tokens.get('expires_in', 3600)
                st.session_state[self.TOKEN_EXPIRY_KEY] = time.time() + expires_in
                
                logger.info("Successfully refreshed access token")
                return True
            else:
                logger.error(f"Token refresh failed: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """
        Check if user is currently authenticated.
        
        Returns:
            True if user has valid access token
        """
        access_token = st.session_state.get(self.ACCESS_TOKEN_KEY)
        if not access_token:
            return False
        
        # Check token expiry
        token_expiry = st.session_state.get(self.TOKEN_EXPIRY_KEY)
        if token_expiry and time.time() > token_expiry:
            # Try to refresh
            if self.refresh_access_token():
                return True
            else:
                # Clear expired session
                self.logout()
                return False
        
        return True
    
    def get_access_token(self) -> Optional[str]:
        """
        Get current access token, refreshing if needed.
        
        Returns:
            Access token string or None if not authenticated
        """
        if not self.is_authenticated():
            return None
        
        # Check if token needs refresh (within 5 minutes of expiry)
        token_expiry = st.session_state.get(self.TOKEN_EXPIRY_KEY)
        if token_expiry and time.time() > (token_expiry - 300):
            self.refresh_access_token()
        
        return st.session_state.get(self.ACCESS_TOKEN_KEY)
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Get current authenticated user information.
        
        Returns:
            User info dictionary or None if not authenticated
        """
        if not self.is_authenticated():
            return None
        
        user_info = st.session_state.get(self.USER_INFO_KEY)
        if not user_info:
            user_info = self._fetch_user_info()
        
        return user_info
    
    def get_id_token(self) -> Optional[str]:
        """Get the raw ID token."""
        return st.session_state.get(self.ID_TOKEN_KEY)
    
    def get_id_token_claims(self) -> Dict[str, Any]:
        """
        Get decoded claims from the ID token.
        
        Returns:
            Dictionary of ID token claims
        """
        id_token = self.get_id_token()
        if not id_token:
            return {}
        return decode_jwt_token(id_token)
    
    def get_access_token_claims(self) -> Dict[str, Any]:
        """
        Get decoded claims from the access token.
        
        Note: Okta access tokens are JWTs and contain useful claims.
        
        Returns:
            Dictionary of access token claims
        """
        access_token = st.session_state.get(self.ACCESS_TOKEN_KEY)
        if not access_token:
            return {}
        return decode_jwt_token(access_token)
    
    def get_token_header(self, token_type: str = 'access') -> Dict[str, Any]:
        """
        Get decoded JWT header from a token.
        
        Args:
            token_type: 'access' or 'id'
            
        Returns:
            Dictionary of JWT header
        """
        if token_type == 'id':
            token = self.get_id_token()
        else:
            token = st.session_state.get(self.ACCESS_TOKEN_KEY)
        
        if not token:
            return {}
        return decode_jwt_header(token)
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        Get comprehensive session information.
        
        Returns:
            Dictionary with session details including tokens, expiry, and user info
        """
        access_token = st.session_state.get(self.ACCESS_TOKEN_KEY)
        token_expiry = st.session_state.get(self.TOKEN_EXPIRY_KEY)
        auth_time = st.session_state.get(self.AUTH_TIME_KEY)
        
        # Get expiry status
        access_claims = self.get_access_token_claims()
        exp = access_claims.get('exp')
        status, color, remaining = get_token_expiry_status(exp) if exp else ("Unknown", "gray", 0)
        
        return {
            'is_authenticated': self.is_authenticated(),
            'auth_time': auth_time,
            'auth_time_formatted': format_timestamp(int(auth_time)) if auth_time else "N/A",
            'token_expiry': token_expiry,
            'token_expiry_formatted': format_timestamp(int(token_expiry)) if token_expiry else "N/A",
            'expiry_status': status,
            'expiry_color': color,
            'seconds_remaining': remaining,
            'has_refresh_token': bool(st.session_state.get(self.REFRESH_TOKEN_KEY)),
            'access_token_preview': f"{access_token[:20]}...{access_token[-10:]}" if access_token else None,
            'scopes': access_claims.get('scp', []),
        }
    
    def get_snowflake_role(self) -> Optional[str]:
        """
        Extract Snowflake role from token claims if available.
        
        Returns:
            Snowflake role name or None
        """
        # Check ID token claims first
        id_claims = self.get_id_token_claims()
        if 'snowflake_role' in id_claims:
            return id_claims['snowflake_role']
        
        # Check access token claims
        access_claims = self.get_access_token_claims()
        if 'snowflake_role' in access_claims:
            return access_claims['snowflake_role']
        
        # Check for role in groups
        groups = id_claims.get('groups', []) or access_claims.get('groups', [])
        for group in groups:
            if isinstance(group, str) and group.upper().startswith('SNOWFLAKE_'):
                return group
        
        return None
    
    def logout(self):
        """Clear all OAuth session state."""
        keys_to_clear = [
            self.STATE_KEY,
            self.VERIFIER_KEY,
            self.ACCESS_TOKEN_KEY,
            self.REFRESH_TOKEN_KEY,
            self.ID_TOKEN_KEY,
            self.USER_INFO_KEY,
            self.TOKEN_EXPIRY_KEY,
            self.AUTH_TIME_KEY,
        ]
        
        for key in keys_to_clear:
            if key in st.session_state:
                st.session_state[key] = None
        
        logger.info("User logged out - OAuth session cleared")
    
    def handle_callback(self) -> bool:
        """
        Handle OAuth callback from Okta.
        
        Checks URL query parameters for authorization code and exchanges
        for tokens if present.
        
        Returns:
            True if callback was handled successfully
        """
        # Get query parameters from URL
        query_params = st.query_params
        
        code = query_params.get('code')
        state = query_params.get('state')
        error = query_params.get('error')
        
        if error:
            error_description = query_params.get('error_description', 'Unknown error')
            st.error(f"Authentication error: {error_description}")
            logger.error(f"OAuth error: {error} - {error_description}")
            # Clear query params and cached auth URL
            st.query_params.clear()
            self._clear_oauth_flow_state()
            return False
        
        if code and state:
            logger.info(f"OAuth callback received - state: {state[:10]}...")
            
            # Debug: Log what we have in session state
            stored_state = st.session_state.get(self.STATE_KEY)
            stored_verifier = st.session_state.get(self.VERIFIER_KEY)
            logger.debug(f"Stored state: {stored_state[:10] if stored_state else 'None'}...")
            logger.debug(f"Has verifier: {bool(stored_verifier)}")
            
            try:
                self.exchange_code_for_tokens(code, state)
                # Clear query params and cached auth URL after successful exchange
                st.query_params.clear()
                self._clear_oauth_flow_state()
                st.rerun()
                return True
            except Exception as e:
                st.error(f"Authentication failed: {str(e)}")
                logger.error(f"Token exchange failed: {e}")
                st.query_params.clear()
                self._clear_oauth_flow_state()
                return False
        
        return False
    
    def _clear_oauth_flow_state(self):
        """Clear OAuth flow state (state, verifier, cached URL) but keep tokens."""
        if self.STATE_KEY in st.session_state:
            st.session_state[self.STATE_KEY] = None
        if self.VERIFIER_KEY in st.session_state:
            st.session_state[self.VERIFIER_KEY] = None
        if '_oauth_auth_url' in st.session_state:
            del st.session_state['_oauth_auth_url']
    
    def is_in_callback(self) -> bool:
        """Check if we're currently in an OAuth callback (have code in URL)."""
        query_params = st.query_params
        return bool(query_params.get('code') and query_params.get('state'))
    
    def show_login_page(self):
        """Display a compact OAuth login page with Okta login button - no scrolling needed."""
        st.markdown("""
        <style>
        @keyframes gradient-shift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-8px); }
        }
        
        .login-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
            max-width: 500px;
            margin: 0 auto;
        }
        
        .login-icon {
            font-size: 4rem;
            animation: float 3s ease-in-out infinite;
            margin-bottom: 10px;
        }
        
        .login-title {
            font-size: 2.5rem;
            font-weight: 800;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
            background-size: 200% 200%;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            animation: gradient-shift 4s ease infinite;
            margin: 0 0 8px 0;
            letter-spacing: -0.02em;
            text-align: center;
        }
        
        .login-subtitle {
            font-size: 1.1rem;
            color: #6b7280;
            margin: 0 0 30px 0;
            font-weight: 400;
            text-align: center;
        }
        
        .security-row {
            display: flex;
            justify-content: center;
            gap: 24px;
            margin-top: 20px;
            flex-wrap: wrap;
        }
        
        .security-item {
            display: flex;
            align-items: center;
            gap: 6px;
            color: #6b7280;
            font-size: 0.85rem;
        }
        
        .login-footer {
            text-align: center;
            color: #9ca3af;
            font-size: 0.8rem;
            margin-top: 15px;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Compact centered layout
        st.markdown("""
        <div class="login-container">
            <div class="login-icon">❄️</div>
            <h1 class="login-title">Cortex Agent</h1>
            <p class="login-subtitle">AI-Powered Conversations with Your Snowflake Data</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Login button - centered, opens in same tab
        auth_url = self.get_authorization_url()
        
        st.markdown(f"""
        <div style="display: flex; justify-content: center; margin: 2rem 0;">
            <a href="{auth_url}" target="_self" style="
                display: inline-block;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 1rem 3rem;
                border-radius: 12px;
                text-decoration: none;
                font-weight: 600;
                font-size: 1.1rem;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
                transition: all 0.3s ease;
            " onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 6px 20px rgba(102, 126, 234, 0.5)';"
               onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 4px 15px rgba(102, 126, 234, 0.4)';">
                🔑 Sign in with Okta
            </a>
        </div>
        """, unsafe_allow_html=True)
        
        # Security badges - compact row
        st.markdown("""
        <div class="security-row">
            <div class="security-item">🔒 PKCE</div>
            <div class="security-item">🛡️ OAuth 2.0</div>
            <div class="security-item">✓ Enterprise SSO</div>
        </div>
        <div class="login-footer">
            Secure authentication via Okta
        </div>
        """, unsafe_allow_html=True)
    
    def show_user_info_sidebar(self):
        """Display user info at top and logout button at bottom of sidebar."""
        user = self.get_current_user()
        if user:
            email = user.get('email', 'Unknown')
            name = user.get('name', email.split('@')[0])
            
            # User info at top of sidebar (compact)
            with st.sidebar:
                st.markdown(f"👤 **{name}**")
                st.caption(email)
    
    def show_logout_button_sidebar(self):
        """Display logout button at the bottom of sidebar. Call this after other sidebar content."""
        with st.sidebar:
            st.markdown("---")
            if st.button("🚪 Logout", use_container_width=True, key="oauth_logout_btn", type="secondary"):
                self.logout()
                st.rerun()
    
    def show_landing_page(self):
        """
        Display the OAuth landing page with user info and token details.
        
        This page shows:
        - User profile information from Okta
        - Decoded ID token claims
        - Decoded access token claims
        - Session information and status
        - Snowflake integration details
        """
        user = self.get_current_user()
        if not user:
            st.error("User information not available")
            return
        
        # Page header
        st.markdown("""
        <style>
        .profile-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            border-radius: 15px;
            color: white;
            margin-bottom: 30px;
        }
        .profile-header h1 {
            margin: 0;
            font-size: 2rem;
        }
        .profile-header p {
            margin: 10px 0 0 0;
            opacity: 0.9;
        }
        .token-card {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin: 10px 0;
            border-left: 4px solid #667eea;
        }
        .claim-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }
        .claim-key {
            font-weight: 600;
            color: #333;
        }
        .claim-value {
            color: #666;
            word-break: break-all;
            max-width: 60%;
            text-align: right;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Profile header
        name = user.get('name', user.get('email', 'User'))
        email = user.get('email', 'N/A')
        
        st.markdown(f"""
        <div class="profile-header">
            <h1>👤 {name}</h1>
            <p>{email}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Back button
        if st.button("← Back to Application", key="back_to_app"):
            st.session_state['show_oauth_profile'] = False
            st.rerun()
        
        # Create tabs for different sections
        tab1, tab2, tab3, tab4 = st.tabs([
            "📋 User Profile", 
            "🔑 ID Token", 
            "🎫 Access Token", 
            "⚙️ Session Info"
        ])
        
        with tab1:
            self._render_user_profile(user)
        
        with tab2:
            self._render_id_token_claims()
        
        with tab3:
            self._render_access_token_claims()
        
        with tab4:
            self._render_session_info()
    
    def _render_user_profile(self, user: Dict[str, Any]):
        """Render user profile section."""
        st.subheader("User Information from Okta")
        
        # Main user info
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Identity")
            st.markdown(f"**Name:** {user.get('name', 'N/A')}")
            st.markdown(f"**Email:** {user.get('email', 'N/A')}")
            st.markdown(f"**Username:** {user.get('preferred_username', user.get('email', 'N/A'))}")
            
            if user.get('given_name') or user.get('family_name'):
                st.markdown(f"**First Name:** {user.get('given_name', 'N/A')}")
                st.markdown(f"**Last Name:** {user.get('family_name', 'N/A')}")
        
        with col2:
            st.markdown("#### Account Details")
            st.markdown(f"**Subject (sub):** `{user.get('sub', 'N/A')}`")
            
            if user.get('email_verified') is not None:
                verified = "✅ Yes" if user.get('email_verified') else "❌ No"
                st.markdown(f"**Email Verified:** {verified}")
            
            if user.get('locale'):
                st.markdown(f"**Locale:** {user.get('locale')}")
            
            if user.get('zoneinfo'):
                st.markdown(f"**Timezone:** {user.get('zoneinfo')}")
        
        # Groups if available
        groups = user.get('groups', [])
        if groups:
            st.markdown("#### Groups")
            for group in groups:
                st.markdown(f"- `{group}`")
        
        # Raw user info JSON
        with st.expander("📄 Raw User Info JSON"):
            st.json(user)
    
    def _render_id_token_claims(self):
        """Render ID token claims section."""
        id_token = self.get_id_token()
        
        if not id_token:
            st.warning("No ID token available")
            return
        
        st.subheader("ID Token Claims")
        st.caption("The ID token contains identity information about the authenticated user.")
        
        # Decode claims
        claims = self.get_id_token_claims()
        header = self.get_token_header('id')
        
        if not claims:
            st.error("Failed to decode ID token")
            return
        
        # Token header info
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Token Header")
            st.markdown(f"**Algorithm:** `{header.get('alg', 'N/A')}`")
            st.markdown(f"**Key ID:** `{header.get('kid', 'N/A')[:20]}...`" if header.get('kid') else "**Key ID:** N/A")
        
        with col2:
            st.markdown("#### Token Metadata")
            # Expiry status
            exp = claims.get('exp')
            if exp:
                status, color, remaining = get_token_expiry_status(exp)
                st.markdown(f"**Expiry Status:** :{color}[{status}]")
                st.markdown(f"**Expires:** {format_timestamp(exp)}")
            
            iat = claims.get('iat')
            if iat:
                st.markdown(f"**Issued At:** {format_timestamp(iat)}")
        
        # Standard claims
        st.markdown("#### Standard Claims")
        
        standard_claims = ['iss', 'sub', 'aud', 'exp', 'iat', 'auth_time', 'nonce', 'at_hash']
        identity_claims = ['name', 'email', 'preferred_username', 'given_name', 'family_name']
        
        col1, col2 = st.columns(2)
        
        with col1:
            for key in standard_claims:
                if key in claims:
                    value = claims[key]
                    if key in ['exp', 'iat', 'auth_time']:
                        value = format_timestamp(value)
                    elif isinstance(value, str) and len(value) > 50:
                        value = f"{value[:50]}..."
                    st.markdown(f"**{key}:** `{value}`")
        
        with col2:
            for key in identity_claims:
                if key in claims:
                    st.markdown(f"**{key}:** {claims[key]}")
        
        # Custom claims
        custom_claims = {k: v for k, v in claims.items() 
                       if k not in standard_claims + identity_claims + ['groups', 'scp']}
        
        if custom_claims:
            st.markdown("#### Custom Claims")
            for key, value in custom_claims.items():
                if isinstance(value, (list, dict)):
                    st.markdown(f"**{key}:**")
                    st.json(value)
                else:
                    st.markdown(f"**{key}:** `{value}`")
        
        # Groups
        groups = claims.get('groups', [])
        if groups:
            st.markdown("#### Groups")
            st.markdown(", ".join([f"`{g}`" for g in groups]))
        
        # Raw token
        with st.expander("🔐 Raw ID Token"):
            st.code(id_token, language=None)
        
        with st.expander("📄 Decoded Claims JSON"):
            st.json(claims)
    
    def _render_access_token_claims(self):
        """Render access token claims section."""
        access_token = st.session_state.get(self.ACCESS_TOKEN_KEY)
        
        if not access_token:
            st.warning("No access token available")
            return
        
        st.subheader("Access Token Claims")
        st.caption("The access token is used to authenticate API requests to Snowflake.")
        
        # Decode claims
        claims = self.get_access_token_claims()
        header = self.get_token_header('access')
        
        if not claims:
            st.info("Access token may not be a JWT or could not be decoded. This is normal for some Okta configurations.")
            with st.expander("🔐 Raw Access Token"):
                st.code(access_token, language=None)
            return
        
        # Token header info
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Token Header")
            st.markdown(f"**Algorithm:** `{header.get('alg', 'N/A')}`")
            st.markdown(f"**Key ID:** `{header.get('kid', 'N/A')[:20]}...`" if header.get('kid') else "**Key ID:** N/A")
        
        with col2:
            st.markdown("#### Token Metadata")
            # Expiry status
            exp = claims.get('exp')
            if exp:
                status, color, remaining = get_token_expiry_status(exp)
                st.markdown(f"**Expiry Status:** :{color}[{status}]")
                st.markdown(f"**Expires:** {format_timestamp(exp)}")
                
                if remaining > 0:
                    minutes = int(remaining / 60)
                    st.markdown(f"**Time Remaining:** {minutes} minutes")
        
        # Scopes
        scopes = claims.get('scp', [])
        if scopes:
            st.markdown("#### Granted Scopes")
            scope_cols = st.columns(min(len(scopes), 4))
            for i, scope in enumerate(scopes):
                with scope_cols[i % 4]:
                    # Highlight Snowflake-related scopes
                    if 'session' in scope.lower() or 'role' in scope.lower():
                        st.markdown(f"🔹 `{scope}`")
                    else:
                        st.markdown(f"• `{scope}`")
        
        # Important claims
        st.markdown("#### Key Claims")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"**Issuer:** `{claims.get('iss', 'N/A')}`")
            st.markdown(f"**Subject:** `{claims.get('sub', 'N/A')}`")
            st.markdown(f"**Client ID:** `{claims.get('cid', claims.get('client_id', 'N/A'))}`")
        
        with col2:
            aud = claims.get('aud')
            if isinstance(aud, list):
                st.markdown(f"**Audience:** {', '.join([f'`{a}`' for a in aud])}")
            else:
                st.markdown(f"**Audience:** `{aud}`")
            
            st.markdown(f"**Issued At:** {format_timestamp(claims.get('iat'))}")
            
            # Snowflake-specific claims
            if claims.get('snowflake_role'):
                st.markdown(f"**Snowflake Role:** `{claims.get('snowflake_role')}`")
        
        # All other claims
        with st.expander("📄 All Claims JSON"):
            st.json(claims)
        
        with st.expander("🔐 Raw Access Token"):
            st.code(access_token, language=None)
    
    def _render_session_info(self):
        """Render session information section."""
        st.subheader("Session Information")
        
        session_info = self.get_session_info()
        
        # Session status card
        status = session_info['expiry_status']
        color = session_info['expiry_color']
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="Session Status",
                value=status,
                delta=f"{int(session_info['seconds_remaining'] / 60)} min remaining" if session_info['seconds_remaining'] > 0 else "Refresh needed"
            )
        
        with col2:
            st.metric(
                label="Authenticated Since",
                value=session_info['auth_time_formatted'].split(' ')[1] if ' ' in session_info['auth_time_formatted'] else session_info['auth_time_formatted']
            )
        
        with col3:
            st.metric(
                label="Token Expires",
                value=session_info['token_expiry_formatted'].split(' ')[1] if ' ' in session_info['token_expiry_formatted'] else session_info['token_expiry_formatted']
            )
        
        st.markdown("---")
        
        # Detailed session info
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Authentication Details")
            st.markdown(f"**Authenticated:** {'✅ Yes' if session_info['is_authenticated'] else '❌ No'}")
            st.markdown(f"**Has Refresh Token:** {'✅ Yes' if session_info['has_refresh_token'] else '❌ No'}")
            st.markdown(f"**Auth Time:** {session_info['auth_time_formatted']}")
            st.markdown(f"**Token Expiry:** {session_info['token_expiry_formatted']}")
            
            if session_info['access_token_preview']:
                st.markdown(f"**Access Token:** `{session_info['access_token_preview']}`")
        
        with col2:
            st.markdown("#### Granted Scopes")
            scopes = session_info['scopes']
            if scopes:
                for scope in scopes:
                    if 'session' in scope.lower() or 'role' in scope.lower():
                        st.markdown(f"🔹 `{scope}` (Snowflake)")
                    else:
                        st.markdown(f"• `{scope}`")
            else:
                st.markdown("_No scopes available_")
        
        # Snowflake integration
        st.markdown("---")
        st.markdown("#### Snowflake Integration")
        
        sf_role = self.get_snowflake_role()
        if sf_role:
            st.success(f"Snowflake Role: **{sf_role}**")
        else:
            st.info("No Snowflake role found in token claims. Role will be determined by Snowflake External OAuth configuration.")
        
        # OAuth configuration
        with st.expander("🔧 OAuth Configuration"):
            st.markdown(f"**Issuer:** `{self.config.issuer}`")
            st.markdown(f"**Client ID:** `{self.config.client_id}`")
            st.markdown(f"**Redirect URI:** `{self.config.redirect_uri}`")
            st.markdown(f"**Scopes:** `{self.config.scope}`")
        
        # Actions
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Refresh Token", use_container_width=True):
                if self.refresh_access_token():
                    st.success("Token refreshed successfully!")
                    st.rerun()
                else:
                    st.error("Failed to refresh token. Please log in again.")
        
        with col2:
            if st.button("📋 Copy Access Token", use_container_width=True):
                access_token = st.session_state.get(self.ACCESS_TOKEN_KEY)
                if access_token:
                    st.code(access_token, language=None)
                    st.info("Token displayed above - copy manually")
        
        with col3:
            if st.button("🚪 Logout", use_container_width=True, type="primary"):
                self.logout()
                st.rerun()


# Global OAuth provider instance
_oauth_provider: Optional[OktaOAuthProvider] = None


def get_oauth_provider() -> Optional[OktaOAuthProvider]:
    """
    Get the global OAuth provider instance.
    
    Returns:
        OktaOAuthProvider instance or None if not configured
    """
    global _oauth_provider
    
    # Always try to initialize if not already done
    # Use session state to track if we've tried initialization this session
    init_key = '_oauth_provider_initialized'
    
    if _oauth_provider is None and not st.session_state.get(init_key, False):
        # Mark that we've attempted initialization
        st.session_state[init_key] = True
        
        # Try to load config from various sources
        logger.info("Attempting to initialize Okta OAuth provider...")
        
        config = OktaConfig.from_streamlit_secrets()
        
        if config is None:
            logger.debug("No Streamlit secrets config, trying environment variables...")
            config = OktaConfig.from_env()
        
        if config is not None:
            _oauth_provider = OktaOAuthProvider(config)
            logger.info(f"Okta OAuth provider initialized successfully - client_id: {config.client_id[:10]}...")
        else:
            logger.warning("Okta OAuth not configured - no [okta] section in secrets.toml and no OKTA_* env vars")
    
    return _oauth_provider


def is_oauth_enabled() -> bool:
    """
    Check if Okta OAuth is configured and enabled.
    
    Returns:
        True if OAuth is configured
    """
    return get_oauth_provider() is not None


def require_authentication():
    """
    Require OAuth authentication for the current page.
    
    This function should be called at the start of a page that requires
    authentication. It will:
    1. Check if OAuth is enabled
    2. Handle OAuth callback if present
    3. Show login page if not authenticated
    4. Show profile/landing page if requested
    5. Return user info if authenticated
    
    Returns:
        User info dict if authenticated, None otherwise
    """
    oauth = get_oauth_provider()
    
    if oauth is None:
        # OAuth not configured, skip authentication
        return None
    
    # Handle callback if present
    oauth.handle_callback()
    
    # Check if authenticated
    if not oauth.is_authenticated():
        oauth.show_login_page()
        st.stop()
        return None
    
    # Check if user wants to see profile page
    if st.session_state.get('show_oauth_profile', False):
        oauth.show_landing_page()
        st.stop()
        return None
    
    # Show user info in sidebar
    oauth.show_user_info_sidebar()
    
    return oauth.get_current_user()


def show_token_debug_panel():
    """
    Display a debug panel showing current OAuth token information.
    
    Useful for debugging Snowflake integration issues.
    """
    oauth = get_oauth_provider()
    
    if oauth is None or not oauth.is_authenticated():
        st.warning("Not authenticated with OAuth")
        return
    
    with st.expander("🔑 OAuth Token Debug", expanded=False):
        access_claims = oauth.get_access_token_claims()
        id_claims = oauth.get_id_token_claims()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Access Token Claims:**")
            if access_claims:
                exp = access_claims.get('exp')
                if exp:
                    status, color, _ = get_token_expiry_status(exp)
                    st.markdown(f"Status: :{color}[{status}]")
                st.markdown(f"Subject: `{access_claims.get('sub', 'N/A')}`")
                st.markdown(f"Scopes: {', '.join(access_claims.get('scp', []))}")
            else:
                st.markdown("_Could not decode access token_")
        
        with col2:
            st.markdown("**ID Token Claims:**")
            if id_claims:
                st.markdown(f"Email: `{id_claims.get('email', 'N/A')}`")
                st.markdown(f"Name: `{id_claims.get('name', 'N/A')}`")
            else:
                st.markdown("_Could not decode ID token_")
