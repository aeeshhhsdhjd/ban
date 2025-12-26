#!/usr/bin/env python3
"""
Telegram Report Bot - Main Launcher
Fixed Version with all error handling
"""

import os
import sys
import json
import time
from pathlib import Path

def check_dependencies():
    """Check and install required packages"""
    print("🔍 Checking dependencies...")
    
    try:
        import telegram
        print("✅ python-telegram-bot is installed")
    except ImportError:
        print("❌ python-telegram-bot not found")
        print("Installing...")
        os.system("pip install python-telegram-bot==20.7")
        print("✅ python-telegram-bot installed")
    
    return True

def create_directories():
    """Create all necessary directories"""
    print("📁 Creating directories...")
    
    directories = [
        "database",
        "configs", 
        "backups",
        "logs"
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✅ Created: {directory}")
        else:
            print(f"✅ Already exists: {directory}")
    
    return True

def create_config_files():
    """Create configuration files if not exist"""
    print("⚙️ Creating configuration files...")
    
    # Create configs directory
    Path("configs").mkdir(exist_ok=True)
    
    # Check if config.json exists
    if not os.path.exists("configs/config.json"):
        default_config = {
            "bot_token": "YOUR_BOT_TOKEN_HERE",
            "owner_id": 1234567890,
            "otp_expiry_minutes": 5,
            "max_reports_per_day": 100,
            "database_path": "database/report_bot.db"
        }
        
        with open("configs/config.json", "w") as f:
            json.dump(default_config, f, indent=4)
        print("✅ Created configs/config.json")
    
    # Check if admin_secret.json exists
    if not os.path.exists("configs/admin_secret.json"):
        default_admin = {
            "owner_id": 1234567890,
            "hidden_admins": [],
            "backup_codes": ["ADMIN123", "SECURE456"]
        }
        
        with open("configs/admin_secret.json", "w") as f:
            json.dump(default_admin, f, indent=4)
        print("✅ Created configs/admin_secret.json")
    
    return True

def backup_system():
    """Create backup of system files"""
    print("💾 Creating system backup...")
    
    # Ensure backup directory exists
    Path("backups").mkdir(exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_file = f"backups/backup_{timestamp}.zip"
    
    # Create list of files to backup
    files_to_backup = []
    
    if os.path.exists("bot_main.py"):
        files_to_backup.append("bot_main.py")
    
    if os.path.exists("configs"):
        files_to_backup.append("configs")
    
    if os.path.exists("database") and os.listdir("database"):
        files_to_backup.append("database")
    
    if not files_to_backup:
        print("⚠️ No files to backup")
        return False
    
    # Create backup using zip
    try:
        import zipfile
        
        with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files_to_backup:
                if os.path.isdir(file_path):
                    for root, dirs, files in os.walk(file_path):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, start=".")
                            zipf.write(full_path, arcname)
                            print(f"  Added: {arcname}")
                else:
                    zipf.write(file_path, os.path.basename(file_path))
                    print(f"  Added: {file_path}")
        
        print(f"✅ Backup created: {backup_file}")
        return True
        
    except Exception as e:
        print(f"⚠️ Backup failed: {e}")
        return False

def check_system_health():
    """Check system health"""
    print("🩺 Checking system health...")
    
    required_files = [
        "bot_main.py",
        "configs/config.json",
        "configs/admin_secret.json"
    ]
    
    all_ok = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} - OK")
        else:
            print(f"❌ {file} - Missing")
            all_ok = False
    
    return all_ok

def display_banner():
    """Display system banner"""
    banner = """
    ╔══════════════════════════════════════════╗
    ║     🤖 TELEGRAM REPORT BOT SYSTEM       ║
    ║            v2.0 - Complete              ║
    ╚══════════════════════════════════════════╝
    
    Features:
    ✅ Phone Number Login System
    ✅ Multi-Admin Support  
    ✅ OTP Verification
    ✅ Hidden Admin Panel
    ✅ Multiple Reports
    ✅ Real-time Reporting
    
    Starting system...
    """
    print(banner)

def run_system():
    """Run the complete system"""
    print("🚀 Starting Telegram Report Bot...")
    
    try:
        # Import the bot module
        import bot_main
        
        print("✅ Bot module loaded successfully")
        print("📱 Starting Telegram Bot...")
        print("="*50)
        
        # Run the bot
        bot_main.main()
        
    except KeyboardInterrupt:
        print("\n\n🛑 Bot stopped by user")
        return True
    except Exception as e:
        print(f"\n❌ Error starting bot: {e}")
        print("\nTrying to fix configuration...")
        
        # Try to fix config
        create_config_files()
        
        # Ask user to update token
        print("\n⚠️ Please update your bot token:")
        print("1. Open 'configs/config.json'")
        print("2. Replace 'YOUR_BOT_TOKEN_HERE' with your bot token")
        print("3. Replace '1234567890' with your Telegram ID")
        print("4. Save the file and run again")
        
        return False

def main():
    """Main launcher function"""
    display_banner()
    
    # Create directories first
    create_directories()
    
    # Check and create configs
    create_config_files()
    
    # Check dependencies
    check_dependencies()
    
    # Check system health
    if not check_system_health():
        print("\n⚠️ Some files are missing")
        print("Creating missing files...")
        create_config_files()
    
    # Create backup
    print("\n" + "="*50)
    backup_system()
    
    print("\n" + "="*50)
    print("🔐 SYSTEM READY")
    print("="*50)
    
    # Run the system
    try:
        run_system()
    except Exception as e:
        print(f"\n❌ System error: {e}")
        print("\nPlease check:")
        print("1. Is bot token correct in configs/config.json?")
        print("2. Is your Telegram ID correct?")
        print("3. Do you have internet connection?")
        
        # Show config help
        print("\n📋 Config file location: configs/config.json")
        print("Example config:")
        print('''
{
    "bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
    "owner_id": 1234567890
}
''')

if __name__ == "__main__":
    main()