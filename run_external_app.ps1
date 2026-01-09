# Cortex Agent External Integration Demo - Windows PowerShell Startup Script
# Requires PowerShell 5.0+ (Windows 10/11 default)
# Usage: .\run_external_app.ps1
# Or: powershell -ExecutionPolicy Bypass -File .\run_external_app.ps1

param(
    [int]$Port = 8501
)

Write-Host "⚡ Cortex Agent External Integration Demo" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Function to check if a command exists
function Test-Command {
    param($Command)
    try {
        if (Get-Command $Command -ErrorAction SilentlyContinue) {
            return $true
        }
    }
    catch {
        return $false
    }
    return $false
}

# Check if Python is available
Write-Host "🔍 Checking Python installation..." -ForegroundColor Yellow
if (-not (Test-Command "python")) {
    Write-Host "❌ Python is required but not found" -ForegroundColor Red
    Write-Host "Please install Python 3.11+ from https://python.org and try again" -ForegroundColor Red
    Write-Host "Make sure to check 'Add Python to PATH' during installation" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check Python version
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Found: $pythonVersion" -ForegroundColor Green
    
    # Extract version numbers
    $versionMatch = $pythonVersion -match "Python (\d+)\.(\d+)"
    if ($versionMatch) {
        $majorVersion = [int]$matches[1]
        $minorVersion = [int]$matches[2]
        
        if ($majorVersion -lt 3 -or ($majorVersion -eq 3 -and $minorVersion -lt 11)) {
            Write-Host "⚠️  Warning: Python 3.11+ is recommended. Current version: $pythonVersion" -ForegroundColor Yellow
            $continue = Read-Host "Continue anyway? (y/N)"
            if ($continue -notmatch "^[Yy]") {
                exit 1
            }
        }
    }
}
catch {
    Write-Host "❌ Could not determine Python version" -ForegroundColor Red
    exit 1
}

