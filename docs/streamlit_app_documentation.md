# Cortex Agent Streamlit Application Documentation

## Overview

The **modular** Cortex Agent application demonstrates how to build a production-ready external integration with Snowflake's Cortex Agents API. The application has been completely refactored from a monolithic 2,551-line file into a well-organized modular architecture spanning multiple focused modules.

**Key Architecture Change**: The entry point is now `streamlit_app.py` (43 lines) which imports the main application logic from `modules.main.app.main()`.

## Modular Architecture Overview

The application follows a modular architecture with clear separation of concerns:

```text
┌─────────────────────────────────────────────────────────────┐
│                streamlit_app.py (Entry Point)               │
│                     │                                       │
│                     ▼                                       │
├─────────────────────────────────────────────────────────────┤
│                modules/main/app.py                          │
│              (Main Application Logic)                       │
├─────────────────────────────────────────────────────────────┤
│  modules/ui/     │  modules/config/  │  modules/models/     │
│  UI Components   │  Configuration    │  Data Structures     │
├─────────────────────────────────────────────────────────────┤
│  modules/api/    │  modules/snowflake/ │ modules/threads/   │
│  HTTP & Cortex   │  Client & Agents    │ Conversation Mgmt  │
├─────────────────────────────────────────────────────────────┤
│  modules/files/  │  modules/auth/     │  modules/logging/   │
│  File Handling   │  Authentication    │  Structured Logs    │
├─────────────────────────────────────────────────────────────┤
│                   Cortex Agents API                         │
└─────────────────────────────────────────────────────────────┘
```

## Modular File Structure and Organization

### 1. Entry Point: `streamlit_app.py` (43 lines)

#### Streamlit Page Configuration

```python
st.set_page_config(
    page_title="Cortex Agent - External Integration Demo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)
```

#### Main Function Import and Execution

```python
from modules.main import main

if __name__ == "__main__":
    main()
```

**Architecture Benefits**: Clean separation between configuration and application logic.

### 2. Main Application Logic: `modules/main/app.py`

#### Module Imports Organization

**Data Models:**

```python
from modules.models import (
    TextContentItem,
    MessageContentItem, 
    Message,
    DataAgentRunRequest
)
```

**Configuration:**

```python
# Direct imports from centralized config.py (root level)
from config import (
    API_TIMEOUT_MS,       # 50000 - API request timeout in milliseconds  
    MAX_DATAFRAME_ROWS,   # 1000 - Limit for displayed data
    ENABLE_FILE_PREVIEW,  # Feature flags
    ENABLE_CITATIONS,
    ENABLE_SUGGESTIONS,
    MAX_PDF_PAGES,        # 2 - PDF preview page limit
    ENABLE_DEBUG_MODE,
    PAGE_TITLE,           # UI configuration
    ASSISTANT_AVATAR,
    USER_AVATAR
)

# Module-level constants (imports from config.py)
from modules.config.app_config import (
    THREAD_BASE_ENDPOINT,  # "/api/v2/cortex/threads" - API endpoint
    SNOWFLAKE_SSL_VERIFY   # SSL configuration
)
```

**Core Services:**

```python
from modules.api.cortex_integration import agent_run_streaming, stream_events_realtime
from modules.snowflake.client import ExternalSnowflakeClient
from modules.threads.management import create_thread, get_thread_messages
from modules.ui import config_options, display_agent_status
```

### 3. Centralized Configuration System: `config.py` + `modules/config/`

#### Configuration Architecture

**Purpose**: Two-layer configuration system for clean separation of user settings and internal constants.

**Configuration Layers**:

1. **`config.py` (Root Level)**: User-configurable application behavior settings
2. **`modules/config/` (Module Level)**: Internal configuration management and Snowflake authentication

**Root Configuration (config.py)**:

```python
# All user-configurable settings in one place
from config import (
    # Feature flags
    ENABLE_CITATIONS,
    ENABLE_DEBUG_MODE, 
    ENABLE_FILE_PREVIEW,
    ENABLE_SUGGESTIONS,
    SHOW_FIRST_TOOL_USE_ONLY,
    
    # API and performance
    API_TIMEOUT_MS,
    MAX_DATAFRAME_ROWS,
    MAX_PDF_PAGES,
    
    # UI configuration
    PAGE_TITLE,
    PAGE_ICON,
    LAYOUT,
    SIDEBAR_STATE,
    LOGO_PATH,
    ASSISTANT_AVATAR,
    USER_AVATAR,
    
    # Application identity
    ORIGIN_APPLICATION
)
```

