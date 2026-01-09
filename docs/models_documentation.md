# Models Module Documentation

## Overview

The `modules/models/` package contains comprehensive data models for Snowflake's Cortex Agents API with Thread support. It provides a structured approach to handling all API interactions, streaming events, and thread management using Python dataclasses with type hints and JSON serialization capabilities.

**Key Architecture Change**: The models have been refactored from a single `models.py` file into a well-organized modular package with focused sub-modules.

## Modular Structure

The models package is organized into three main sub-modules:

1. **messages.py** - Core message and content structures for agent communication
2. **events.py** - Data models for parsing streaming server-sent events
3. **threads.py** - Models for managing conversation threads

**Import Pattern**:

```python
# All models available through package import
from modules.models import (
    Message, TextContentItem, TableContentItem, ChartContentItem,  # Content types
    MessageContentItem, DataAgentRunRequest, ThreadAgentRunRequest,  # from messages.py
    StatusEventData, TextDeltaEventData, ToolUseEventData,          # from events.py  
    ThreadMetadata, ThreadMessage, ThreadResponse                   # from threads.py
)
```

## Dependencies

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
import json
```

## Module 1: messages.py - Core Message Structures

**Location**: `modules/models/messages.py`

This module contains the fundamental data structures for message communication with Cortex Agents.

### TextContentItem

```python
@dataclass
class TextContentItem:
    type: str = "text"
    text: str = ""
```

**Purpose**: Represents a single text content item within a message.

**Fields**:

- `type`: Content type (defaults to "text")
- `text`: The actual text content

**Usage**: Building blocks for message content arrays.

### TableContentItem

```python
@dataclass
class TableContentItem:
    type: str = "table"
    data: List[List[Any]] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    title: Optional[str] = None
```

**Purpose**: Represents table content within a message for persistent storage and replay.

**Fields**:

- `type`: Content type identifier (always "table")
- `data`: Table data as list of lists (rows)
- `columns`: Column names as list of strings
- `title`: Optional title for the table

**Usage**: Storing and replaying table data in conversation history.

### ChartContentItem

```python
@dataclass
class ChartContentItem:
    type: str = "chart"
    spec: Dict[str, Any] = field(default_factory=dict)
    title: Optional[str] = None
```

**Purpose**: Represents chart content within a message for persistent storage and replay.

**Fields**:

- `type`: Content type identifier (always "chart")
- `spec`: Chart specification (usually Vega-Lite JSON)
- `title`: Optional title for the chart

**Usage**: Storing and replaying chart visualizations in conversation history.

### MessageContentItem

```python
@dataclass 
class MessageContentItem:
    actual_instance: Union[TextContentItem, TableContentItem, ChartContentItem] = field(default_factory=TextContentItem)
```

**Purpose**: Wrapper class for content items to support multiple content types.

**Fields**:

- `actual_instance`: The wrapped content item (TextContentItem, TableContentItem, or ChartContentItem)

**Design Pattern**: This follows a wrapper pattern that supports different content types (text, tables, charts) while maintaining backward compatibility and type safety.

### Message

```python
@dataclass
class Message:
    role: str
    content: List[MessageContentItem] = field(default_factory=list)
    id: Optional[str] = field(default=None)
    processed_content: Optional[List[MessageContentItem]] = field(default=None)
    is_processed: bool = field(default=False)
    raw_text: Optional[str] = field(default=None)
    citations: Optional[List[Dict]] = field(default=None)
