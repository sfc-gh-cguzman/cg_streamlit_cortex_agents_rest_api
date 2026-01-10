"""
Agent discovery and management utilities.

This module provides functions for discovering and managing Snowflake Cortex Agents:
- Agent discovery using SQL (SHOW AGENTS IN ACCOUNT)
- Agent configuration parsing and validation
- Sample question formatting for UI display
- Cached agent retrieval with performance optimization

Key Features:
- SQL-based agent discovery across entire account
- Cached agent discovery (1 hour TTL) for performance
- Complete agent specification parsing via API
- Sample question extraction and formatting
- Error handling for agent access failures
"""
import json
import requests
import streamlit as st
from typing import List, Dict, Optional

from modules.logging import get_logger, log_performance, log_api_call


def discover_agents_via_sql(session) -> List[Dict]:
    """
    Discover all available agents in the account using SQL.
    
    Uses: SHOW AGENTS IN ACCOUNT
    
    Args:
        session: Snowpark session for executing SQL
        
    Returns:
        List of agent info dicts with database, schema, name, and display_name
    """
    logger = get_logger()
    
    try:
        # Execute SHOW AGENTS IN ACCOUNT and parse results
        sql = """
        show agents in account
        ->> select 
                parse_json("profile"):display_name::string as DISPLAY_NAME
                , concat_ws('.', "database_name", "schema_name", "name") FULLY_QUALIFIED_AGENT
                , "database_name" DATABASE_NAME
                , "schema_name" SCHEMA_NAME
                , "name" AGENT_NAME
            from $1
            order by AGENT_NAME
        """
        
        
        # Then query the results
        results = session.sql(sql).collect()
        
        agents = []
        for row in results:
            agents.append({
                'display_name': row['DISPLAY_NAME'],
                'fully_qualified_name': row['FULLY_QUALIFIED_AGENT'],
                'database': row['DATABASE_NAME'],
                'schema': row['SCHEMA_NAME'],
                'name': row['AGENT_NAME']
            })
        
        logger.info(f"SQL discovery found {len(agents)} agents in account")
        return agents
        
    except Exception as e:
        logger.error(f"SQL agent discovery failed: {e}")
        return []


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour to improve performance
@log_performance("agent_discovery")
@log_api_call("cortex_agents_list", "GET")
def get_available_agents(account: str, auth_token: str, ssl_verify: bool = True, _session=None) -> List[Dict]:
    """
    Retrieve all available Cortex Agents and their sample questions from the account.
    
    Uses SQL (SHOW AGENTS IN ACCOUNT) for discovery, then API for detailed config.
    
    Args:
        account: Snowflake account identifier
        auth_token: Bearer token for API calls
        ssl_verify: Whether to verify SSL certificates
        _session: Optional Snowpark session for SQL-based discovery (underscore prefix for cache)
        
    Returns:
        List of agent dictionaries with parsed configurations
    """
    logger = get_logger()
    base_url = f"https://{account}.snowflakecomputing.com/api/v2"
    
    logger.info(
        "Starting agent discovery",
        account=account,
        base_url=base_url,
        cache_ttl_hours=1
    )
    
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "User-Agent": "CortexAgentDemo/1.0"
    }
    
    all_agents = []
    
    # Try SQL-based discovery first (discovers ALL agents in account)
    agents_from_sql = []
    if _session is not None:
        agents_from_sql = discover_agents_via_sql(_session)
    
    if agents_from_sql:
        # Use SQL results - get detailed config for each discovered agent
        logger.info(f"Using SQL discovery results: {len(agents_from_sql)} agents found")
        
        for sql_agent in agents_from_sql:
            database = sql_agent['database']
            schema = sql_agent['schema']
            agent_name = sql_agent['name']
            
            try:
                # Get agent details via API
                detail_url = f"{base_url}/databases/{database}/schemas/{schema}/agents/{agent_name}"
                detail_response = requests.get(detail_url, headers=headers, verify=ssl_verify)
                
                if detail_response.status_code == 200:
                    agent_details = detail_response.json()
                    
                    # Parse the agent_spec JSON
                    agent_spec_str = agent_details.get('agent_spec', '{}')
                    try:
                        agent_spec = json.loads(agent_spec_str) if isinstance(agent_spec_str, str) else agent_spec_str
                    except json.JSONDecodeError:
                        agent_spec = {}
                    
                    # Extract sample questions
                    instructions = agent_spec.get('instructions', {})
                    sample_questions = instructions.get('sample_questions', [])
                    
                    # Build agent info - use display_name from SQL if available
                    agent_info = {
                        'name': agent_name,
                        'display_name': sql_agent.get('display_name') or agent_name.replace('_', ' ').title(),
                        'database': database,
                        'schema': schema,
                        'fully_qualified_name': sql_agent.get('fully_qualified_name'),
                        'owner': agent_details.get('owner', 'N/A'),
                        'created_on': agent_details.get('created_on', 'N/A'),
                        'comment': agent_details.get('comment', None),
                        'sample_questions': sample_questions,
                        'tools_count': len(agent_spec.get('tools', [])),
                        'models': agent_spec.get('models', {}),
                        'instructions': instructions,
                        'full_spec': agent_spec
                    }
                    
                    all_agents.append(agent_info)
                else:
                    logger.warning(f"Failed to get details for agent {agent_name}: HTTP {detail_response.status_code}")
            
            except requests.RequestException as e:
                logger.warning(
                    "Failed to fetch agent details",
                    agent_name=agent_name,
                    error=str(e),
                    database=database,
                    schema=schema
                )
                continue
    
    else:
        # Fallback to API-based discovery (original method)
        logger.info("Falling back to API-based agent discovery")
        
        # Primary location for agents (fallback)
        locations_to_check = [
            ("SNOWFLAKE_INTELLIGENCE", "AGENTS"),
        ]
        
        for database, schema in locations_to_check:
            try:
                # List agents in this location
                list_url = f"{base_url}/databases/{database}/schemas/{schema}/agents"
                logger.debug(
                    "Fetching agents from location",
                    database=database,
                    schema=schema,
                    url=list_url
                )
                response = requests.get(list_url, headers=headers, verify=ssl_verify)
                
                if response.status_code == 200:
                    agents_list = response.json()
                    logger.info(
                        "Found agents in location",
                        database=database,
                        schema=schema,
                        agent_count=len(agents_list)
                    )
                    
                    # Get detailed configuration for each agent
                    for agent in agents_list:
                        agent_name = agent.get('name', 'Unknown')
                        
                        try:
                            # Get agent details
                            detail_url = f"{base_url}/databases/{database}/schemas/{schema}/agents/{agent_name}"
                            detail_response = requests.get(detail_url, headers=headers, verify=ssl_verify)
                            
                            if detail_response.status_code == 200:
                                agent_details = detail_response.json()
                                
                                # Parse the agent_spec JSON
                                agent_spec_str = agent_details.get('agent_spec', '{}')
                                try:
                                    agent_spec = json.loads(agent_spec_str) if isinstance(agent_spec_str, str) else agent_spec_str
                                except json.JSONDecodeError:
                                    agent_spec = {}
                                
                                # Extract sample questions
                                instructions = agent_spec.get('instructions', {})
                                sample_questions = instructions.get('sample_questions', [])
                                
                                # Build agent info
                                agent_info = {
                                    'name': agent_name,
                                    'display_name': agent_name.replace('_', ' ').title(),
                                    'database': database,
                                    'schema': schema,
                                    'owner': agent_details.get('owner', 'N/A'),
                                    'created_on': agent_details.get('created_on', 'N/A'),
                                    'comment': agent.get('comment', None),
                                    'sample_questions': sample_questions,
                                    'tools_count': len(agent_spec.get('tools', [])),
                                    'models': agent_spec.get('models', {}),
                                    'instructions': instructions,
                                    'full_spec': agent_spec
                                }
                                
                                all_agents.append(agent_info)
                        
                        except requests.RequestException as e:
                            # Skip agents we can't access
                            logger.warning(
                                "Failed to fetch agent details",
                                agent_name=agent_name,
                                error=str(e),
                                database=database,
                                schema=schema
                            )
                            continue
            
            except requests.RequestException as e:
                # Skip locations we can't access
                logger.warning(
                    "Failed to access agent location",
                    database=database,
                    schema=schema,
                    error=str(e)
                )
                continue
    
    logger.info(
        "Agent discovery completed",
        total_agents_found=len(all_agents),
        agent_names=[agent['name'] for agent in all_agents]
    )
    return all_agents


def format_sample_questions_for_ui(sample_questions: List[Dict]) -> List[Dict]:
    """
    Convert sample questions from agent spec format to clean UI format
    Returns a simple list of question dictionaries for clean display
    """
    if not sample_questions:
        return []
    
    formatted_questions = []
    for idx, question_obj in enumerate(sample_questions, 1):
        question_text = question_obj.get('question', 'No question text')
        
        formatted_questions.append({
            'number': idx,
            'text': question_text,
            'key': f"sample_q_{idx}"
        })
    
    return formatted_questions