### 4. Modular Authentication System: `modules/config/snowflake_config.py`

#### SnowflakeConfig Class

**Purpose**: Comprehensive authentication configuration management supporting multiple authentication methods, now extracted into its own dedicated module.

**Module Location**: `modules/config/snowflake_config.py`

```python
from modules.config import SnowflakeConfig

class SnowflakeConfig:
    def __init__(self, config_file: str = "/Library/Application Support/Snowflake/config.json")
```

**Authentication Methods Supported**:

1. **RSA Private Key Authentication** (Recommended)
2. **Personal Access Token (PAT)**
3. **Username/Password** (Less secure)

**Configuration Sources** (Priority Order):

1. JSON configuration file
2. Environment variables
3. Streamlit secrets.toml
4. Default values

**Key Methods** (Now in dedicated module):

##### _get_config()

- **Purpose**: Unified configuration retrieval with fallback chain
- **Module**: `modules.config.snowflake_config`
- **Returns**: Configuration value or raises error if required and missing

##### _load_rsa_key_from_file()

- **Purpose**: Securely loads RSA private key from file system
- **Module**: `modules.config.snowflake_config`
- **Security**: Validates file existence and format

##### _validate_config()

- **Purpose**: Comprehensive validation of all authentication requirements
- **Module**: `modules.config.snowflake_config`
- **Integration**: Works with `modules.authentication.token_provider`

**Modular Authentication Flow**:

```text
modules.config → modules.authentication → modules.snowflake → API Ready
      ↓                    ↓                     ↓              ↓
SnowflakeConfig → Token Generation → Client Setup → Bearer Auth
```

### 4. Modular HTTP Request Management: `modules/api/http_client.py`

#### execute_curl_request Function

**Purpose**: Executes HTTP requests using curl subprocess, following the exact pattern from `test_thread_curl.sh`, now in dedicated HTTP client module.

**Module Location**: `modules/api/http_client.py`

```python
from modules.api.http_client import execute_curl_request
```

**Why Curl Instead of Requests**:

- Matches exactly with working test scripts
- Handles authentication edge cases consistently
- Provides verbose debugging output
- Production-tested approach

**Modular Function Signature**:

```python
def execute_curl_request(method: str, url: str, auth_token: str, payload: Dict = None, timeout: int = 30) -> Dict
```

**Key Features** (In dedicated module):

- Subprocess-based curl execution
- Comprehensive error handling
- Debug mode support
- HTTP status code parsing
- Timeout management
- Integration with `modules.logging` for structured logging

**Return Structure**:

```python
{
    "status": int,        # HTTP status code
    "content": str,       # Response body
    "error": str|None,    # Error message if any
    "headers": dict       # Response headers
}
```

**Module Integration**: Used by `modules.api.cortex_integration` and `modules.threads.management`

### 5. Modular Agent Discovery and Management: `modules/snowflake/agents.py`

#### get_available_agents Function

**Purpose**: Discovers all accessible Cortex Agents in the Snowflake account, now in dedicated agent management module.

**Module Location**: `modules/snowflake/agents.py`

```python
from modules.snowflake.agents import get_available_agents, format_sample_questions_for_ui
```

**Discovery Process** (In dedicated module):

1. Query multiple database locations
2. Retrieve agent metadata and specifications
3. Parse agent configurations (tools, models, sample questions)
4. Build user-friendly agent information
5. Integration with `modules.logging` for operation tracking

**Agent Information Structure**:

```python
{
    'name': str,                    # Technical agent name
    'display_name': str,           # User-friendly name
    'database': str,               # Database location
    'schema': str,                 # Schema location
    'owner': str,                  # Agent owner
    'created_on': str,             # Creation date
    'sample_questions': list,      # Predefined questions
    'tools_count': int,            # Number of available tools
    'models': dict,                # Model configurations
    'instructions': dict,          # Agent instructions
    'full_spec': dict             # Complete agent specification
}
```

#### format_sample_questions_for_ui Function

**Purpose**: Converts agent sample questions into UI-friendly format with numbering and keys.

**Module Location**: `modules/snowflake/agents.py`

**UI Enhancement**: Emoji numbering (1️⃣, 2️⃣, etc.) for visual appeal up to 20 questions.

**Integration**: Used by `modules.ui.config_ui` for sidebar display.

