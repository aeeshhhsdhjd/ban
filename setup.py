#!/usr/bin/env python3
"""
Auto Setup Script for Telegram Report Bot
"""

import os
import sys
import json
import subprocess

def check_python():
    """Check Python version"""
    print("🔍 Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("❌ Python 3.10+ required!")
        sys.exit(1)
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")

def install_requirements():
    """Install required packages"""
    print("📦 Installing requirements...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Requirements installed")
    except:
        print("⚠️ Could not install from requirements.txt")
        print("Installing manually...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-telegram-bot==20.7"])
        print("✅ python-telegram-bot installed")

def create_directories():
    """Create necessary directories"""
    print("📁 Creating directories...")
    directories = [
        "configs",
        "database",
        "backups",
        "logs"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Created: {directory}")

def create_config_files():
    """Create configuration files"""
    print("⚙️ Creating config files...")
    
    # Get user input
    print("\n📝 Please enter configuration:")
    
    bot_token = input("Bot Token from @BotFather: ").strip()
    owner_id = input("Your Telegram ID (from @userinfobot): ").strip()
    
    # Create config.json
    config = {
        "bot_token": bot_token,
        "owner_id": int(owner_id),
        "otp_expiry_minutes": 5,
        "max_reports_per_day": 100,
        "max_admins": 50,
        "database_path": "database/report_bot.db",
        "backup_interval_hours": 24,
        "admin_notification_enabled": True,
        "security_level": "high",
        "auto_backup": True,
        "log_level": "INFO"
    }
    
    with open("configs/config.json", "w") as f:
        json.dump(config, f, indent=4)
    
    # Create admin_secret.json
    admin_secret = {
        "owner_id": int(owner_id),
        "hidden_admins": [],
        "backup_codes": ["ADMIN123", "SECURE456", "BOT789"],
        "secret_key": "CHANGE_THIS_TO_RANDOM_STRING",
        "otp_enabled": True,
        "multi_factor_auth": True
    }
    
    with open("configs/admin_secret.json", "w") as f:
        json.dump(admin_secret, f, indent=4)
    
    print("✅ Config files created")

def update_bot_token():
    """Update bot token in main file"""
    print("🔑 Updating bot token...")
    
    with open("configs/config.json", "r") as f:
        config = json.load(f)
    
    token = config["bot_token"]
    
    # Read bot_main.py
    with open("bot_main.py", "r") as f:
        content = f.read()
    
    # Update token
    content = content.replace('"YOUR_BOT_TOKEN_HERE"', f'"{token}"')
    
    # Write back
    with open("bot_main.py", "w") as f:
        f.write(content)
    
    print("✅ Bot token updated")

def setup_complete():
    """Display setup completion message"""
    print("\n" + "="*50)
    print("🎉 SETUP COMPLETE!")
    print("="*50)
    print("\n📋 Next Steps:")
    print("1. Start the bot: python main.py")
    print("2. Open Telegram and find your bot")
    print("3. Send /start to begin")
    print("4. Send /login to authenticate")
    print("\n🔐 Admin Access:")
    print(f"• Your ID: {owner_id}")
    print("• Send /admin in bot (hidden command)")
    print("\n⚠️ Important:")
    print("• Keep configs/admin_secret.json safe")
    print("• Don't share your bot token")
    print("• Regular backups in backups/ folder")
    print("="*50)

def main():
    """Main setup function"""
    print("\n🤖 Telegram Report Bot - Setup Wizard")
    print("="*50)
    
    check_python()
    create_directories()
    create_config_files()
    install_requirements()
    update_bot_token()
    setup_complete()

if __name__ == "__main__":
    main()