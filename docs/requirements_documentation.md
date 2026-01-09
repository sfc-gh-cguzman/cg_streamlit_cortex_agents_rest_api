# Requirements.txt Documentation

## Overview

The `requirements.txt` file defines all Python dependencies required for the Cortex Agent External Integration Demo. The dependencies are carefully selected and versioned to ensure compatibility, security, and functionality across all features of the application.

## Dependency Categories

The requirements are organized into logical categories based on their primary purpose in the application:

### 1. Core Streamlit Dependencies

#### streamlit>=1.49.0

- **Purpose**: Primary web application framework
- **Why This Version**: Version 1.28.0 introduced critical features for enterprise applications:
  - Improved session state management
  - Enhanced chat interface components
  - Better error handling for production deployments
  - Performance improvements for large applications
- **Usage in App**:
  - Main UI framework (`st.chat_message`, `st.sidebar`, etc.)
  - Session state management
  - Real-time UI updates during streaming
  - Configuration management (`st.set_page_config`)

#### pandas>=1.5.0

- **Purpose**: Data manipulation and analysis library
- **Why This Version**: Version 1.5.0 provides:
  - Improved DataFrame performance
  - Better memory management for large datasets
  - Enhanced data type handling
  - Compatibility with Snowflake data types
- **Usage in App**:
  - SQL query result processing (`bot_retrieve_sql_results`)
  - DataFrame display in Streamlit (`st.dataframe`)
  - Data transformation for charts and tables
  - Integration with Snowpark DataFrames

#### numpy>=1.24.0

- **Purpose**: Numerical computing foundation
- **Why This Version**: Version 1.24.0 offers:
  - Performance improvements
  - Better array handling
  - Enhanced compatibility with pandas
  - Security updates
- **Usage in App**:
  - Underlying array operations for pandas
  - Table data processing in event handlers
  - Support for numerical data from Snowflake queries

### 2. Snowflake Connectivity

#### snowflake-connector-python>=3.5.0

- **Purpose**: Official Snowflake database connector
- **Why This Version**: Version 3.5.0 provides:
  - Enhanced authentication methods (RSA, PAT, OAuth)
  - Improved connection pooling
  - Better error handling and retry mechanisms
  - Support for latest Snowflake features
- **Usage in App**:
  - Direct database connections for utility functions
  - Authentication token generation
  - SQL execution for file operations

#### snowflake-snowpark-python>=1.11.0

- **Purpose**: Snowflake's DataFrame API and session management
- **Why This Version**: Version 1.11.0 includes:
  - Cortex AI function support
  - Enhanced DataFrame operations
  - Better integration with Streamlit
  - Performance optimizations for large datasets
- **Usage in App**:
  - Session management (`Session.builder.configs().create()`)
  - DataFrame operations for query results
  - Integration with Snowflake stages for file operations
  - Root object creation for advanced features

### 3. HTTP Requests and Server-Sent Events

#### requests>=2.31.0,<2.33.0

- **Purpose**: HTTP request library for API interactions
- **Version Range Explanation**:
  - **Lower Bound (>=2.31.0)**: Security fixes and streaming improvements
  - **Upper Bound (<2.33.0)**: Prevents compatibility issues with newer versions
- **Critical Features Used**:
  - Streaming request support (`stream=True`)
  - Custom headers for authentication
  - Timeout handling
  - SSL/TLS verification
- **Usage in App**:
  - Agent API calls (`agent_run_streaming`)
  - Agent discovery requests (`get_available_agents`)
  - File URL generation
  - Authentication validation

#### sseclient-py>=1.8.0

- **Purpose**: Server-Sent Events (SSE) client for real-time streaming
- **Why This Version**: Version 1.8.0 provides:
  - Reliable event parsing
  - Connection retry mechanisms
  - Better error handling
  - Memory efficiency for long-running streams
- **Usage in App**:
  - Real-time streaming event processing (`stream_events_realtime`)
  - Event parsing (`sseclient.SSEClient(response).events()`)
  - Handling disconnections and reconnections
  - Processing multiple event types concurrently

### 4. File Processing

#### pypdfium2>=4.24.0

- **Purpose**: PDF rendering and processing library
- **Why This Version**: Version 4.24.0 offers:
  - High-quality PDF rendering
  - Memory-efficient processing
  - Cross-platform compatibility
  - No external dependencies
- **Usage in App**:
  - PDF file preview (`display_file_with_scrollbar`)
  - Page rendering for citations
  - Cached PDF document handling
  - Multi-page preview with scrolling