```

**Purpose**: Represents a complete message in the conversation with role-based structure and advanced processing capabilities.

**Fields**:

- `role`: The role of the message sender (e.g., "user", "assistant")
- `content`: List of content items that make up the message (raw content)
- `id`: Unique identifier for the message
- `processed_content`: Final processed content with citations, tables, etc. (display-ready)
- `is_processed`: Whether this message has been fully processed (avoid re-processing)
- `raw_text`: Original raw text for API compatibility  
- `citations`: Citations associated with this message for persistence

**Key Methods**:

#### Message.from_json(cls, json_str: str)

- **Purpose**: Class method to deserialize JSON data into Message objects
- **Parameters**: `json_str` - JSON string or dict containing message data
- **Returns**: Message instance
- **Usage**: Parsing API responses into structured objects

#### Message.to_json(self) -> str

- **Purpose**: Serialize Message object to JSON string
- **Returns**: JSON string representation
- **Usage**: Preparing data for API requests

#### Message.store_processed_content(self, processed_text: str, tables: List[Dict] = None, charts: List[Dict] = None) -> None

- **Purpose**: Store final processed content to prevent reformatting in thread conversations
- **Parameters**:
  - `processed_text`: Final processed text with citations and formatting
  - `tables`: Optional list of table data
  - `charts`: Optional list of chart specifications
- **Usage**: Called after streaming completion to preserve display formatting

#### Message.get_effective_content(self) -> List[MessageContentItem]

- **Purpose**: Get the most appropriate content (processed if available, raw otherwise)
- **Returns**: List of MessageContentItem objects ready for display
- **Usage**: Ensures proper content display in thread conversations

**JSON Structure**:

```json
{
    "role": "user",
    "content": [
        {
            "type": "text",
            "text": "Hello, how can you help me?"
        }
    ]
}
```

### DataAgentRunRequest

```python
@dataclass
class DataAgentRunRequest:
    model: str
    messages: List[Message] = field(default_factory=list)
```

**Purpose**: Represents the complete request structure for agent interactions.

**Fields**:

- `model`: The AI model to use for the interaction
- `messages`: List of Message objects representing the conversation

**Key Methods**:

#### DataAgentRunRequest.to_json(self) -> str

- **Purpose**: Serialize request to JSON for API calls
- **Returns**: Complete JSON payload for agent API
- **Usage**: Converting Python objects to API-compatible JSON

### ThreadAgentRunRequest

```python
@dataclass
class ThreadAgentRunRequest:
    models: Dict[str, str]
    thread_id: int
    parent_message_id: int
    messages: List[Message] = field(default_factory=list)
    tool_choice: Optional[Dict[str, Any]] = None
```

**Purpose**: Represents the complete request structure for thread-based agent interactions.

**Fields**:

- `models`: Nested model configuration (e.g., {"orchestration": "claude-4-sonnet"})
- `thread_id`: Thread identifier for conversation context
- `parent_message_id`: ID of the parent message in the thread
- `messages`: List of Message objects (typically just the current user message)
- `tool_choice`: Optional tool selection configuration

**Key Methods**:

#### ThreadAgentRunRequest.to_json(self) -> str

- **Purpose**: Serialize thread-based request to JSON for API calls
- **Returns**: Complete JSON payload for Cortex Agents API with thread context
- **Usage**: Converting thread requests to API-compatible format

#### ThreadAgentRunRequest.create_for_thread(cls, model: str, thread_id: int, parent_message_id: int, user_message: str, tool_choice: Optional[Dict[str, Any]] = None)

- **Purpose**: Convenience factory method for creating thread-based requests
- **Parameters**: Model name, thread/parent IDs, user message text, optional tool choice
- **Returns**: Configured ThreadAgentRunRequest ready for API call
- **Usage**: Simplified thread request creation

## Module 2: events.py - Streaming Event Data Models

**Location**: `modules/models/events.py`

This module handles the parsing of streaming server-sent events from the Cortex Agents API. Each event type has its own data model with a consistent `from_json` pattern.

**Module Features**:

- Type-safe event parsing
- Consistent `from_json` deserialization
- Support for all Cortex API event types
- Defensive programming with safe defaults

### StatusEventData

```python
@dataclass
class StatusEventData:
    message: str
