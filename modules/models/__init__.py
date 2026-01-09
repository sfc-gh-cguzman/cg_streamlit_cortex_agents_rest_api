"""
Cortex Agents API Data Models

This package provides comprehensive data models for the Cortex Agents API,
organized into logical modules:

- messages: Core message and content structures
- events: Streaming event data models  
- threads: Thread management models

All models use dataclasses with type hints and JSON serialization capabilities.
"""

# Import all models for convenient access
from .messages import (
    TextContentItem,
    TableContentItem,
    ChartContentItem,
    MessageContentItem,
    Message,
    DataAgentRunRequest,
    ThreadAgentRunRequest
)

from .events import (
    StatusEventData,
    TextDeltaEventData,
    ThinkingDeltaEventData,
    ThinkingEventData,
    ToolUseEventData,
    ToolResultEventData,
    ResultSetMetaData,
    ResultSet,
    TableEventData,
    ChartEventData,
    ErrorEventData
)

from .threads import (
    ThreadMetadata,
    ThreadMessage,
    ThreadResponse
)

# Export all model classes
__all__ = [
    # Message models
    "TextContentItem",
    "TableContentItem",
    "ChartContentItem",
    "MessageContentItem", 
    "Message",
    "DataAgentRunRequest",
    "ThreadAgentRunRequest",
    
    # Event models
    "StatusEventData",
    "TextDeltaEventData",
    "ThinkingDeltaEventData",
    "ThinkingEventData",
    "ToolUseEventData",
    "ToolResultEventData",
    "ResultSetMetaData",
    "ResultSet",
    "TableEventData",
    "ChartEventData",
    "ErrorEventData",
    
    # Thread models
    "ThreadMetadata",
    "ThreadMessage",
    "ThreadResponse"
]