### 6. Modular External Snowflake Client: `modules/snowflake/client.py`

#### ExternalSnowflakeClient Class

**Purpose**: Manages Snowflake connections and API interactions for external deployment, now in dedicated client module.

**Module Location**: `modules/snowflake/client.py`

```python
from modules.snowflake.client import ExternalSnowflakeClient

class ExternalSnowflakeClient:
    def __init__(self, config: SnowflakeConfig)
```

**Key Capabilities** (In dedicated module):

- Snowpark session management
- JWT token generation for API authentication via `modules.authentication`
- Multiple authentication method support
- API request orchestration with `modules.api.http_client`
- Integration with `modules.logging` for comprehensive logging

##### get_session() Method

**Purpose**: Creates and manages Snowpark session with proper authentication.

**Module Integration**: Works with `modules.config.SnowflakeConfig`

**Authentication Priority**:

1. RSA Private Key (Most Secure) - via `modules.authentication.token_provider`
2. Personal Access Token
3. Username/Password (Fallback)

**Session Configuration**:

```python
connection_params = {
    "account": self.config.account,
    "user": self.config.user,
    "warehouse": self.config.warehouse,
    "database": "SNOWFLAKE_INTELLIGENCE",  # Default
    "schema": "PUBLIC",                    # Default
}
```

##### JWT Token Generation

**Module Integration**: Now delegates to `modules.authentication.token_provider`

**JWT Payload Structure**:

```python
{
    'iss': f"{account}.{user}",    # Issuer
    'sub': user,                   # Subject
    'iat': now,                    # Issued at
    'exp': now + 3600,            # Expires in 1 hour
}
```

**Security Features**:

- 1-hour token expiration
- RSA256 signing algorithm
- Proper key format validation

##### send_api_request() Method

**Purpose**: Unified API request handling with authentication and error management.

**Module Integration**: Uses `modules.api.http_client.execute_curl_request`

**Features**:

- Automatic token management
- Timeout configuration
- Comprehensive error handling
- Response format standardization
- Structured logging via `modules.logging`

### 7. Modular Thread Management System: `modules/threads/management.py`

#### Thread API Integration

The application implements full thread management following Snowflake's official Cortex Agents Thread REST API specification, now in a dedicated thread management module.

**Module Location**: `modules/threads/management.py`

```python
from modules.threads.management import create_thread, get_thread_messages, delete_thread, get_or_create_thread
```

##### create_thread() Function

**Purpose**: Creates new conversation threads for agent interactions.

**Module Integration**: Uses `modules.api.http_client` and `modules.logging`

**API Call**:

```text
POST /api/v2/cortex/threads
```

**Request Body**:

```json
{
    "origin_application": "CortexAgentDemo"
}
```

**Response Processing** (In dedicated module):

- Extracts `thread_id` from JSON response
- Handles authentication errors with structured logging
- Provides user feedback
- Integration with `modules.models.threads` for type safety

##### get_thread_messages() Function

**Purpose**: Retrieves messages from existing threads with pagination support.

**Module Integration**: Returns `modules.models.threads.ThreadResponse` objects

**API Call**:

```text
GET /api/v2/cortex/threads/{id}?page_size={size}&last_message_id={id}
```

**Features** (In dedicated module):

- Pagination (max 100 messages per page)
- Message ordering (newest first)
- Metadata inclusion
- Error handling with `modules.logging`
- Type-safe response parsing

##### delete_thread() Function

**Purpose**: Permanently deletes threads and all associated messages.

**Module Integration**: Uses `modules.api.http_client` for API calls

**API Call**:

```text
DELETE /api/v2/cortex/threads/{id}
```

**Safety Features**:

- Confirmation feedback
- Error handling with structured logging
- Session state cleanup coordination

##### get_or_create_thread() Function

**Purpose**: Intelligent thread management - gets existing thread or creates new one.

**Module Features**: Handles thread lifecycle automatically

#### Thread State Management

**Session State Variables** (Managed by module):

- `thread_id`: Current active thread identifier
- `thread_messages`: Local message cache for UI display
- `create_new_thread`: Flag for forced thread recreation

**Module Integration**: Works with `modules.config.session_state` for state management

### 8. Modular Citation System: `modules/citations/`

#### Citation Processing Architecture

**Purpose**: Comprehensive citation collection, processing, and display system for external Cortex Agent integration.

**Module Components**:

