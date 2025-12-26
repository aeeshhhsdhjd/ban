#!/bin/bash

echo "========================================"
echo "   Telegram Report Bot - Termux"
echo "========================================"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Installing Python..."
    pkg install python -y
fi

# Install requirements
echo "Installing requirements..."
pip install python-telegram-bot==20.7

# Create directories
mkdir -p database configs backups logs

# Create config if not exists
if [ ! -f "configs/config.json" ]; then
    echo "Creating config file..."
    cat > configs/config.json << EOF
{
    "bot_token": "YOUR_BOT_TOKEN_HERE",
    "owner_id": 1234567890,
    "otp_expiry_minutes": 5,
    "max_reports_per_day": 100,
    "max_admins": 50
}
EOF
    echo "⚠️ Please edit configs/config.json with your bot token!"
fi

# Run the bot
echo "Starting bot..."
python3 bot_main.py