```

**Purpose**: Handles status update events during agent processing.
**Event Type**: `response.status`
**Usage**: Displaying progress messages to users

### TextDeltaEventData

```python
@dataclass
class TextDeltaEventData:
    content_index: int
    text: str
```

**Purpose**: Handles incremental text updates during streaming responses.
**Event Type**: `response.text.delta`
**Fields**:

- `content_index`: Index of the content section being updated (scoped per request_id)
- `text`: The incremental text to append

**Content Scoping Architecture**: The `content_index` is now scoped per `request_id` to ensure thread integrity. Content management uses `(request_id, content_index)` pairs to prevent cross-request interference. This ensures that:

- **Thread Isolation**: Content from previous requests remains intact
- **Agent Re-evaluation Safety**: Re-evaluation only affects the current request
- **Content Persistence**: Tables, charts, and text from earlier requests are preserved

**Usage**: Building streaming text responses character by character with request-scoped content containers. Each request maintains its own content namespace, preventing previous responses from being overwritten by subsequent requests.

#### Request-Scoped Content Management Architecture

**Implementation**: Content containers use composite keys `(request_id, content_index)` instead of just `content_index`:

```python
# Before (BROKEN): Content could be overwritten across requests
content_map[content_index] = container

# After (FIXED): Content is isolated per request
content_key = (request_id, content_index)
content_map[content_key] = container
```

**Thread Structure**:

```text
Thread
├── Request A: (req_A, 0), (req_A, 1), (req_A, 2)  ← PROTECTED
├── Request B: (req_B, 0), (req_B, 1), (req_B, 2)  ← ISOLATED  
└── Request C: (req_C, 0), (req_C, 1), (req_C, 2)  ← ISOLATED
```

**Benefits**:

- **Cross-Request Protection**: Previous responses remain intact
- **Safe Agent Re-evaluation**: Only current request content is cleared
- **Complete Thread History**: Full conversation context preserved
- **Content Type Persistence**: Tables, charts, citations all protected

### ThinkingDeltaEventData

```python
@dataclass
class ThinkingDeltaEventData:
    content_index: int
    text: str
```

**Purpose**: Handles incremental updates to the agent's thinking process.
**Event Type**: `response.thinking.delta`
**Usage**: Showing real-time agent reasoning to users

### ThinkingEventData

```python
@dataclass
class ThinkingEventData:
    content_index: int
    text: str
```

**Purpose**: Handles complete thinking content when reasoning is finished.
**Event Type**: `response.thinking`
**Usage**: Displaying final thinking output

### ToolUseEventData

```python
@dataclass
class ToolUseEventData:
    content_index: int
    tool_use: Dict[str, Any] = field(default_factory=dict)
```

**Purpose**: Handles tool usage events when agent invokes external tools.
**Event Type**: `response.tool_use`
**Fields**:

- `content_index`: Content section index
- `tool_use`: Dictionary containing tool information (name, parameters, etc.)

**Usage**: Showing users what tools the agent is using

### ToolResultEventData

```python
@dataclass
class ToolResultEventData:
    content_index: int
    tool_result: Dict[str, Any] = field(default_factory=dict)
```

**Purpose**: Handles tool execution results.
**Event Type**: `response.tool_result`
**Fields**:

- `content_index`: Content section index
- `tool_result`: Dictionary containing tool execution results

**Usage**: Displaying tool outputs and results

### TableEventData

```python
@dataclass
class TableEventData:
    content_index: int
    result_set: ResultSet = field(default_factory=ResultSet)
```

**Purpose**: Handles tabular data responses from agents.
**Event Type**: `response.table`

**Supporting Classes**:

#### ResultSetMetaData

```python
@dataclass
class ResultSetMetaData:
    row_type: List[Dict[str, Any]] = field(default_factory=list)
```

**Purpose**: Contains metadata about table structure (column types, names, etc.)

#### ResultSet

```python
@dataclass
class ResultSet:
    data: List[List[Any]] = field(default_factory=list)
    result_set_meta_data: ResultSetMetaData = field(default_factory=ResultSetMetaData)