- **`modules/citations/collector.py`**: Citation data collection and aggregation
- **`modules/citations/processor.py`**: Citation processing and validation
- **`modules/citations/display.py`**: UI components for citation display
- **`modules/citations/utils.py`**: Citation utility functions and helpers

**Key Features**:

- **Automatic Citation Detection**: Real-time citation extraction from agent responses
- **Citation Validation**: Ensures citation integrity and accessibility
- **Interactive Display**: Clickable citations with document previews
- **File Integration**: Works with `modules/files` for document access
- **UI Integration**: Seamless integration with Streamlit components

### 9. Modular Session State Management: `modules/config/session_state.py`

#### ensure_session_state_defaults() Function

**Purpose**: Initializes all required session state variables with safe defaults, now in dedicated configuration module.

**Module Location**: `modules/config/session_state.py`

```python
from modules.config.session_state import ensure_session_state_defaults
```

**Default Values** (In dedicated module):

```python
defaults = {
    "use_chat_history": True,
    "summarize_with_chat_history": True,
    "cortex_search": True,
    "response_instruction": "",
    "api_history": [],
    "show_first_tool_use_only": True,
    "thread_messages": [],
    "suggestions": [],
    "active_suggestion": None,
    "debug_payload_response": False,
    "active_sample_question": None,
    "create_new_thread": False,
    "thread_id": None,
    "selected_agent": None
}
```

**Module Features**:

- **Defensive Programming**: Uses `setdefault()` to avoid overwriting existing values
- **Centralized Management**: All session state defaults in one location
- **Integration**: Works with other modules for consistent state

### 10. Modular User Interface Configuration: `modules/ui/config_ui.py`

#### config_options() Function

**Purpose**: Builds the sidebar configuration interface and handles user interactions, now in dedicated UI module.

**Module Location**: `modules/ui/config_ui.py`

```python
from modules.ui import config_options, display_agent_status, validate_agent_selection
```

**UI Components** (In dedicated module):

##### Application Controls

- **Start Over Button**: Clears conversation and creates new thread
- **Debug Mode Toggle**: Enables/disables comprehensive debugging via `modules.ui.debug_interface`
- **Visual Feedback**: Clear action confirmation

##### Agent Selection

- **Dynamic Agent Discovery**: Real-time loading via `modules.snowflake.agents`
- **Agent Information Display**: Tools count, database location, model info
- **Auto-Selection**: Automatically selects first available agent
- **Agent Details Expander**: Comprehensive agent information

##### Sample Questions Interface

- **Dynamic Question Loading**: From `modules.snowflake.agents.format_sample_questions_for_ui`
- **Visual Enhancement**: Emoji numbering for questions
- **One-Click Usage**: Direct question submission
- **Responsive Design**: Container-width buttons

**Module Integration**:

- Updates `selected_agent` in session state via `modules.config.session_state`
- Handles `active_sample_question` selection
- Manages debug mode flags with `modules.ui.debug_interface`
- Uses `modules.logging` for user interaction tracking

#### Additional UI Functions

##### display_agent_status()

- **Module Location**: `modules/ui/config_ui.py`
- **Purpose**: Shows current agent selection status
- **Integration**: Works with session state management

##### validate_agent_selection()

- **Module Location**: `modules/ui/config_ui.py`
- **Purpose**: Ensures agent is selected before processing
- **Features**: User-friendly error messages

### 11. Modular File Handling System: `modules/files/management.py`

#### File Preview Capabilities

The application supports preview of files stored in Snowflake stages, now in dedicated file management module.

**Module Location**: `modules/files/management.py`

```python
from modules.files.management import download_file_from_stage, get_presigned_url, display_file_with_scrollbar
```

##### download_file_from_stage() Function

- **Module Integration**: Uses `modules.snowflake.client` for stage access
- Downloads files from Snowflake stages to local temporary storage
- Handles path normalization and caching
- Integration with `modules.logging` for file operation tracking

##### get_presigned_url() Function

- **Module Features**: Secure URL generation for file access
- Generates presigned URLs for direct file access
- Supports different stage types (DEMO_STAGE, OUTPUT_STAGE)
- Configurable expiration times
- Error handling with structured logging

##### display_file_with_scrollbar() Function

- **Module Location**: `modules/files/management.py`
- **PDF Preview**: Multi-page rendering with configurable page limits via `modules.config.app_config.MAX_PDF_PAGES`
- **Audio Preview**: Direct audio player integration
- **Image Preview**: Full-resolution image display
- **Security**: Expandable containers with citation tracking
- **Integration**: Works with `modules.citations` for citation management

