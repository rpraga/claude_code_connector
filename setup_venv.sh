#!/bin/bash
# Setup script for Metabase Migrator

set -e

echo "Setting up Metabase Migrator..."

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✓ Setup complete!"
echo ""
echo "To use the migrator:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run commands: ./metabase-migrator test-connection"
echo "  3. Deactivate when done: deactivate"
echo ""