### 5. Data Handling and Type Support

#### typing-extensions>=4.5.0

- **Purpose**: Backport of newer typing features
- **Why This Version**: Version 4.5.0 provides:
  - Enhanced type hints for Python < 3.11
  - Generic type support
  - Better IDE integration
  - Forward compatibility
- **Usage in App**:
  - Enhanced type hints throughout models.py
  - Better IDE support for development
  - Type checking for data structures
  - Generic type definitions

### 6. Environment and Configuration

#### python-dotenv>=1.0.0

- **Purpose**: Environment variable management
- **Why This Version**: Version 1.0.0 is the stable release with:
  - Reliable .env file parsing
  - Environment variable precedence handling
  - Cross-platform compatibility
  - No breaking changes from earlier versions
- **Usage in App**:
  - Configuration loading in `SnowflakeConfig`
  - Environment variable fallbacks
  - Development environment setup
  - Production configuration management

### 7. Security and Authentication

#### cryptography>=41.0.0

- **Purpose**: Cryptographic operations and security
- **Why This Version**: Version 41.0.0 provides:
  - Latest security updates
  - RSA key processing improvements
  - Better error handling
  - Performance optimizations
- **Usage in App**:
  - RSA private key loading and parsing
  - JWT token signing for authentication
  - Secure credential handling
  - Private key format validation

#### PyJWT>=2.8.0

- **Purpose**: JSON Web Token implementation
- **Why This Version**: Version 2.8.0 includes:
  - Security vulnerability fixes
  - Algorithm validation improvements
  - Better error messages
  - Performance enhancements
- **Usage in App**:
  - JWT token generation for API authentication
  - RSA256 signature creation
  - Token expiration management
  - Secure authentication flows

### 8. File System Monitoring

#### watchdog>=6.0.0

- **Purpose**: File system event monitoring and watching
- **Why This Version**: Version 6.0.0 provides:
  - Cross-platform file system event handling
  - Improved performance and reliability
  - Better error handling for file operations
  - Support for modern Python versions
- **Usage in App**:
  - Configuration file change detection
  - Log file rotation monitoring
  - Development environment file watching
  - Real-time file system event processing

### 9. Structured Logging and Rich Output

#### structlog>=23.2.0

- **Purpose**: Structured logging library for professional logging
- **Why This Version**: Version 23.2.0 offers:
  - Enhanced structured logging capabilities
  - Better integration with modern Python logging
  - Improved performance for high-volume logging
  - Rich context and metadata support
- **Usage in App**:
  - Professional logging infrastructure (`modules/logging/structured_logging.py`)
  - Structured log message formatting
  - Context preservation across modules
  - Debug and production logging consistency

#### rich>=13.0.0

- **Purpose**: Rich text and beautiful formatting library
- **Why This Version**: Version 13.0.0 provides:
  - Enhanced terminal output formatting
  - Better table and text rendering
  - Improved performance for large outputs
  - Console and logging integration
- **Usage in App**:
  - Enhanced debug interface formatting
  - Rich console output for development
  - Professional log formatting
  - Better error message presentation

## Version Strategy

### Lower Bound Versioning (>=)

- **Security**: Ensures minimum security patch levels
- **Features**: Guarantees required functionality availability
- **Compatibility**: Maintains backward compatibility
- **Stability**: Uses tested, stable releases

### Upper Bound Versioning (<)

- **Used Selectively**: Only for requests library where compatibility issues are known
- **Reason**: Prevents automatic updates that might break functionality
- **Maintenance**: Requires periodic review and updates

### Version Selection Criteria

1. **Security First**: All versions include latest security patches
2. **Feature Requirements**: Versions support all required functionality
3. **Stability**: Preference for stable, well-tested releases
4. **Compatibility**: Inter-dependency compatibility verified
5. **Performance**: Versions with performance improvements preferred

## Dependency Relationships

### Critical Dependency Chains

```text
streamlit → pandas → numpy
    ↓         ↓        ↓
  UI Layer → Data → Arrays
```

```text
snowflake-connector-python → cryptography → PyJWT
         ↓                      ↓           ↓
   Database Access →      RSA Keys →   JWT Tokens
```

```text
requests → sseclient-py
    ↓           ↓
HTTP Calls → SSE Streaming
```

```text
structlog → rich → watchdog
    ↓        ↓        ↓
Logging → Formatting → File Monitoring
```

### Integration Points