### 12. Modular Streaming Event Processing: `modules/api/cortex_integration.py`

#### stream_events_realtime() Function

**Purpose**: Processes real-time streaming events from the Cortex Agents API with comprehensive UI updates, now in dedicated API integration module.

**Module Location**: `modules/api/cortex_integration.py`

```python
from modules.api.cortex_integration import agent_run_streaming, stream_events_realtime
```

**Modular Event Processing Architecture**:

```text
modules.api → modules.models → modules.ui → modules.main
     ↓             ↓              ↓            ↓
SSE Stream → Event Parser → UI Components → Live Display
```

**Module Integration**:

- **Event Models**: Uses `modules.models.events` for type-safe event parsing
- **UI Updates**: Integrates with `modules.ui` components
- **Logging**: Uses `modules.logging` for comprehensive event tracking
- **Citations**: Works with `modules.citations` for citation processing

### 13. Modular Main Application Function: `modules/main/app.py`

#### main() Function

**Purpose**: Orchestrates the complete application flow and user interaction, now in dedicated main module.

**Module Location**: `modules/main/app.py`

```python
from modules.main import main

# Entry point flow
streamlit_app.py → modules.main.main() → modules.main.app.main()
```

**Modular Execution Flow**:

1. **UI Initialization**: `modules.ui.config_options()` for sidebar configuration
2. **Conversation Setup**: `modules.threads.management` for thread handling
3. **Agent Status**: `modules.ui.display_agent_status()` for agent information
4. **Message Display**: Uses `modules.models` for type-safe message rendering
5. **User Input**: Processes input through modular pipeline
6. **Debug Interface**: `modules.ui.debug_interface` for comprehensive debugging

**Module Orchestration Benefits**:

- **Separation of Concerns**: Each module handles specific functionality
- **Testability**: Individual modules can be tested in isolation
- **Maintainability**: Changes to one module don't affect others
- **Scalability**: New features can be added as new modules
- **Clear Dependencies**: Explicit imports show module relationships

## Modular Architecture Summary

The refactored application demonstrates **enterprise-grade modular design**:

- **43-line entry point** vs. original 2,551-line monolith
- **12 focused modules** with single responsibilities
- **Clear separation of concerns** across all functionality
- **Comprehensive logging** throughout all modules
- **Type safety** with consistent model usage
- **Easy testing and maintenance** with modular structure
- **Professional code standards** with clean, production-ready documentation

This modular architecture makes the application more **maintainable**, **scalable**, and **enterprise-ready** while preserving all the original functionality and adding enhanced logging, debugging capabilities, and professional code quality standards.

### Supported Event Types

#### response.status

- **Purpose**: Progress indicators during agent processing
- **UI Update**: Dynamic spinner messages
- **User Experience**: Real-time feedback

#### response.text.delta

- **Purpose**: Incremental text streaming
- **UI Update**: Character-by-character text building
- **Features**: HTML support for citations, markdown rendering
- **Content Management**: Request-scoped content containers using `(request_id, content_index)` keys
- **Thread Integrity**: Previous requests remain intact during agent re-evaluation
- **Architecture**: Each request maintains isolated content namespace preventing cross-request interference

#### response.thinking.delta / response.thinking

- **Purpose**: Agent reasoning process display
- **UI Update**: Expandable thinking sections
- **Transparency**: Shows AI decision-making process

#### response.tool_use

- **Purpose**: Tool invocation display
- **UI Components**:
  - Tool name and type display
  - Input parameter visualization
  - SQL query syntax highlighting
  - Reference query display
  - Parameter summaries

#### response.tool_result

- **Purpose**: Tool execution result display
- **Features**:
  - Status-aware display (success/error)
  - SQL query result tables
  - Text explanations
  - Error handling
  - Metadata display

#### response.chart

- **Purpose**: Chart and visualization rendering
- **Technology**: Vega-Lite chart specifications
- **Features**: Responsive, interactive charts

#### response.table

- **Purpose**: Tabular data display
- **Features**: Column metadata, data type handling, responsive tables

#### response.text.annotation

- **Purpose**: Citation and reference handling
- **Features**:
  - Intelligent citation positioning
  - Clickable reference links
  - Document preview integration
  - Context-aware placement

#### error

- **Purpose**: Error handling and recovery
- **Features**: User-friendly error messages, session state cleanup

