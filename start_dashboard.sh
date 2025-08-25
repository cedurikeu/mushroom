#!/bin/bash

echo "🍄 Starting Mushroom Environmental Control Dashboard"
echo "=================================================="

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run the setup first."
    exit 1
fi

# Activate virtual environment and start the application
echo "🚀 Starting application..."
source venv/bin/activate && python3 app.py