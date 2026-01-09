#!/bin/bash

# Cortex Agent External Integration Demo - Startup Script

echo "⚡ Cortex Agent External Integration Demo"
echo "========================================"

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    echo "Please install Python 3.11+ and try again"
    exit 1
fi

# Check if pip is available
if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
    echo "❌ pip is required but not found"
    echo "Please install pip and try again"
    exit 1
fi

# Create or update virtual environment
if [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment"
        exit 1
    fi
    echo "✅ Virtual environment created successfully"
else
    echo "🐍 Virtual environment exists - updating..."
    # Update the virtual environment to ensure it's current
    python3 -m venv --upgrade venv
    if [ $? -ne 0 ]; then
        echo "⚠️  Warning: Virtual environment upgrade failed, continuing with existing venv"
    else
        echo "✅ Virtual environment updated successfully"
    fi
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install or update dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "📦 Installing/updating dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies"
        exit 1
    fi
    echo "✅ Dependencies installed successfully"
else
    echo "⚠️  requirements.txt not found - skipping dependency installation"
fi

# Check if configuration exists (matches Python loading priority)
SNOWFLAKE_CONFIG="/Library/Application Support/Snowflake/config.json"

if [ ! -f ".streamlit/secrets.toml" ] && [ ! -f "$SNOWFLAKE_CONFIG" ] && [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  Configuration not found!"
    echo "Please create one of:"
    echo "  1. .streamlit/secrets.toml file - RECOMMENDED (highest priority)"
    echo "  2. /Library/Application Support/Snowflake/config.json - fallback" 
    echo "  3. .env file with environment variables (see config.example) - fallback"
    echo ""
    echo "See README.md for detailed configuration instructions"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    # Check in actual priority order (matches Python code)
    if [ -f ".streamlit/secrets.toml" ]; then
        echo "✅ Using Streamlit secrets configuration (.streamlit/secrets.toml) - highest priority"
    elif [ -f "$SNOWFLAKE_CONFIG" ]; then
        echo "✅ Using Snowflake JSON configuration ($SNOWFLAKE_CONFIG) - fallback"
    elif [ -f ".env" ]; then
        echo "✅ Using environment configuration (.env) - fallback"
    fi
fi

# Set default port if not specified
PORT=${STREAMLIT_SERVER_PORT:-8501}

# Set SSL verification to true for security (can be overridden by environment)
export SNOWFLAKE_SSL_VERIFY=${SNOWFLAKE_SSL_VERIFY:-true}

# Kill any existing Streamlit processes to prevent conflicts
echo "🔄 Checking for existing Streamlit processes..."
if pgrep -f streamlit > /dev/null; then
    echo "⚠️  Found existing Streamlit processes - terminating them..."
    pkill -f streamlit
    sleep 2
    echo "✅ Existing Streamlit processes terminated"
else
    echo "✅ No existing Streamlit processes found"
fi

# Clear Python cache files to prevent import issues
echo "🧹 Clearing Python cache files..."
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
echo "✅ Python cache files cleared"

echo ""
echo "🚀 Starting Cortex Agent Demo..."
echo "📍 Access URL: http://localhost:$PORT"
echo "🔧 SSL Verification: $SNOWFLAKE_SSL_VERIFY"
echo "🛑 Stop with: Ctrl+C"
echo ""

# Explicitly use virtual environment's Python and Streamlit
echo "🐍 Using virtual environment Python: $(./venv/bin/python --version)"

# Start the application using venv's Python explicitly
if [ -f "./venv/bin/streamlit" ]; then
    echo "🚀 Launching with venv streamlit executable..."
    ./venv/bin/streamlit run streamlit_app.py --server.port=$PORT
elif [ -f "./venv/bin/python" ]; then
    echo "🚀 Launching with venv python -m streamlit..."
    ./venv/bin/python -m streamlit run streamlit_app.py --server.port=$PORT
else
    echo "❌ Virtual environment not found or incomplete"
    exit 1
fi
