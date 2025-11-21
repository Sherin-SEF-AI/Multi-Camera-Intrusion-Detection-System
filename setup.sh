#!/bin/bash

# Multi-Camera Intrusion Detection System - Setup Script

echo "=========================================="
echo "Multi-Camera Intrusion Detection System"
echo "Setup Script"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    echo "ERROR: Python 3.9 or higher is required"
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p logs database recordings snapshots exports backups app/models docs scripts

# Check for CUDA
echo ""
echo "Checking for CUDA support..."
python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'CUDA version: {torch.version.cuda if torch.cuda.is_available() else \"N/A\"}')"

echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "To run the application:"
echo "  1. Activate the virtual environment: source venv/bin/activate"
echo "  2. Connect your USB webcams"
echo "  3. Run: python main.py"
echo ""
echo "For more information, see README.md"
echo ""