1. **Streamlit + Snowflake**: Session management and data display
2. **Requests + SSE**: API calls and real-time streaming
3. **Cryptography + JWT**: Secure authentication
4. **Pandas + Numpy**: Data processing and display
5. **Structlog + Rich**: Professional logging and formatting
6. **Watchdog**: File system monitoring and development support

## Installation Considerations

### Development Environment

```bash
pip install -r requirements.txt
```

### Production Environment

```bash
pip install --no-cache-dir -r requirements.txt
```

### Virtual Environment (Recommended)

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Docker Environment

```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```

## Security Considerations

### Vulnerability Management

- All dependencies are at versions with latest security patches
- Regular dependency scanning recommended
- Update strategy should prioritize security patches

### Authentication Dependencies

- `cryptography`: Handles sensitive RSA key operations
- `PyJWT`: Manages authentication tokens
- Both libraries are at secure, up-to-date versions

### Network Security

- `requests`: Configured for HTTPS-only in application
- `sseclient-py`: Supports secure streaming connections
- Certificate validation enabled by default

## Performance Implications

### Memory Usage

- **pandas/numpy**: Efficient for large datasets from Snowflake
- **pypdfium2**: Memory-efficient PDF processing
- **streamlit**: Optimized session state management

### Network Performance

- **requests**: Connection pooling and keep-alive
- **sseclient-py**: Efficient event streaming
- **snowflake-connector**: Connection reuse

### Processing Performance

- **cryptography**: Optimized RSA operations
- **PyJWT**: Fast token generation
- **pandas**: Vectorized operations

## Compatibility Matrix

**Note**: This application requires **Python 3.11 or higher** as of the latest update.

| Dependency | Python 3.11 | Python 3.12 | Python 3.13 |
|------------|--------------|--------------|--------------|
| streamlit  | ✅ | ✅ | ✅ |
| pandas     | ✅ | ✅ | ✅ |
| snowflake-* | ✅ | ✅ | ✅ |
| requests   | ✅ | ✅ | ✅ |
| cryptography | ✅ | ✅ | ✅ |
| structlog  | ✅ | ✅ | ✅ |
| rich       | ✅ | ✅ | ✅ |
| watchdog   | ✅ | ✅ | ✅ |

## Maintenance and Updates

### Update Schedule

- **Security Updates**: Immediate (within 1-2 days)
- **Minor Updates**: Monthly review
- **Major Updates**: Quarterly review with testing

### Testing Requirements

Before updating dependencies:

1. Authentication flow testing
2. Streaming functionality testing
3. File preview testing
4. UI responsiveness testing
5. Error handling testing

### Breaking Change Management

- Monitor dependency changelogs
- Test in staging environment first
- Have rollback plan ready
- Update documentation accordingly

## Troubleshooting Common Issues

### Installation Issues

#### Cryptography Installation Problems

```bash
# On some systems, may need:
pip install --upgrade pip setuptools wheel
pip install cryptography
```

#### PDF Processing Issues

```bash
# If pypdfium2 fails to install:
pip install --no-cache-dir pypdfium2
```

### Runtime Issues

#### SSL/TLS Certificate Issues

- Ensure requests library can verify SSL certificates
- Check corporate firewall/proxy settings

#### Authentication Problems

- Verify cryptography and PyJWT versions are compatible
- Check RSA key format and permissions

### Performance Issues

#### Memory Usage Issues

- Monitor pandas DataFrame sizes
- Implement data pagination for large results

#### Streaming Performance Issues

- Check network connectivity for SSE streams
- Monitor event processing speed

## Recent Enhancements

### Professional Logging Infrastructure ✅ ADDED

**Latest Update**: Enhanced logging capabilities with structured logging

**New Dependencies Added**:

- **structlog>=23.2.0**: Professional structured logging throughout all modules
- **rich>=13.0.0**: Enhanced formatting and console output for development and debugging
- **watchdog>=6.0.0**: File system monitoring for configuration changes and development workflow

**Benefits**:

- **Professional Standards**: Enterprise-ready logging infrastructure
- **Development Experience**: Rich console output and better debugging tools
- **Production Ready**: Structured logging with context preservation
- **File Monitoring**: Automatic detection of configuration changes

### Python Version Update ✅ UPDATED

**Minimum Requirement**: Updated from Python 3.8+ to **Python 3.11+**

**Rationale**:

- **Modern Features**: Access to latest Python language features and performance improvements
- **Security**: Latest security patches and improvements
- **Dependencies**: Better compatibility with modern dependency versions
- **Performance**: Enhanced performance characteristics of Python 3.11+

This comprehensive dependency management ensures the application runs reliably across different environments while maintaining security, performance, and professional development standards.
