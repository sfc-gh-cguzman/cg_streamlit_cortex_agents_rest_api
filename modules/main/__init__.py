"""
Main Application Module

This module contains the main application logic and entry points for the
Cortex Agent external Streamlit application.

Key Components:
- app: Main application functions and core logic
- main(): Primary application entry point

The main module orchestrates all other modules to provide the complete
Cortex Agent integration experience.
"""

from .app import main

__all__ = ['main']