### Content Scoping Architecture (Thread Integrity)

**Problem Solved**: Previously, content from earlier requests in a thread could be overwritten by subsequent requests, causing parts of responses to disappear from conversation history.

**Solution**: Comprehensive request-scoped content management system that ensures complete conversation history persistence through:

1. **Smart Content Retrieval**: Automatically locates the correct request IDs for charts and tables
2. **Request-Scoped Storage**: Uses composite keys `(request_id, content_index)` for all content types
3. **Conversation History Persistence**: Charts, tables, and text from all previous responses remain visible

#### Key Implementation Details

```python
# Extract request ID for content scoping
current_request_id = response.headers.get('X-Snowflake-Request-Id', 'unknown')

# Use composite keys for all content operations
content_key = (current_request_id, data.content_index)
content_map[content_key] = streamlit_container
buffers[content_key] = accumulated_text
```

#### Thread Structure Protection

```text
Thread (Persistent Conversation)
├── Request A: (req_A, content_0), (req_A, content_1) ← PROTECTED
├── Request B: (req_B, content_0), (req_B, content_1) ← ISOLATED
└── Request C: (req_C, content_0), (req_C, content_1) ← ISOLATED
```

#### Agent Re-evaluation Safety

When agents enter "reevaluating_plan" status, content clearing only affects the current request:

```python
# SAFE: Only clears current request content
for old_content_idx in active_content_indices:
    old_content_key = (current_request_id, old_content_idx)
    content_map[old_content_key].empty()  # Previous requests untouched
```

#### Content Type Coverage

- **Text Streaming**: All `response.text.delta` events use request-scoped keys
- **Table Display**: `response.table` events use `(request_id, content_index)`
- **Chart Rendering**: `response.chart` events use request-scoped containers
- **Thinking Content**: `response.thinking.delta` uses isolated buffers
- **Tool Results**: All tool outputs use request-scoped display containers

#### Benefits

- ✅ **Complete Thread History**: Previous responses remain fully visible
- ✅ **Safe Agent Operations**: Re-evaluation never affects previous requests
- ✅ **Content Persistence**: Tables, charts, citations all preserved
- ✅ **Thread Continuity**: Full conversation context maintained across requests

### Conversation History Persistence

**Advanced Content Retrieval**: The system implements intelligent content detection to ensure charts and tables from previous responses persist in conversation history.

#### Smart Request ID Detection

```python
# Locate the most recent request containing charts
chart_request_id = None
if all_request_charts:
    chart_request_ids = [rid for rid, charts in all_request_charts.items() if charts]
    if chart_request_ids:
        chart_request_id = chart_request_ids[-1]

# Locate the most recent request containing tables  
table_request_id = None
if all_request_tables:
    table_request_ids = [rid for rid, tables in all_request_tables.items() if tables]
    if table_request_ids:
        table_request_id = table_request_ids[-1]
```

#### Content-Specific Retrieval

The system uses different request IDs for different content types:

```python
# Use content-specific request IDs or fallback to current request
effective_chart_request_id = chart_request_id or current_request_id
effective_table_request_id = table_request_id or current_request_id

# Retrieve content using the appropriate request IDs
retrieved_tables = session_manager.get_request_tables(effective_table_request_id)
retrieved_charts = session_manager.get_request_charts(effective_chart_request_id)
```

#### Processed Content Storage

All content is stored in processed message format for conversation history:

```python
# Store complete processed content including charts and tables
assistant_message.store_processed_content(
    processed_text=complete_processed_text,
    tables=tables_data,  # Retrieved using smart detection
    charts=charts_data   # Retrieved using smart detection
)
```

#### Conversation History Display

Charts and tables are rendered from processed content during conversation display:

```python
elif isinstance(item.actual_instance, ChartContentItem):
    # Display chart from stored data
    chart_content = item.actual_instance
    if chart_content.spec:
        st.vega_lite_chart(chart_content.spec, use_container_width=True)

elif isinstance(item.actual_instance, TableContentItem):
    # Display table from stored data
    table_content = item.actual_instance
    if table_content.data and table_content.columns:
        df = pd.DataFrame(table_content.data, columns=table_content.columns)
        st.data_editor(df, use_container_width=True, hide_index=True, disabled=True)
```

### Content Management System

