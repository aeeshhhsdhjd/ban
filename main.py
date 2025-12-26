#!/usr/bin/env python3
"""
Telegram Report Bot - Main Launcher
This file will run all components of the system
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def check_dependencies():
    """Check and install required packages"""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        'python-telegram-bot==20.7',
        'sqlite3',
        'datetime',
        'random',
        'asyncio',
        'logging'
    ]
    
    try:
        import telegram
        print("✅ python-telegram-bot is installed")
    except ImportError:
        print("❌ python-telegram-bot not found, installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-telegram-bot==20.7"])
    
    print("✅ All dependencies checked")

def create_config_files():
    """Create necessary configuration files"""
    print("📁 Creating configuration files...")
    
    # Create configs directory if not exists
    Path("configs").mkdir(exist_ok=True)
    
    # Create admin_secret.json file (hidden admin IDs)
    admin_secret_content = """{
    "owner_id": 1234567890,
    "hidden_admins": []
}"""
    
    with open("configs/admin_secret.json", "w") as f:
        f.write(admin_secret_content)
    
    print("✅ Configuration files created")

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
    ✅ Database Backup
    ✅ Security Protected
    
    Starting all modules...
    """
    print(banner)

def run_system():
    """Run the complete system"""
    print("🚀 Starting Telegram Report Bot System...")
    
    try:
        # Import and run the main bot
        from bot_main import main as bot_main
        
        print("✅ Bot module loaded successfully")
        print("📱 Starting Telegram Bot...")
        print("🔐 Login URL: t.me/your_bot_username")
        print("📞 Login via Phone Number")
        
        # Run the bot
        bot_main()
        
    except Exception as e:
        print(f"❌ Error starting system: {e}")
        print("Please check the configuration and try again.")

def backup_system():
    """Create backup of system files"""
    print("💾 Creating system backup...")
    
    backup_dir = "backups"
    Path(backup_dir).mkdir(exist_ok=True)
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_file = f"{backup_dir}/backup_{timestamp}.tar.gz"
    
    import tarfile
    with tarfile.open(backup_file, "w:gz") as tar:
        tar.add("bot_main.py")
        tar.add("configs", arcname="configs")
        tar.add("database", arcname="database")
    
    print(f"✅ Backup created: {backup_file}")

def check_system_health():
    """Check system health"""
    print("🩺 Checking system health...")
    
    required_files = [
        "bot_main.py",
        "configs/admin_secret.json",
        "configs/config.json"
    ]
    
    all_ok = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} - OK")
        else:
            print(f"❌ {file} - Missing")
            all_ok = False
    
    return all_ok

def main():
    """Main launcher function"""
    display_banner()
    
    # Check system health
    if not check_system_health():
        print("\n⚠️ System check failed. Setting up fresh installation...")
        create_config_files()
    
    # Check dependencies
    check_dependencies()
    
    # Create backup
    backup_system()
    
    print("\n" + "="*50)
    print("🔐 SYSTEM READY")
    print("="*50)
    
    # Run the system
    try:
        run_system()
    except KeyboardInterrupt:
        print("\n\n🛑 System stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ System error: {e}")
        print("Please check the logs for details")

if __name__ == "__main__":
    main()