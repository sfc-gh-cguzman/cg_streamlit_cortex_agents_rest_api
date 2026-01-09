"""
File management module for Cortex Agent application.

This module provides file handling operations for working with Snowflake stages,
PDF processing, and file preview functionality in Streamlit applications.

Usage:
    from modules.files import download_file_from_stage, get_presigned_url, get_pdf
    from modules.files import display_file_with_scrollbar
    
    # Download and process files
    local_path = download_file_from_stage("documents/report.pdf", session)
    pdf_doc = get_pdf(local_path)
    
    # Display with preview
    display_file_with_scrollbar("documents/report.pdf", session, "pdf", citation_id="1")
"""

from .management import (
    download_file_from_stage,
    get_presigned_url,
    get_pdf,
    display_file_with_scrollbar
)

# Export all file management utilities
__all__ = [
    "download_file_from_stage",
    "get_presigned_url", 
    "get_pdf",
    "display_file_with_scrollbar"
]
