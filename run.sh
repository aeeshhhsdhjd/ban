#!/bin/bash

echo "================================"
echo "   Telegram Report Bot System"
echo "================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found!"
    echo "Please install Python 3.10+"
    exit 1
fi

# Check if first run
if [ ! -f "configs/config.json" ]; then
    echo "⚙️ First time setup..."
    python3 setup.py
    if [ $? -ne 0 ]; then
        echo "❌ Setup failed!"
        exit 1
    fi
fi

# Run main system
echo "🚀 Starting bot system..."
python3 main.py

if [ $? -ne 0 ]; then
    echo "❌ Bot crashed!"
    echo "Check logs for details."
    exit 1
fi
