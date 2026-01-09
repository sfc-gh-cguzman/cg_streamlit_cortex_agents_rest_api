# Startup Script Documentation (run_external_app.sh)

## Overview

The `run_external_app.sh` script is an intelligent startup and installation script that automates the entire setup process for the Cortex Agent External Integration Demo. It performs comprehensive system checks, dependency installation, configuration validation, and application launch with minimal user intervention.

## Script Architecture

### Execution Flow

```text
Script Start → Environment Checks → Dependency Installation → Process Cleanup → Config Validation → Application Launch
     ↓               ↓                     ↓                     ↓                ↓                    ↓
Check Python → Check pip → Install requirements.txt → Kill existing Streamlit → Find config files → Start Streamlit
```

### Key Features

- **Intelligent Environment Detection**: Automatically detects Python and pip availability
- **Process Cleanup**: Automatically terminates existing Streamlit processes to prevent port conflicts
- **Cross-Platform Compatibility**: Works with both `pip` and `pip3` commands
- **Smart Configuration Discovery**: Finds configuration in multiple locations
- **Graceful Error Handling**: Provides clear error messages and recovery options
- **User-Friendly Output**: Color-coded status messages and progress indicators

## Detailed Script Analysis

### 1. Header and Initialization (Lines 1-7)

```bash
#!/bin/bash

# Cortex Agent External Integration Demo - Startup Script

echo "⚡ Cortex Agent External Integration Demo"
echo "========================================"
```

**Purpose**:

- Sets bash interpreter with proper shebang
- Displays branded startup banner
- Establishes user-friendly interface

**Design Decision**: Uses emoji and visual formatting for better user experience.

### 2. Python Environment Validation (Lines 8-13)

```bash
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    echo "Please install Python 3.11+ and try again"
    exit 1
fi
```

**Purpose**: Validates Python 3 availability before proceeding.

**Key Features**:

- Uses `command -v` for reliable executable detection
- Suppresses output with `&> /dev/null` for clean checking
- Provides specific version requirement (3.11+)
- Exits gracefully with error code 1

**Error Handling**: Clear error message with actionable next steps.

### 3. Package Manager Validation (Lines 15-20)

```bash
if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
    echo "❌ pip is required but not found"
    echo "Please install pip and try again"
    exit 1
fi
```

**Purpose**: Ensures package management capability is available.

**Cross-Platform Support**: Checks for both `pip` and `pip3` to handle different Python installations.

**Logic**: Uses logical AND (`&&`) with NOT (`!`) to ensure at least one pip command exists.

### 4. Dependency Installation (Lines 22-33)

```bash
if [ -f "requirements.txt" ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt || pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        exit 1
    fi
    echo "✅ Dependencies installed successfully"
else
    echo "⚠️  requirements.txt not found - skipping dependency installation"
fi
```

**Purpose**: Automatically installs required Python packages.

**Key Features**:

- **File Existence Check**: Only attempts installation if `requirements.txt` exists
- **Fallback Logic**: Tries `pip` first, then `pip3` if first command fails
- **Error Detection**: Checks exit status (`$?`) of installation command
- **User Feedback**: Progress indicators and status messages

**Error Handling**:

- Graceful handling of missing requirements file
- Installation failure detection with clear error message
- Exit on critical failure

### 5. Configuration Detection System (Lines 35-61)

```bash
SNOWFLAKE_CONFIG="/Library/Application Support/Snowflake/config.json"

if [ ! -f "$SNOWFLAKE_CONFIG" ] && [ ! -f ".env" ] && [ ! -f ".streamlit/secrets.toml" ]; then
    # Configuration missing logic
else
    # Configuration found logic
fi
```

**Purpose**: Implements intelligent configuration discovery across multiple methods.

#### Configuration Priority Order

1. **JSON Configuration**: `/Library/Application Support/Snowflake/config.json`
2. **Environment Variables**: `.env` file
3. **Streamlit Secrets**: `.streamlit/secrets.toml`

#### Missing Configuration Handling

```bash
echo "⚠️  Configuration not found!"
echo "Please create one of:"
echo "  1. /Library/Application Support/Snowflake/config.json - RECOMMENDED"
echo "  2. .env file with environment variables (see config.example)" 
echo "  3. .streamlit/secrets.toml file"
echo ""
echo "See README.md for detailed configuration instructions"
echo ""
read -p "Continue anyway? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi
```

**Features**:

- **Clear Instructions**: Lists all available configuration methods
- **Prioritized Recommendations**: Indicates preferred method
- **Documentation Reference**: Points to README.md for details
- **Interactive Choice**: Allows user to continue without configuration
- **Conservative Default**: Defaults to "No" (exit) unless explicitly confirmed

#### Configuration Found Handling