- **Content Buffers**: Per-index text accumulation with intelligent buffer management
- **Content Mapping**: Dynamic UI container management with automatic cleanup
- **Real-time Updates**: Live text streaming without flicker
- **Agent Re-evaluation Handling**: Automatic detection and cleanup of outdated content when agents improve their responses

#### Agent Re-evaluation Logic

The system now includes intelligent handling of agent self-evaluation scenarios:

- **Detection**: Monitors `response.status` events for `"reevaluating_plan"` status
- **Content Tracking**: Tracks all active content indices and their associated UI containers
- **Smart Cleanup**: When agents start streaming improved responses (higher content_index), automatically clears previous content to prevent duplication
- **Seamless UX**: Users see the agent's improved response without duplicate content from earlier iterations

This ensures that when Cortex Agents refine their responses through self-evaluation, users only see the final, improved answer rather than multiple versions of the same content.

### 11. Debug System (Lines 1629-1678, 2122-2250)

#### Comprehensive Debug Capabilities

**Debug Mode Features**:

- **Complete Request/Response Capture**: Full JSON payload logging
- **Event Stream Analysis**: Detailed event type counting
- **Real-time Debug Interface**: Immediate access to debug data
- **File Export**: JSON file generation for analysis
- **Performance Metrics**: Event processing statistics

**Debug Data Structure**:

```python
consolidated_api_response = {
    "response_metadata": {
        "headers": dict,
        "status_code": int,
        "url": str,
        "encoding": str
    },
    "events": [
        {
            "event_number": int,
            "event_type": str,
            "event_id": str,
            "retry": int,
            "data": dict,
            "raw_data": str
        }
    ],
    "event_summary": {
        "total_events": int,
        "event_types": dict
    }
}
```

**Debug Interface**:

- **JSON Viewer**: Syntax-highlighted code display
- **File Export**: Local filesystem save capability
- **Tabbed Interface**: Request and response separation
- **Performance Metrics**: Event count and type distribution

### 12. Message Processing System (Lines 2042-2121)

#### process_new_message_with_thread() Function

**Purpose**: Orchestrates the complete message processing flow with thread context.

**Processing Flow**:

```text
User Input → Thread Validation → Message Creation → API Call → Stream Processing
     ↓             ↓                   ↓              ↓            ↓
  Validate →  Check Thread →    Build Request →   Send API →  Update UI
```

**Key Steps**:

1. **Thread Management**: Get or create thread
2. **Message Creation**: Build user message structure
3. **Session State Update**: Add to thread messages
4. **API Interaction**: Call streaming agent API
5. **Real-time Processing**: Stream events to UI

#### render_thread_message() Function

**Purpose**: Renders historical thread messages with full feature support.

**Rendering Features**:

- **Rich Text**: Markdown and HTML support
- **Data Tables**: DataFrame display
- **Citations**: Clickable reference links
- **Suggestions**: Expandable follow-up questions
- **Error States**: Error message display

### 13. Main Application Flow (Lines 2251-2299)

#### Application Execution Flow

**Purpose**: Orchestrates the complete application flow and user interaction.

**Execution Order**:

1. **UI Initialization**: Sidebar configuration and agent selection
2. **Conversation Initialization**: Thread management and message loading
3. **Status Display**: Active agent information
4. **Thread Display**: Historical message rendering
5. **Debug Interface**: Persistent debug data display
6. **User Input Handling**: New message processing

**User Experience Flow**:

```text
App Start → Agent Selection → Sample Questions → User Input → AI Response
    ↓            ↓                ↓               ↓            ↓
 Load UI → Choose Agent → Pick Question → Type Message → Get Answer
```

**Error Handling**:

- **Agent Validation**: Ensures agent selection before queries
- **Authentication Checking**: Validates credentials
- **Network Error Recovery**: Graceful failure handling
- **State Consistency**: Session state validation

## Integration Patterns

### 1. Model Integration

The application heavily uses the data models from `models.py`:

```python
from models import (
    Message,
    MessageContentItem, 
    TextContentItem,
    DataAgentRunRequest,
    # All event data models...
)
```

**Usage Patterns**:

- **Request Building**: DataAgentRunRequest for API calls
- **Event Parsing**: Event data models for stream processing
- **Type Safety**: Full type checking throughout

### 2. Authentication Flow

```text
Config Load → Validation → Client Creation → Token Generation → API Calls
     ↓            ↓             ↓               ↓              ↓
File/Env → Check Required → Snowflake Client → JWT/PAT → Authenticated Requests
```

### 3. Thread Management

