"""
HTTP client utilities for external API communication.

This module provides CURL-based HTTP request functionality that mirrors
the working test_thread_curl.sh pattern for consistent API communication
with Snowflake Cortex Agents.

Key Features:
- CURL command execution with proper headers and authentication
- Error handling and timeout management
- Debug output support
- JSON payload handling for POST/PUT/PATCH requests
- Response parsing and status code extraction
"""
import json
import subprocess
import streamlit as st
from typing import Dict, Optional
from modules.config.session_state import get_session_manager

def execute_curl_request(method: str, url: str, auth_token: str, payload: Dict = None, timeout: int = 30) -> Dict:
    """
    Execute CURL request using the same pattern as the working test script.
    
    This function replicates the proven CURL command structure to ensure consistent 
    API communication with Snowflake Cortex Agents. It includes proper header 
    configuration, authentication, and response parsing.
    
    Args:
        method: HTTP method (GET, POST, DELETE, PUT, PATCH)
        url: Full URL including protocol and host (e.g., https://account.snowflakecomputing.com/api/...)
        auth_token: Bearer token for Authorization header
        payload: JSON payload dictionary for POST/PUT/PATCH requests (optional)
        timeout: Request timeout in seconds (default: 30)
    
    Returns:
        Dict containing:
        - status (int): HTTP status code (200, 404, 500, etc.)
        - content (str): Response body content
        - error (str|None): Error message if request failed
        - headers (dict): Response headers (currently empty placeholder)
        
    Raises:
        subprocess.TimeoutExpired: When request exceeds timeout limit
        Exception: For general CURL execution failures
        
    Example:
        response = execute_curl_request(
            method="POST",
            url="https://account.snowflakecomputing.com/api/v2/cortex/threads", 
            auth_token="your_token_here",
            payload={"origin_application": "MyApp"}
        )
        if response["status"] == 200:
            print(f"Success: {response['content']}")
    """
    try:
        # Build curl command like the working test script
        curl_cmd = [
            'curl',
            '-X', method,
            url,
            '-H', 'Content-Type: application/json',
            '-H', 'Accept: application/json', 
            '-H', f'Authorization: Bearer {auth_token}',
            '-w', '\n\nHTTP Status: %{http_code}\nResponse Time: %{time_total}s\n'
        ]
        
        # Add payload for POST requests
        if payload and method.upper() in ['POST', 'PUT', 'PATCH']:
            curl_cmd.extend(['-d', json.dumps(payload)])
        
        # Execute curl command with timeout
        result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=timeout)
        
        # Handle curl errors first
        if result.returncode != 0:
            error_msg = result.stderr or f"Curl command failed with return code {result.returncode}"
            if get_session_manager().is_debug_mode():
                st.error(f":material/error: CURL Failed: {error_msg}")
            return {
                "status": 500,
                "content": "",
                "error": error_msg,
                "headers": {}
            }
        
        # Parse response and extract HTTP status from output
        output = result.stdout
        status_code = 200  # Default to success
        content = output
        
        # Extract HTTP status from the write-out format
        if 'HTTP Status:' in output:
            lines = output.split('\n')
            for line in lines:
                if line.startswith('HTTP Status:'):
                    try:
                        status_code = int(line.split(':')[1].strip())
                        break
                    except:
                        pass
            
            # Remove the status line from content
            content_lines = []
            for line in lines:
                if not line.startswith('HTTP Status:') and not line.startswith('Response Time:'):
                    content_lines.append(line)
            content = '\n'.join(content_lines).strip()
        
        # Debug output only if enabled
        if get_session_manager().is_debug_mode():
            st.success(f":material/check_circle: CURL Success: HTTP {status_code}")
            if content:
                st.write(f":material/description: Response: {content[:100]}{'...' if len(content) > 100 else ''}")
        
        return {
            "status": status_code,
            "content": content,
            "error": None,
            "headers": {}
        }
        
    except subprocess.TimeoutExpired:
        st.error(f":material/error: CURL Timeout after {timeout} seconds")
        return {
            "status": 408,
            "content": "",
            "error": f"Request timeout after {timeout} seconds",
            "headers": {}
        }
    except Exception as e:
        st.error(f":material/error: CURL Exception: {str(e)}")
        return {
            "status": 500,
            "content": "",
            "error": f"Curl execution failed: {str(e)}",
            "headers": {}
        }