```bash
if [ -f "$SNOWFLAKE_CONFIG" ]; then
    echo "✅ Using Snowflake JSON configuration ($SNOWFLAKE_CONFIG)"
elif [ -f ".env" ]; then
    echo "✅ Using environment configuration (.env)"
else
    echo "✅ Using Streamlit secrets configuration"
fi
```

**Features**:

- **Status Reporting**: Clearly indicates which configuration method is being used
- **Path Display**: Shows exact file path for JSON configuration
- **Priority Enforcement**: Checks in priority order (JSON → .env → secrets.toml)

### 6. Port Configuration (Lines 63-64)

```bash
PORT=${STREAMLIT_SERVER_PORT:-8501}
```

**Purpose**: Sets Streamlit server port with environment variable support.

**Features**:

- **Environment Variable Support**: Respects `STREAMLIT_SERVER_PORT` if set
- **Sensible Default**: Falls back to standard Streamlit port 8501
- **Bash Parameter Expansion**: Uses `${VAR:-default}` syntax for clean fallback

### 7. Application Launch Preparation (Lines 66-70)

```bash
echo ""
echo "🚀 Starting Cortex Agent Demo..."
echo "📍 Access URL: http://localhost:$PORT"
echo "🛑 Stop with: Ctrl+C"
echo ""
```

**Purpose**: Provides clear launch information and usage instructions.

**User Experience Features**:

- **Visual Separation**: Empty lines for readable output
- **Direct Access Information**: Complete URL with dynamic port
- **Usage Instructions**: Clear shutdown procedure
- **Visual Icons**: Emoji for quick visual scanning

### 8. Multi-Method Application Launch (Lines 72-79)

```bash
if command -v streamlit &> /dev/null; then
    streamlit run streamlit_app.py --server.port=$PORT
elif command -v python3 &> /dev/null; then
    python3 -m streamlit run streamlit_app.py --server.port=$PORT
else
    python -m streamlit run streamlit_app.py --server.port=$PORT
fi
```

**Purpose**: Launches the **modular** Streamlit application using the most appropriate method available.

**Architecture Note**: The script now launches `streamlit_app.py`, which is a minimal 37-line entry point that imports the main application logic from `modules.main.main()`.

**Launch Strategy**:

1. **Direct Streamlit Command**: If `streamlit` is in PATH (preferred)
2. **Python 3 Module**: If Python 3 is available but streamlit not in PATH
3. **Python Module Fallback**: Uses generic `python` command as last resort

**Features**:

- **Command Detection**: Uses `command -v` for reliable executable checking
- **Dynamic Port Configuration**: Passes configured port to Streamlit
- **Modular Architecture Support**: Launches the new modular entry point
- **Module Execution**: Uses `-m streamlit` for cases where streamlit isn't directly executable

**Application Flow**:

```text
run_external_app.sh → streamlit run streamlit_app.py → modules.main.main() → Modular Application
```

## Error Handling Strategy

### 1. Preventive Validation

- **Prerequisites Check**: Validates Python and pip before proceeding
- **File Existence**: Checks for required files before using them
- **Command Availability**: Verifies commands exist before executing

### 2. Graceful Degradation

- **Configuration Missing**: Allows continuation with user confirmation
- **Requirements Missing**: Skips installation but continues
- **Command Fallback**: Multiple launch methods for different environments

### 3. Clear Error Communication

- **Descriptive Messages**: Explains what went wrong and why
- **Actionable Instructions**: Tells users exactly what to do next
- **Visual Indicators**: Uses emoji and formatting for quick error identification

## Usage Scenarios

### 1. First-Time Setup

```bash
chmod +x run_external_app.sh
./run_external_app.sh
```

**Flow**:

- Installs all dependencies
- Prompts for configuration setup
- Launches application

### 2. Regular Usage

```bash
./run_external_app.sh
```

**Flow**:

- Skips dependency installation (already installed)
- Uses existing configuration
- Launches application immediately

### 3. Development Environment

```bash
STREAMLIT_SERVER_PORT=8502 ./run_external_app.sh
```

**Features**:

- Custom port configuration
- Environment variable support
- Quick development iteration

### 4. Production Deployment

```bash
# Setup configuration first
sudo mkdir -p "/Library/Application Support/Snowflake"
sudo cp config.json "/Library/Application Support/Snowflake/"

# Run with production settings
./run_external_app.sh
```

## Integration with Modular Project Architecture

### 1. Configuration System Integration

The script perfectly integrates with the modular three-tier configuration system:

```text
Script Detection → Application Loading → Modular Runtime Usage
       ↓                   ↓                     ↓
   File Checks → modules.config.SnowflakeConfig → API Calls
```

**Priority Alignment**: Script detection order matches application priority order.
**Modular Integration**: Configuration is now handled by `modules.config` package.