```

**Purpose**: Complete table data structure with both data and metadata

**Usage**: Rendering tables and data visualizations in the UI

### ChartEventData

```python
@dataclass
class ChartEventData:
    content_index: int
    chart_spec: str = ""
```

**Purpose**: Handles chart/visualization specifications.
**Event Type**: `response.chart`
**Fields**:

- `chart_spec`: JSON string containing chart specification (typically Vega-Lite format)

**Usage**: Rendering charts and visualizations

### ErrorEventData

```python
@dataclass
class ErrorEventData:
    code: str
    message: str
```

**Purpose**: Handles error events from the API.
**Event Type**: `error`
**Usage**: Error handling and user feedback

## Module 3: threads.py - Thread Management Models

**Location**: `modules/models/threads.py`

This module handles the thread-based conversation system that allows maintaining conversation context across multiple interactions.

**Module Features**:

- Thread metadata management
- Message persistence models
- Thread response handling
- Integration with Cortex Agents Thread API

### ThreadMetadata

```python
@dataclass
class ThreadMetadata:
    thread_id: str
    thread_name: str
    origin_application: str
    created_on: int
    updated_on: int
```

**Purpose**: Contains metadata about a conversation thread.
**Fields**:

- `thread_id`: Unique identifier for the thread
- `thread_name`: Human-readable thread name
- `origin_application`: Application that created the thread
- `created_on`: Unix timestamp of creation
- `updated_on`: Unix timestamp of last update

### ThreadMessage

```python
@dataclass
class ThreadMessage:
    message_id: int
    parent_id: Optional[int]
    created_on: int
    role: str
    message_payload: str
    request_id: str
```

**Purpose**: Represents a single message within a thread.
**Fields**:

- `message_id`: Unique message identifier
- `parent_id`: ID of parent message (for threading)
- `created_on`: Creation timestamp
- `role`: Message role ("user" or "assistant")
- `message_payload`: The actual message content
- `request_id`: API request identifier

### ThreadResponse

```python
@dataclass
class ThreadResponse:
    metadata: ThreadMetadata
    messages: List[ThreadMessage]
```

**Purpose**: Complete thread response containing metadata and all messages.
**Usage**: Retrieving complete conversation threads from the API

## Design Patterns and Architecture

### Consistent JSON Serialization

All event data models follow a consistent pattern:

```python
@classmethod
def from_json(cls, json_str: str):
    data = json.loads(json_str) if isinstance(json_str, str) else json_str
    return cls(
        # field mappings with safe defaults
    )
```

**Benefits**:

- Robust JSON parsing with error handling
- Consistent interface across all models
- Safe defaults prevent crashes on malformed data

### Dataclass with Field Defaults

```python
@dataclass
class ExampleModel:
    required_field: str
    optional_field: List[SomeType] = field(default_factory=list)
```

**Benefits**:

- Immutable by default with explicit mutability
- Type safety with runtime checking
- Clean, readable code structure
- Automatic `__init__`, `__repr__`, and `__eq__` methods

### Union Types for Extensibility

```python
actual_instance: Union[TextContentItem] = field(default_factory=TextContentItem)
```

**Benefits**:

- Future-proof design for adding new content types
- Type-safe extensibility
- Maintains backward compatibility

## Integration with Modular Application

The models package is imported and used throughout the modular Streamlit application:

```python
# Main application integration
from modules.models import (
    Message,                    # Core message structure
    MessageContentItem,         # Content wrapper
    TextContentItem,           # Text content handling
    DataAgentRunRequest,       # API request structure
    StatusEventData,           # Stream event handling
    TextDeltaEventData,        # Text streaming
    ThreadMetadata,            # Thread information
    ThreadMessage,             # Thread messages
    ThreadResponse             # Thread responses
)
```

**Modular Integration Points**:

1. **Request Building**: `modules.api.cortex_integration` uses DataAgentRunRequest and Message models
2. **Stream Processing**: `modules.api.cortex_integration` uses event data models for parsing
3. **Thread Management**: `modules.threads.management` uses thread models for persistence
4. **Type Safety**: All modules benefit from type hints for IDE support and runtime checking
5. **UI Rendering**: `modules.main.app` uses models for consistent data handling

**Cross-Module Usage Examples**:

```python
# In modules/main/app.py
from modules.models import Message, TextContentItem, MessageContentItem

