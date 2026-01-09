"""
Streaming event data models for Cortex Agents API.

This module provides data models for handling real-time streaming events including:
- Status updates during agent processing
- Incremental text and thinking deltas
- Tool usage and result events
- Table and chart data events
- Error handling events

All models use dataclasses with type hints and JSON serialization.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json

# =============================================================================
# Event Data Models
# =============================================================================
# These models handle parsing of streaming server-sent events from the
# Cortex Agents API. Each event type has its own data model with a
# consistent from_json pattern for robust JSON parsing.

@dataclass
class StatusEventData:
    """Handles status update events during agent processing.
    
    Event type: 'response.status'
    Used for displaying progress messages to users during agent execution.
    
    Attributes:
        message: Status message text
    """
    message: str
    
    @classmethod
    def from_json(cls, json_str: str):
        """Create instance from JSON data with safe parsing.
        
        Args:
            json_str: JSON string or dict containing event data
            
        Returns:
            StatusEventData: New instance with parsed data
        """
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        return cls(message=data.get("message", ""))

@dataclass
class TextDeltaEventData:
    """Handles incremental text updates during streaming responses.
    
    Event type: 'response.text.delta'
    Used for building streaming text responses character by character,
    allowing real-time display of agent responses.
    
    Attributes:
        content_index: Index of the content section being updated
        text: The incremental text to append
    """
    content_index: int
    text: str
    
    @classmethod
    def from_json(cls, json_str: str):
        """Create instance from JSON data with safe parsing.
        
        Args:
            json_str: JSON string or dict containing delta event data
            
        Returns:
            TextDeltaEventData: New instance with parsed data
        """
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        return cls(
            content_index=data.get("content_index", 0),
            text=data.get("text", "")
        )

@dataclass
class ThinkingDeltaEventData:
    """Handles incremental updates to the agent's thinking process.
    
    Event type: 'response.thinking.delta'
    Used for showing real-time agent reasoning to users as it develops,
    providing transparency into the agent's decision-making process.
    
    Attributes:
        content_index: Index of the thinking content section
        text: The incremental thinking text to append
    """
    content_index: int
    text: str
    
    @classmethod
    def from_json(cls, json_str: str):
        """Create instance from JSON data with safe parsing.
        
        Args:
            json_str: JSON string or dict containing thinking delta data
            
        Returns:
            ThinkingDeltaEventData: New instance with parsed data
        """
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        return cls(
            content_index=data.get("content_index", 0),
            text=data.get("text", "")
        )

@dataclass
class ThinkingEventData:
    """Handles complete thinking content when reasoning is finished.
    
    Event type: 'response.thinking'
    Used for displaying final thinking output after the agent has
    completed its reasoning process.
    
    Attributes:
        content_index: Index of the thinking content section
        text: The complete thinking text
    """
    content_index: int
    text: str
    
    @classmethod
    def from_json(cls, json_str: str):
        """Create instance from JSON data with safe parsing.
        
        Args:
            json_str: JSON string or dict containing thinking event data
            
        Returns:
            ThinkingEventData: New instance with parsed data
        """
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        return cls(
            content_index=data.get("content_index", 0),
            text=data.get("text", "")
        )

@dataclass
class ToolUseEventData:
    """Handles tool usage events when agent invokes external tools.
    
    Event type: 'response.tool_use'
    Used for showing users what tools the agent is using and with
    what parameters, providing transparency into agent actions.
    
    Attributes:
        content_index: Content section index
        tool_use: Dictionary containing tool information (name, parameters, etc.)
    """
    content_index: int
    tool_use: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_json(cls, json_str: str):
        """Create instance from JSON data with safe parsing.
        
        Args:
            json_str: JSON string or dict containing tool use event data
            
        Returns:
            ToolUseEventData: New instance with parsed data
        """
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        return cls(
            content_index=data.get("content_index", 0),
            tool_use=data.get("tool_use", {})
        )

@dataclass
class ToolResultEventData:
    """Handles tool execution results.
    
    Event type: 'response.tool_result'
    Used for displaying tool outputs and results to users,
    showing the data returned by external tool calls.
    
    Attributes:
        content_index: Content section index
        tool_result: Dictionary containing tool execution results
    """
    content_index: int
    tool_result: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_json(cls, json_str: str):
        """Create instance from JSON data with safe parsing.
        
        Args:
            json_str: JSON string or dict containing tool result event data
            
        Returns:
            ToolResultEventData: New instance with parsed data
        """
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        return cls(
            content_index=data.get("content_index", 0),
            tool_result=data.get("tool_result", {})
        )

@dataclass 
class ResultSetMetaData:
    """Contains metadata about table structure.
    
    Provides information about column types, names, and other structural
    details needed to properly render and interpret tabular data.
    
    Attributes:
        row_type: List of dictionaries describing column metadata
    """
    row_type: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class ResultSet:
    """Complete table data structure with both data and metadata.
    
    Combines raw tabular data with structural metadata to provide
    everything needed for proper table rendering and data interpretation.
    
    Attributes:
        data: Two-dimensional list containing the actual table data
        result_set_meta_data: Metadata about the table structure
    """
    data: List[List[Any]] = field(default_factory=list)
    result_set_meta_data: ResultSetMetaData = field(default_factory=ResultSetMetaData)

@dataclass
class TableEventData:
    """Handles tabular data responses from agents.
    
    Event type: 'response.table'
    Used for rendering tables and data visualizations in the UI
    when agents return structured data results.
    
    Attributes:
        content_index: Content section index
        result_set: Complete table data with metadata
    """
    content_index: int
    result_set: ResultSet = field(default_factory=ResultSet)
    
    @classmethod
    def from_json(cls, json_str: str):
        """Create instance from JSON data with nested result set parsing.
        
        Args:
            json_str: JSON string or dict containing table event data
            
        Returns:
            TableEventData: New instance with parsed table data and metadata
        """
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        result_set_data = data.get("result_set", {})
        return cls(
            content_index=data.get("content_index", 0),
            result_set=ResultSet(
                data=result_set_data.get("data", []),
                result_set_meta_data=ResultSetMetaData(
                    # Use official Snowflake SQL API field names: resultSetMetaData.rowType
                    row_type=result_set_data.get("resultSetMetaData", {}).get("rowType", [])
                )
            )
        )

@dataclass
class ChartEventData:
    """Handles chart/visualization specifications.
    
    Event type: 'response.chart'
    Used for rendering charts and visualizations when agents provide
    data visualization specifications (typically in Vega-Lite format).
    
    Attributes:
        content_index: Content section index
        chart_spec: JSON string containing chart specification
    """
    content_index: int
    chart_spec: str = ""
    
    @classmethod
    def from_json(cls, json_str: str):
        """Create instance from JSON data with safe parsing.
        
        Args:
            json_str: JSON string or dict containing chart event data
            
        Returns:
            ChartEventData: New instance with parsed chart specification
        """
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        return cls(
            content_index=data.get("content_index", 0),
            chart_spec=data.get("chart_spec", "")
        )

@dataclass
class ErrorEventData:
    """Handles error events from the API.
    
    Event type: 'error'
    Used for error handling and providing feedback to users when
    API operations fail or encounter issues.
    
    Attributes:
        code: Error code identifier
        message: Human-readable error message
    """
    code: str
    message: str
    
    @classmethod
    def from_json(cls, json_str: str):
        """Create instance from JSON data with safe parsing.
        
        Args:
            json_str: JSON string or dict containing error event data
            
        Returns:
            ErrorEventData: New instance with parsed error information
        """
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        return cls(
            code=data.get("code", ""),
            message=data.get("message", "")
        )