### 2. Dependency Management Integration

```text
Script Installation → Modular Runtime Imports → Feature Availability
         ↓                      ↓                      ↓
requirements.txt → modules.* import statements → Full functionality
```

**Validation**: Ensures all required packages are available before launching the modular application.
**Module Support**: All dependencies support the new modular architecture.

### 3. Modular Error Handling Integration

```text
Script Validation → Modular Application Startup → Runtime Operation
        ↓                      ↓                        ↓
   Early Detection → modules.main.main() → Robust Modular Operation
```

**Philosophy**: Catch and resolve issues as early as possible in the pipeline.
**Modular Benefits**: The startup script now launches a more robust, modular application.

### 4. Entry Point Flow Integration

```text
run_external_app.sh → streamlit_app.py → modules.main.main() → Modular Components
         ↓                   ↓                   ↓                    ↓
   Environment Setup → Entry Point → Application Logic → 11 Specialized Modules
```

**Startup Advantages**:

- **Faster Startup**: Modular imports only load needed components
- **Better Error Isolation**: Issues can be traced to specific modules
- **Enhanced Logging**: Structured logging throughout the modular application
- **Improved Debugging**: Module-specific debugging capabilities

## Security Considerations

### 1. File Permission Awareness

- **Configuration Files**: Script doesn't set permissions but documentation recommends `chmod 600`
- **Script Execution**: Requires execute permissions (`chmod +x`)
- **Path Security**: Uses absolute paths for system-wide configuration

### 2. Command Injection Prevention

- **Safe Variable Usage**: Variables are properly quoted and contained
- **Command Validation**: Uses `command -v` instead of executing arbitrary commands
- **Input Sanitization**: User input is validated with regex patterns

### 3. Information Disclosure

- **Path Display**: Shows configuration file paths for transparency
- **Error Messages**: Balanced between helpful and not revealing system details
- **Output Suppression**: Suppresses command output during checks

## Performance Optimizations

### 1. Efficient Checks

- **Command Detection**: Uses built-in `command -v` instead of external tools
- **File Existence**: Simple file tests instead of complex operations
- **Early Exit**: Fails fast on critical errors

### 2. Minimal Dependencies

- **Pure Bash**: No external script dependencies
- **System Commands**: Uses only standard Unix commands
- **Lightweight Operations**: All checks are fast and non-blocking

### 3. Smart Installation

- **Conditional Installation**: Only installs if requirements.txt exists
- **Idempotent Operations**: Safe to run multiple times
- **Error Recovery**: Handles partial installation states

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. Permission Denied

```bash
chmod +x run_external_app.sh
```

**Cause**: Script lacks execute permissions
**Solution**: Add execute permission for user

#### 2. Python Not Found

```bash
# Install Python 3.8+ using your system package manager
# macOS: brew install python3
# Ubuntu: sudo apt-get install python3
# CentOS: sudo yum install python3
```

**Cause**: Python 3 not installed or not in PATH
**Solution**: Install Python 3.8 or later

#### 3. Configuration Not Found

```bash
# Choose one method:
cp .env.example .env
# OR
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# OR create JSON config file
```

**Cause**: No configuration method set up
**Solution**: Create configuration using any supported method

#### 4. Dependency Installation Fails

```bash
# Try manual installation
pip install -r requirements.txt --user
# OR use virtual environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Cause**: System-wide installation restrictions or conflicts
**Solution**: Use user installation or virtual environment

#### 5. Port Already in Use

```bash
STREAMLIT_SERVER_PORT=8502 ./run_external_app.sh
```

**Cause**: Default port 8501 is occupied
**Solution**: Specify alternative port via environment variable

### Debug Mode

Enable detailed output by modifying the script:

```bash
# Add at the top of script for debugging
set -x  # Enable command tracing
set -e  # Exit on any error
```

**Usage**: Helps identify exactly where issues occur during execution.

## Integration with Other Project Components

### 1. README.md Integration

- **Installation Instructions**: README references the script as primary setup method
- **Configuration Guide**: Script validation aligns with README configuration section
- **Troubleshooting**: Both documents provide complementary troubleshooting information

### 2. Requirements.txt Integration

- **Dependency Management**: Script directly uses requirements.txt for installation
- **Version Control**: Ensures exact dependency versions are installed
- **Cross-Platform**: Works with all operating systems supported by requirements

### 3. Configuration Files Integration

- **Multi-Method Support**: Script detects all three configuration methods
- **Priority Order**: Matches application configuration priority
- **Validation**: Ensures at least one configuration method is available

This startup script represents a production-ready deployment solution that handles the complexity of environment setup while maintaining simplicity for end users. It embodies best practices in shell scripting, error handling, and user experience design.
