"""
Text processing and data utilities for Cortex Agent application.

This module provides text parsing, file reference extraction, and SQL result
processing utilities for handling agent responses and data operations.

Key Features:
- File reference parsing from agent text responses
- Citation and reference extraction with regex patterns
- SQL result retrieval with DataFrame conversion
- Configurable data limits and caching for performance

Usage:
    from modules.utils.text_processing import parse_file_references_new, bot_retrieve_sql_results
    
    # Parse file references from text
    cleaned_text, references = parse_file_references_new(agent_response)
    
    # Execute SQL and get pandas DataFrame
    df = bot_retrieve_sql_results("SELECT * FROM my_table LIMIT 100", session)
"""
import re
import streamlit as st
import pandas as pd
from typing import Tuple, List

from modules.config.app_config import MAX_DATAFRAME_ROWS


def parse_file_references_new(text: str) -> Tuple[str, List[Tuple[str, str, str]]]:
    """
    Detect any PDF, MP3, or image file references and return cleaned text with references.
    
    This function uses regex patterns to identify file references in agent responses,
    extracting document names and file paths while cleaning the original text.
    
    Args:
        text: Input text containing potential file references
        
    Returns:
        Tuple containing:
        - cleaned_text (str): Text with file references removed
        - references (List[Tuple[str, str, str]]): List of (file_path, file_type, full_string) tuples
    """
    pattern = (
        r"(?P<full>"
        r"(?P<label>Document Name|Audio File Name)\s*:\s*" 
        r"(?P<path>[^\s:]+\.(?:pdf|mp3|jpg|jpeg))"
        r"(?:\:?)"
        r")"
    )

    references = []
    for match in re.finditer(pattern, text):
        full_string = match["full"]
        label = match["label"]
        file_path = match["path"]

        if file_path.endswith(".pdf"):
            file_type = "pdf"
        elif file_path.endswith(".mp3"):
            file_type = "audio"
        elif file_path.endswith(".jpeg"):
            file_type = "jpeg"
        elif file_path.endswith(".jpg"):
            file_type = "jpg"
        else:
            file_type = "audio"

        references.append((file_path, file_type, full_string))

    cleaned_text = text
    for _, _, full_string in references:
        cleaned_text = cleaned_text.replace(full_string, "")

    return cleaned_text.strip(), references


@st.cache_data
def bot_retrieve_sql_results(sql: str, session) -> pd.DataFrame:
    """
    Execute the SQL in Snowflake, returning a pandas DataFrame.
    
    Args:
        sql: SQL query string to execute
        session: Snowpark session for SQL operations
        
    Returns:
        pandas DataFrame with query results, limited by MAX_DATAFRAME_ROWS
    """
    return session.sql(sql).limit(MAX_DATAFRAME_ROWS).to_pandas()
