"""
File management utilities for Cortex Agent application.

This module provides file handling operations for working with Snowflake stages,
PDF processing, and file preview functionality in Streamlit applications.

Key Features:
- Snowflake stage file downloads with caching
- Presigned URL generation for secure file access
- PDF document processing with pdfium
- Multi-format file preview (PDF, images, audio) with Streamlit UI integration
- Configurable file preview settings and pagination

Usage:
    from modules.files.management import download_file_from_stage, get_presigned_url
    
    # Download file from Snowflake stage
    local_path = download_file_from_stage("documents/report.pdf")
    
    # Get presigned URL for secure access
    url = get_presigned_url("images/chart.jpg", expire_seconds=300)
    
    # Display file with scrollable preview
    display_file_with_scrollbar("documents/report.pdf", "pdf", citation_id="1")
"""
import streamlit as st
import os
import pypdfium2 as pdfium
from typing import Optional

from modules.config.app_config import ENABLE_FILE_PREVIEW, MAX_PDF_PAGES


@st.cache_resource
def download_file_from_stage(relative_path: str, session) -> str:
    """
    Download file from Snowflake stage to a local tmp directory.
    
    Args:
        relative_path: Path to the file in the Snowflake stage
        session: Snowpark session for file operations
        
    Returns:
        Local file path where the file was downloaded
    """
    local_dir = "/tmp/"
    relative_path = relative_path.replace(r"call_recordings/", "CALL_RECORDINGS/")
    session.file.get(f"DEMO_DB.DATA.DEMO_STAGE/{relative_path}", local_dir)
    local_file_path = os.path.join(local_dir, os.path.basename(relative_path))
    return local_file_path


@st.cache_data
def get_presigned_url(relative_path: str, session, expire_seconds: int = 360) -> str:
    """
    Returns a presigned URL to an object in the Snowflake stage.
    
    Args:
        relative_path: Path to the file in the Snowflake stage
        session: Snowpark session for SQL operations
        expire_seconds: URL expiration time in seconds (default: 360)
        
    Returns:
        Presigned URL string for secure file access
    """
    if "DICOM" in relative_path:
        STAGE = "OUTPUT_STAGE"
    else:
        STAGE = "DEMO_STAGE"
    
    sql = f"""
        SELECT GET_PRESIGNED_URL(@DEMO_DB.DATA.{STAGE}, '{relative_path}', {expire_seconds}) AS URL_LINK
    """
    res = session.sql(sql).collect()
    return res[0].URL_LINK


@st.cache_resource
def get_pdf(local_pdf_path: str) -> pdfium.PdfDocument:
    """
    Return a cached pdfium.PdfDocument object for a given local PDF path.
    
    Args:
        local_pdf_path: Path to the local PDF file
        
    Returns:
        Cached PdfDocument object for efficient processing
    """
    return pdfium.PdfDocument(local_pdf_path)


def display_file_with_scrollbar(relative_path: str, session, file_type: str = "pdf", 
                               unique_key: str = "", citation_id: str = ""):
    """
    Display a file preview (PDF or audio) inside an expander with a scrollbar.
    
    Args:
        relative_path: Path to the file in the Snowflake stage
        session: Snowpark session for file operations
        file_type: Type of file to display ("pdf", "jpg", "audio")
        unique_key: Unique key for Streamlit widget (optional)
        citation_id: Citation identifier for display purposes
    """
    # Check if file preview is enabled
    if not ENABLE_FILE_PREVIEW:
        st.info(f"File preview disabled. File: {os.path.basename(relative_path)}")
        return
        
    with st.expander(f"Citation:{citation_id} - {os.path.basename(relative_path)}", expanded=False):
        if file_type == "pdf":
            # PDF rendering logic
            try:
                local_file_path = download_file_from_stage(relative_path, session)
                if not os.path.exists(local_file_path):
                    st.error(f"Could not find the {file_type} at {local_file_path}.")
                    return

                pdf_doc = get_pdf(local_file_path)
                total_pages = len(pdf_doc)
                # Use configured max pages
                max_pages = min(MAX_PDF_PAGES, total_pages)
                page_numbers = (1, max_pages)
                start_page, end_page = page_numbers

                pdf_container = st.container(height=300)
                st.info(f"Showing {max_pages} of {total_pages} pages")
                
                for page_number in range(start_page - 1, end_page):
                    page = pdf_doc[page_number]
                    bitmap = page.render(scale=1.0)
                    pil_image = bitmap.to_pil()
                    with pdf_container:
                        st.image(pil_image, use_container_width=True)
            except Exception as e:
                st.error(f"Error displaying PDF: {str(e)}")
                    
        elif file_type == "jpg":
            try:
                presigned_url = get_presigned_url(relative_path, session, expire_seconds=600)
                st.write(relative_path)
                st.image(presigned_url)
            except Exception as e:
                st.error(f"Error displaying image: {str(e)}")
                
        elif file_type == "audio":
            try:
                presigned_url = get_presigned_url(relative_path, session, expire_seconds=600)
                st.write(presigned_url)
                st.audio(presigned_url, format="audio/mpeg")
            except Exception as e:
                st.error(f"Error displaying audio: {str(e)}")
        else:
            st.warning(f"File type '{file_type}' not supported for preview.")