# Check if pip is available
if (-not (Test-Command "pip")) {
    Write-Host "❌ pip is required but not found" -ForegroundColor Red
    Write-Host "Please install pip and try again (usually included with Python)" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Create or update virtual environment
if (-not (Test-Path "venv")) {
    Write-Host "🐍 Creating virtual environment..." -ForegroundColor Yellow
    try {
        python -m venv venv
        Write-Host "✅ Virtual environment created successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Failed to create virtual environment" -ForegroundColor Red
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}
else {
    Write-Host "🐍 Virtual environment exists - updating..." -ForegroundColor Yellow
    try {
        python -m venv --upgrade venv
        Write-Host "✅ Virtual environment updated successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "⚠️  Warning: Virtual environment upgrade failed, continuing with existing venv" -ForegroundColor Yellow
    }
}

# Activate virtual environment
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Yellow
try {
    if (Test-Path "venv\Scripts\activate.ps1") {
        & .\venv\Scripts\activate.ps1
    }
    elseif (Test-Path "venv\Scripts\Activate.ps1") {
        & .\venv\Scripts\Activate.ps1
    }
    else {
        throw "Virtual environment activation script not found"
    }
}
catch {
    Write-Host "❌ Failed to activate virtual environment" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Install or update dependencies if requirements.txt exists
if (Test-Path "requirements.txt") {
    Write-Host "📦 Installing/updating dependencies..." -ForegroundColor Yellow
    try {
        & .\venv\Scripts\python.exe -m pip install --upgrade pip
        & .\venv\Scripts\python.exe -m pip install -r requirements.txt
        Write-Host "✅ Dependencies installed successfully" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ Failed to install dependencies" -ForegroundColor Red
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}
else {
    Write-Host "⚠️  requirements.txt not found - skipping dependency installation" -ForegroundColor Yellow
}

# Check if configuration exists (matches Python loading priority)
$streamlitSecrets = ".streamlit\secrets.toml"
$snowflakeConfig = "$env:APPDATA\Snowflake\config.json"
$envFile = ".env"

if (-not (Test-Path $streamlitSecrets) -and -not (Test-Path $snowflakeConfig) -and -not (Test-Path $envFile)) {
    Write-Host ""
    Write-Host "⚠️  Configuration not found!" -ForegroundColor Yellow
    Write-Host "Please create one of:" -ForegroundColor Yellow
    Write-Host "  1. .streamlit\secrets.toml file - RECOMMENDED (highest priority)" -ForegroundColor Cyan
    Write-Host "  2. $env:APPDATA\Snowflake\config.json - fallback" -ForegroundColor Cyan
    Write-Host "  3. .env file with environment variables (see config.example) - fallback" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "See README.md for detailed configuration instructions" -ForegroundColor White
    Write-Host ""
    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -notmatch "^[Yy]") {
        exit 1
    }
}
else {
    # Check in actual priority order (matches Python code)
    if (Test-Path $streamlitSecrets) {
        Write-Host "✅ Using Streamlit secrets configuration ($streamlitSecrets) - highest priority" -ForegroundColor Green
    }
    elseif (Test-Path $snowflakeConfig) {
        Write-Host "✅ Using Snowflake JSON configuration ($snowflakeConfig) - fallback" -ForegroundColor Green
    }
    elseif (Test-Path $envFile) {
        Write-Host "✅ Using environment configuration ($envFile) - fallback" -ForegroundColor Green
    }
}

# Set environment variables
$env:STREAMLIT_SERVER_PORT = $Port
if (-not $env:SNOWFLAKE_SSL_VERIFY) {
    $env:SNOWFLAKE_SSL_VERIFY = "true"
}

# Kill any existing Streamlit processes to prevent conflicts
Write-Host "🔄 Checking for existing Streamlit processes..." -ForegroundColor Yellow
try {
    $streamlitProcesses = Get-Process -Name "*streamlit*" -ErrorAction SilentlyContinue
    if ($streamlitProcesses) {
        Write-Host "⚠️  Found existing Streamlit processes - terminating them..." -ForegroundColor Yellow
        $streamlitProcesses | Stop-Process -Force
        Start-Sleep -Seconds 2
        Write-Host "✅ Existing Streamlit processes terminated" -ForegroundColor Green
    }
    else {
        Write-Host "✅ No existing Streamlit processes found" -ForegroundColor Green
    }
}
catch {
    Write-Host "⚠️  Could not check for existing processes, continuing..." -ForegroundColor Yellow
}

# Clear Python cache files to prevent import issues
Write-Host "🧹 Clearing Python cache files..." -ForegroundColor Yellow
try {
    Get-ChildItem -Path . -Include "*.pyc" -Recurse -Force | Remove-Item -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path . -Include "__pycache__" -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "✅ Python cache files cleared" -ForegroundColor Green
}
catch {
    Write-Host "⚠️  Could not clear all cache files, continuing..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🚀 Starting Cortex Agent Demo..." -ForegroundColor Cyan
Write-Host "📍 Access URL: http://localhost:$Port" -ForegroundColor White
Write-Host "🔧 SSL Verification: $env:SNOWFLAKE_SSL_VERIFY" -ForegroundColor White
Write-Host "🛑 Stop with: Ctrl+C" -ForegroundColor White
Write-Host ""

# Check virtual environment Python
try {
    $venvPython = & .\venv\Scripts\python.exe --version 2>&1
    Write-Host "🐍 Using virtual environment Python: $venvPython" -ForegroundColor Green
}
catch {
    Write-Host "⚠️  Could not verify virtual environment Python version" -ForegroundColor Yellow
}

# Start the application using venv's Python explicitly
Write-Host "🚀 Launching Cortex Agent Demo..." -ForegroundColor Cyan

try {
    if (Test-Path ".\venv\Scripts\streamlit.exe") {
        Write-Host "🚀 Launching with venv streamlit executable..." -ForegroundColor Yellow
        & .\venv\Scripts\streamlit.exe run streamlit_app.py --server.port=$Port
    }
    elseif (Test-Path ".\venv\Scripts\python.exe") {
        Write-Host "🚀 Launching with venv python -m streamlit..." -ForegroundColor Yellow
        & .\venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.port=$Port
    }
    else {
        throw "Virtual environment not found or incomplete"
    }
}
catch {
    Write-Host "❌ Failed to start application" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting tips:" -ForegroundColor Yellow
    Write-Host "1. Make sure you're in the correct directory" -ForegroundColor White
    Write-Host "2. Check that streamlit_app.py exists" -ForegroundColor White
    Write-Host "3. Verify virtual environment was created properly" -ForegroundColor White
    Write-Host "4. Try running: python -m streamlit run streamlit_app.py" -ForegroundColor White
    Read-Host "Press Enter to exit"
    exit 1
}
