"""
Message and content data models for Cortex Agents API.

This module provides core data models for message handling including:
- Text content items and message content wrappers
- Complete message structures with role-based organization
- API request structures for agent interactions

All models use dataclasses with type hints and JSON serialization.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
import json

# =============================================================================
# Basic Content and Message Models
# =============================================================================

@dataclass
class TextContentItem:
    """Represents a single text content item within a message.
    
    This is the basic building block for message content. Currently supports
    only text content, but the structure allows for future extension to
    support other content types like images or files.
    
    Attributes:
        type: Content type identifier (always "text" for this class)
        text: The actual text content
    """
    type: str = "text"
    text: str = ""

@dataclass
class TableContentItem:
    """Represents a table content item within a message.
    
    This stores table data and metadata to allow tables to be persisted
    and replayed in conversation history.
    
    Attributes:
        type: Content type identifier (always "table" for this class)
        data: Table data as list of lists (rows)
        columns: Column names as list of strings
        title: Optional title for the table
    """
    type: str = "table"
    data: List[List[Any]] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    title: Optional[str] = None

@dataclass
class ChartContentItem:
    """Represents a chart content item within a message.
    
    This stores chart specifications to allow charts to be persisted
    and replayed in conversation history.
    
    Attributes:
        type: Content type identifier (always "chart" for this class)
        spec: Chart specification (usually Vega-Lite JSON)
        title: Optional title for the chart
    """
    type: str = "chart"
    spec: Dict[str, Any] = field(default_factory=dict)
    title: Optional[str] = None

@dataclass 
class MessageContentItem:
    """Wrapper class for content items to support future extensibility.
    
    This follows a wrapper pattern that allows for future expansion to support
    different content types (images, files, etc.) while maintaining backward
    compatibility. The Union type can be extended as new content types are added.
    
    Attributes:
        actual_instance: The wrapped content item (TextContentItem or TableContentItem)
    """
    actual_instance: Union[TextContentItem, TableContentItem, ChartContentItem] = field(default_factory=TextContentItem)

@dataclass
class Message:
    """Represents a complete message in the conversation.
    
    Messages follow a role-based structure where each message has a role
    (like "user" or "assistant") and content consisting of one or more
    content items.
    
    To fix thread message reformatting issues, this model now supports storing
    both raw content (for API communication) and processed content (for display).
    
    Attributes:
        id: Unique identifier for the message
        role: The role of the message sender (e.g., "user", "assistant")
        content: List of content items that make up the message (raw content)
        processed_content: Final processed content with citations, tables, etc. (display-ready)
        is_processed: Whether this message has been fully processed (avoid re-processing)
        raw_text: Original raw text for API compatibility
        citations: Citations associated with this message for persistence
    """
    role: str
    content: List[MessageContentItem] = field(default_factory=list)
    
    # Unique identifier for the message
    id: Optional[str] = field(default=None)
    
    # NEW: Processed content storage to fix thread reformatting bug
    processed_content: Optional[List[MessageContentItem]] = field(default=None)
    is_processed: bool = field(default=False)
    raw_text: Optional[str] = field(default=None)
    
    # Citations associated with this message
    citations: Optional[List[Dict]] = field(default=None)
    
    @classmethod
    def from_json(cls, json_str: str):
        """Create a Message instance from JSON data.
        
        Args:
            json_str: JSON string or dict containing message data
            
        Returns:
            Message: A new Message instance with parsed data
            
        Note:
            Uses safe field access with defaults to handle malformed JSON gracefully.
        """
        data = json.loads(json_str) if isinstance(json_str, str) else json_str
        content_items = []
        
        for item in data.get("content", []):
            content_type = item.get("type", "text")
            if content_type == "table":
                content_items.append(MessageContentItem(
                    actual_instance=TableContentItem(
                        type="table",
                        data=item.get("data", []),
                        columns=item.get("columns", []),
                        title=item.get("title")
                    )
                ))
            elif content_type == "chart":
                content_items.append(MessageContentItem(
                    actual_instance=ChartContentItem(
                        type="chart",
                        spec=item.get("spec", {}),
                        title=item.get("title")
                    )
                ))
            else:
                content_items.append(MessageContentItem(
                    actual_instance=TextContentItem(
                        type=item.get("type", "text"),
                        text=item.get("text", "")
                    )
                ))
        
        return cls(
            role=data.get("role", ""),
            content=content_items
        )
    
    def to_json(self) -> str:
        """Serialize the Message to a JSON string.
        
        Returns:
            str: JSON string representation suitable for API requests
        """
        content_list = []
        for item in self.content:
            if isinstance(item.actual_instance, TableContentItem):
                content_list.append({
                    "type": "table",
                    "data": item.actual_instance.data,
                    "columns": item.actual_instance.columns,
                    "title": item.actual_instance.title
                })
            elif isinstance(item.actual_instance, ChartContentItem):
                content_list.append({
                    "type": "chart",
                    "spec": item.actual_instance.spec,
                    "title": item.actual_instance.title
                })
            else:
                content_list.append({
                    "type": item.actual_instance.type,
                    "text": item.actual_instance.text
                })
        
        return json.dumps({
            "role": self.role,
            "content": content_list
        })
    
    def store_processed_content(self, processed_text: str, tables: List[Dict] = None, charts: List[Dict] = None) -> None:
        """
        Store final processed content to prevent reformatting in thread conversations.
        
        This method is called after streaming completion to store the final processed
        content (with citations processed, tables added, etc.) so that when the thread
        is continued, previous messages display exactly as they were originally shown.
        
        Args:
            processed_text: Final processed text with citations replaced ([1], [2], etc.)
            tables: List of table data to include in processed content
            charts: List of chart data to include in processed content
        """
        processed_items = []
        
        # Add processed text content
        if processed_text:
            text_content = TextContentItem(type="text", text=processed_text)
            processed_items.append(MessageContentItem(actual_instance=text_content))
        
        # Add table content if provided
        if tables:
            for table_data in tables:
                table_content = TableContentItem(
                    data=table_data.get('data', []),
                    columns=table_data.get('columns', []),
                    title=table_data.get('title')
                )
                processed_items.append(MessageContentItem(actual_instance=table_content))
        
        # Add chart content if provided  
        if charts:
            for chart_data in charts:
                chart_content = ChartContentItem(
                    spec=chart_data.get('spec', {}),
                    title=chart_data.get('title')
                )
                processed_items.append(MessageContentItem(actual_instance=chart_content))
        
        # Store the processed content and mark as processed
        self.processed_content = processed_items
        self.is_processed = True
    
    def get_display_content(self) -> List[MessageContentItem]:
        """
        Get content for display - uses processed content if available, falls back to raw content.
        
        Returns:
            List of MessageContentItem objects ready for display
        """
        if self.is_processed and self.processed_content is not None:
            return self.processed_content
        return self.content

@dataclass
class DataAgentRunRequest:
    """Represents the complete request structure for agent interactions.
    
    This model encapsulates all the data needed to make a request to the
    Cortex Agents API, including the model to use and the conversation history.
    
    Attributes:
        model: The AI model to use for the interaction
        messages: List of Message objects representing the conversation
    """
    model: str
    messages: List[Message] = field(default_factory=list)
    
    def to_json(self) -> str:
        """Serialize the request to JSON for API calls.
        
        Returns:
            str: Complete JSON payload ready for the Cortex Agents API
        """
        return json.dumps({
            "model": self.model,
            "messages": [
                {
                    "role": msg.role,
                    "content": [
                        {
                            "type": item.actual_instance.type,
                            "text": item.actual_instance.text
                        } if isinstance(item.actual_instance, TextContentItem) else (
                            {
                                "type": "table",
                                "data": item.actual_instance.data,
                                "columns": item.actual_instance.columns,
                                "title": item.actual_instance.title
                            } if isinstance(item.actual_instance, TableContentItem) else {
                                "type": "chart",
                                "spec": item.actual_instance.spec,
                                "title": item.actual_instance.title
                            }
                        ) for item in msg.content
                    ]
                } for msg in self.messages
            ]
        })

@dataclass
class ThreadAgentRunRequest:
    """Represents the complete request structure for thread-based agent interactions.
    
    This model encapsulates all the data needed to make a thread-based request to the
    Cortex Agents API, including thread context, model configuration, and tool choice.
    
    Based on the official Threads API documentation:
    https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run
    
    Attributes:
        models: Nested model configuration (e.g., {"orchestration": "claude-4-sonnet"})
        thread_id: Thread identifier for conversation context
        parent_message_id: ID of the parent message in the thread
        messages: List of Message objects (typically just the current user message)
        tool_choice: Optional tool selection configuration
    """
    models: Dict[str, str]
    thread_id: int
    parent_message_id: int
    messages: List[Message] = field(default_factory=list)
    tool_choice: Optional[Dict[str, Any]] = None
    
    def to_json(self) -> str:
        """Serialize the thread-based request to JSON for API calls.
        
        Returns:
            str: Complete JSON payload ready for the Cortex Agents API with thread context
        """
        request_data = {
            "models": self.models,
            "thread_id": self.thread_id,
            "parent_message_id": self.parent_message_id,
            "messages": [
                {
                    "role": msg.role,
                    "content": [
                        {
                            "type": item.actual_instance.type,
                            "text": item.actual_instance.text
                        } if isinstance(item.actual_instance, TextContentItem) else (
                            {
                                "type": "table",
                                "data": item.actual_instance.data,
                                "columns": item.actual_instance.columns,
                                "title": item.actual_instance.title
                            } if isinstance(item.actual_instance, TableContentItem) else {
                                "type": "chart",
                                "spec": item.actual_instance.spec,
                                "title": item.actual_instance.title
                            }
                        ) for item in msg.content
                    ]
                } for msg in self.messages
            ]
        }
        
        # Add tool_choice only if specified
        if self.tool_choice is not None:
            request_data["tool_choice"] = self.tool_choice
            
        return json.dumps(request_data)
    
    @classmethod
    def create_for_thread(cls, model: str, thread_id: int, parent_message_id: int, 
                         user_message: str, tool_choice: Optional[Dict[str, Any]] = None):
        """Convenience factory method for creating thread-based requests.
        
        Args:
            model: The orchestration model to use (e.g., "claude-4-sonnet")
            thread_id: Thread identifier
            parent_message_id: Parent message ID for threading
            user_message: The user's message text
            tool_choice: Optional tool selection configuration
            
        Returns:
            ThreadAgentRunRequest: Configured request object ready for API call
        """
        # Create user message using proper models
        user_text_content = TextContentItem(type="text", text=user_message)
        user_content_item = MessageContentItem(actual_instance=user_text_content)
        user_message_obj = Message(role="user", content=[user_content_item])
        
        return cls(
            models={"orchestration": model},
            thread_id=thread_id,
            parent_message_id=parent_message_id,
            messages=[user_message_obj],
            tool_choice=tool_choice
        )