```text
Create Thread → Store ID → Send Messages → Update Thread → Display History
      ↓           ↓           ↓             ↓              ↓
   API Call → Session State → Agent API → Thread Update → UI Render
```

## Advanced Features

### 1. Multi-Agent Support

- **Dynamic Discovery**: Automatic agent detection
- **Agent Switching**: Live agent selection without restart
- **Agent-Specific Features**: Sample questions, tool counts, model info

### 2. Real-Time Streaming

- **Server-Sent Events**: Live streaming support
- **Progressive Display**: Character-by-character text rendering
- **Interactive Elements**: Tools, charts, tables in real-time

### 3. Thread Persistence

- **Conversation History**: Full thread context maintenance
- **Message Ordering**: Chronological message display
- **Thread Lifecycle**: Create, update, delete operations

### 4. Comprehensive Debugging

- **Request/Response Logging**: Complete API interaction capture
- **Event Stream Analysis**: Detailed stream processing metrics
- **Export Capabilities**: JSON file generation for analysis

### 5. File Integration

- **Stage File Preview**: PDF, audio, image preview
- **Presigned URLs**: Secure file access
- **Citation Integration**: Automatic file reference linking

## Security Considerations

### 1. Authentication Security

- **RSA Key Priority**: Most secure authentication method preferred
- **Token Expiration**: 1-hour JWT token lifecycle
- **Credential Validation**: Comprehensive authentication checking

### 2. API Security

- **HTTPS Only**: All API calls over secure connections
- **Bearer Token Auth**: Secure token-based authentication
- **Request Validation**: Input sanitization and validation

### 3. File Access Security

- **Presigned URLs**: Time-limited file access
- **Stage Permissions**: Proper Snowflake stage permissions
- **Content Validation**: File type and size validation

## Performance Optimizations

### 1. Caching Strategy

- **Agent Discovery**: 5-minute TTL cache for agent list
- **File Downloads**: Cached file downloads
- **Session Management**: Efficient session reuse

### 2. Streaming Efficiency

- **Buffer Management**: Efficient text accumulation
- **UI Updates**: Minimal DOM manipulation
- **Event Processing**: Fast JSON parsing

### 3. Resource Management

- **Connection Pooling**: Snowflake connection reuse
- **Memory Management**: Proper cleanup of resources
- **Thread Lifecycle**: Efficient thread creation/deletion

## Error Handling Strategy

### 1. User-Friendly Errors

- **Clear Messages**: Actionable error descriptions
- **Recovery Suggestions**: Specific remediation steps
- **Visual Indicators**: Color-coded error states

### 2. Graceful Degradation

- **Feature Fallbacks**: Graceful feature failure
- **Session Recovery**: Automatic session state restoration
- **Network Resilience**: Retry mechanisms

### 3. Debug Support

- **Comprehensive Logging**: Detailed error information
- **Context Preservation**: Error state capture
- **Recovery Assistance**: Debug information for troubleshooting

## Recent Architecture Enhancements

### Code Quality and Professional Standards ✅ COMPLETED

**Latest Update**: Comprehensive code quality improvements across all 39 Python files

**Improvements Made**:

- **Professional Documentation**: Removed 100+ debugging-style comments with emojis, replaced with production-ready documentation
- **Enhanced Docstrings**: Improved function documentation with proper Args, Returns, and usage examples
- **Consistent Standards**: Standardized comment style and documentation patterns across all modules
- **Enterprise Readiness**: Code now meets professional software development standards
- **Developer Experience**: Cleaner, more maintainable codebase for team development

**Files Enhanced**:

- **Core Application Logic**: `modules/main/app.py` - Professional comment standards
- **API Integration**: `modules/api/cortex_integration.py` - Clean, production-ready documentation
- **Citation System**: Complete `modules/citations/` package - Professional UI and processing comments
- **UI Components**: `modules/ui/` - Clean interface documentation
- **All Supporting Modules**: Consistent professional standards throughout

### Startup Script Enhancement ✅ COMPLETED

**Improvements Made**:

- **Python Version Update**: Minimum requirement updated from 3.8+ to 3.11+
- **Process Cleanup**: Automatic cleanup of existing Streamlit processes to prevent port conflicts
- **Enhanced Reliability**: Improved startup workflow for development and production environments

This Streamlit application represents a production-ready implementation of external Cortex Agents integration with comprehensive features, robust error handling, excellent user experience, and enterprise-grade code quality standards.