def process_message(user_input: str) -> Message:
    text_content = TextContentItem(type="text", text=user_input)
    content_item = MessageContentItem(actual_instance=text_content)
    return Message(role="user", content=[content_item])

# In modules/api/cortex_integration.py
from modules.models import DataAgentRunRequest, StatusEventData

def build_request(messages: List[Message]) -> DataAgentRunRequest:
    return DataAgentRunRequest(model="llama", messages=messages)

# In modules/threads/management.py
from modules.models import ThreadResponse, ThreadMessage

def parse_thread_response(json_data: dict) -> ThreadResponse:
    return ThreadResponse.from_json(json_data)
```

## Error Handling Strategy

The models implement defensive programming:

- JSON parsing with fallback to dict input
- Safe field access with `.get()` and default values
- Optional typing where fields might be missing
- Graceful handling of malformed API responses

## Performance Considerations

- **Dataclasses**: Efficient memory usage and fast attribute access
- **Default Factories**: Prevent mutable default arguments
- **Lazy Loading**: Models are created only when needed during stream processing
- **Type Hints**: Enable static analysis and optimization

## Modular Benefits

The modular models package provides significant advantages over the previous monolithic approach:

### 1. Organization and Clarity

- **Focused Modules**: Each module has a clear purpose (messages, events, threads)
- **Easy Navigation**: Developers can quickly find relevant models
- **Logical Grouping**: Related models are grouped together

### 2. Maintainability

- **Isolated Changes**: Modifications to one model type don't affect others
- **Clear Dependencies**: Module imports show exactly what's being used
- **Easier Testing**: Individual model modules can be tested separately

### 3. Extensibility

- **New Model Types**: Easy to add new modules for additional functionality
- **Backward Compatibility**: Existing imports continue to work through `__init__.py`
- **Incremental Enhancement**: Models can be enhanced without affecting the entire system

### 4. Developer Experience

- **Better IDE Support**: Clearer code completion and navigation
- **Faster Loading**: Import only what you need
- **Clear Architecture**: Module structure reflects application architecture

## Package Structure Summary

```text
modules/models/
├── __init__.py          # Public API exports
├── messages.py          # Core message structures
├── events.py           # Streaming event models
└── threads.py          # Thread management models
```

**Total Models**: 20+ dataclasses across 3 focused modules
**Public API**: All models accessible through `modules.models` import
**Type Safety**: Full type hints throughout all modules  
**JSON Support**: Consistent serialization/deserialization across all models
**Content Types**: Support for text, table, and chart content with extensible design

This modular model system provides a robust, type-safe foundation for the Cortex Agents API integration, ensuring extensibility, maintainability, and excellent developer experience.

## Recent Enhancements

### Code Quality and Professional Standards (Latest)

The models package has been enhanced with professional code standards:

**Documentation Improvements**:

- Comprehensive docstrings for all classes and methods with proper Args, Returns, and usage examples
- Professional inline comments replacing debugging-style comments
- Consistent code documentation standards throughout all model files

**Benefits**:

- **Enterprise Ready**: Clean, professional codebase suitable for production deployment
- **Developer Experience**: Improved code readability and comprehensive API documentation
- **Type Safety**: Enhanced type hints and validation throughout all models
- **Maintainability**: Easier code review and future enhancements with clean documentation standards

The models package exemplifies the professional standards maintained throughout the modular architecture.
