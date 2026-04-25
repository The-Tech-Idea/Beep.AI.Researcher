#!/bin/bash
# Beep.AI.Researcher - Linux/macOS Launcher
# This script automatically sets up and runs the app with a virtual environment
# Usage: ./run.sh [port]  e.g. ./run.sh 5006

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo ""
echo "============================================================"
echo "  Beep.AI.Researcher - Linux/macOS Launcher"
echo "============================================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in PATH"
    echo "Please install Python 3.10 or higher"
    exit 1
fi

# Detect default python version
PYTHON_CMD="python3"
echo "[INFO] Using system Python: $($PYTHON_CMD --version)"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "[INFO] Creating virtual environment (.venv)..."
    $PYTHON_CMD -m venv .venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        echo "Please ensure python3-venv is installed (e.g., sudo apt install python3-venv)"
        exit 1
    fi
fi

# Activate virtual environment
echo "[INFO] Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "[INFO] Checking dependencies..."
pip install --upgrade pip --quiet

# Install requirements
if [ -f "requirements.txt" ]; then
    echo "[INFO] Installing/Updating required packages..."
    pip install -r requirements.txt --quiet
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to install required packages!"
        echo "Please check your internet connection and requirements.txt file."
        exit 1
    fi
else
    echo "[WARN] requirements.txt not found. Skipping dependency installation."
fi

# Make scripts executable
chmod +x run_hostadmin.py 2>/dev/null
chmod +x run.py 2>/dev/null

# Run the launcher
echo "[INFO] Starting application..."
python run_hostadmin.py "$@"

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Failed to start Beep.AI.Researcher"
    read -p "Press Enter to exit..."
    exit 1
fi
