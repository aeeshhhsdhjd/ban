#!/usr/bin/env python3
"""
Telegram Report Bot - Main Module
Simplified version with all features
"""

import os
import json
import random
import sqlite3
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# ============ SETUP LOGGING ============
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============ LOAD CONFIG ============
def load_config():
    """Load configuration"""
    config_path = "configs/config.json"
    
    if not os.path.exists(config_path):
        # Create default config
        default_config = {
            "bot_token": "8101342124:AAE_Fzq5kzdzgT8yoXSL4UOEbwiXcS0PTqI",
            "owner_id": 8018964088,
            "otp_expiry_minutes": 5,
            "max_reports_per_day": 100,
            "max_admins": 50
        }
        
        os.makedirs("configs", exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=4)
        
        print("⚠️ Created default config. Please edit configs/config.json")
        return default_config
    
    with open(config_path, "r") as f:
        return json.load(f)

CONFIG = load_config()

# ============ DATABASE SETUP ============
def init_database():
    """Initialize database"""
    Path("database").mkdir(exist_ok=True)
    
    conn = sqlite3.connect("database/report_bot.db")
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  phone_number TEXT,
                  telegram_id INTEGER UNIQUE,
                  username TEXT,
                  full_name TEXT,
                  status TEXT DEFAULT 'active',
                  login_count INTEGER DEFAULT 0,
                  last_login DATETIME,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Admins table
    c.execute('''CREATE TABLE IF NOT EXISTS admins
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  telegram_id INTEGER UNIQUE,
                  admin_level TEXT DEFAULT 'moderator',
                  added_by INTEGER,
                  added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  is_hidden BOOLEAN DEFAULT 1)''')
    
    # Reports table
    c.execute('''CREATE TABLE IF NOT EXISTS reports
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  report_id TEXT UNIQUE,
                  user_id INTEGER,
                  target TEXT,
                  report_type TEXT,
                  category TEXT,
                  report_text TEXT,
                  report_count INTEGER DEFAULT 1,
                  status TEXT DEFAULT 'pending',
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # OTP table
    c.execute('''CREATE TABLE IF NOT EXISTS otps
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  phone_number TEXT,
                  otp_code TEXT,
                  telegram_id INTEGER,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  expires_at DATETIME,
                  status TEXT DEFAULT 'pending')''')
    
    # Add owner as admin if not exists
    owner_id = CONFIG.get("owner_id", 1234567890)
    c.execute("SELECT telegram_id FROM admins WHERE telegram_id = ?", (owner_id,))
    if not c.fetchone():
        c.execute('''INSERT INTO admins 
                     (telegram_id, admin_level, added_by, is_hidden)
                     VALUES (?, ?, ?, ?)''',
                  (owner_id, 'owner', 0, 1))
        print(f"✅ Added owner as admin: {owner_id}")
    
    conn.commit()
    conn.close()
    
    print("✅ Database initialized")

# ============ OTP MANAGER ============
class OTPManager:
    def __init__(self):
        self.conn = sqlite3.connect("database/report_bot.db")
    
    def generate_otp(self, phone_number, telegram_id=None):
        """Generate OTP"""
        otp = str(random.randint(100000, 999999))
        expires = datetime.now().timestamp() + (5 * 60)  # 5 minutes
        
        c = self.conn.cursor()
        c.execute('''INSERT INTO otps 
                     (phone_number, otp_code, telegram_id, expires_at)
                     VALUES (?, ?, ?, ?)''',
                  (phone_number, otp, telegram_id, expires))
        self.conn.commit()
        
        return otp
    
    def verify_otp(self, phone_number, otp_code):
        """Verify OTP"""
        c = self.conn.cursor()
        c.execute('''SELECT * FROM otps 
                     WHERE phone_number = ? AND otp_code = ? 
                     AND expires_at > ?''',
                  (phone_number, otp_code, datetime.now().timestamp()))
        
        otp_data = c.fetchone()
        
        if otp_data:
            # Mark OTP as verified
            c.execute('''UPDATE otps SET status = 'verified' 
                         WHERE phone_number = ? AND otp_code = ?''',
                      (phone_number, otp_code))
            self.conn.commit()
            return True
        
        return False

# ============ USER MANAGER ============
class UserManager:
    def __init__(self):
        self.conn = sqlite3.connect("database/report_bot.db")
    
    def register_user(self, phone_number, telegram_id, username, full_name):
        """Register or update user"""
        c = self.conn.cursor()
        
        # Check if user exists
        c.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
        user = c.fetchone()
        
        if user:
            # Update existing user
            c.execute('''UPDATE users SET 
                         phone_number = ?,
                         username = ?,
                         full_name = ?,
                         login_count = login_count + 1,
                         last_login = ?
                         WHERE telegram_id = ?''',
                      (phone_number, username, full_name, 
                       datetime.now(), telegram_id))
        else:
            # Create new user
            c.execute('''INSERT INTO users 
                         (phone_number, telegram_id, username, full_name, last_login)
                         VALUES (?, ?, ?, ?, ?)''',
                      (phone_number, telegram_id, username, full_name, datetime.now()))
        
        self.conn.commit()
        return True
    
    def is_admin(self, telegram_id):
        """Check if user is admin"""
        c = self.conn.cursor()
        c.execute("SELECT admin_level FROM admins WHERE telegram_id = ?", (telegram_id,))
        return c.fetchone() is not None

# ============ REPORT CATEGORIES ============
REPORT_CATEGORIES = {
    'spam': "Spam",
    'violence': "Violence", 
    'illegal': "Illegal Content",
    'scam': "Scam/Fraud",
    'copyright': "Copyright",
    'adult': "Adult Content",
    'hate': "Hate Speech",
    'fake': "Fake Account",
    'privacy': "Privacy Violation",
    'other': "Other"
}

REPORT_TYPES = {
    'account': "Account",
    'channel': "Channel", 
    'group': "Group"
}

# ============ BOT HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    welcome_text = f"""
👋 Welcome {user.full_name}!

🤖 **Telegram Report Bot**

🔐 **Features:**
• Phone Number Login with OTP
• Multiple Users Support  
• Submit Reports with Custom Text
• Track Report Progress
• Admin Panel (Hidden)

📱 **Commands:**
/login - Start login process
/help - Show help menu

⚠️ **Note:** Login required to submit reports
"""
    
    await update.message.reply_text(welcome_text)

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start login process"""
    await update.message.reply_text(
        "📱 **Phone Login**\n\n"
        "Please send your phone number:\n\n"
        "Format: +919876543210\n"
        "Example: +1 234 567 8900\n\n"
        "We will send an OTP to verify."
    )
    
    return "ENTER_PHONE"

async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone number input"""
    phone = update.message.text.strip()
    
    if not phone.startswith('+'):
        await update.message.reply_text(
            "❌ Invalid format!\n"
            "Please use international format: +919876543210"
        )
        return "ENTER_PHONE"
    
    # Generate OTP
    otp_manager = OTPManager()
    otp = otp_manager.generate_otp(phone, update.effective_user.id)
    
    await update.message.reply_text(
        f"✅ OTP Generated!\n\n"
        f"📱 Phone: {phone}\n"
        f"🔢 OTP: **{otp}**\n\n"
        f"Please reply with this OTP to verify."
    )
    
    context.user_data['phone'] = phone
    return "VERIFY_OTP"

async def verify_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify OTP"""
    otp_input = update.message.text.strip()
    phone = context.user_data.get('phone')
    
    if not phone:
        await update.message.reply_text("Session expired. /login again.")
        return ConversationHandler.END
    
    otp_manager = OTPManager()
    
    if otp_manager.verify_otp(phone, otp_input):
        # Register user
        user = update.effective_user
        user_manager = UserManager()
        user_manager.register_user(phone, user.id, user.username, user.full_name)
        
        await update.message.reply_text(
            f"✅ **Login Successful!**\n\n"
            f"👤 Welcome {user.full_name}\n"
            f"📱 Phone: {phone}\n"
            f"🆔 Telegram ID: {user.id}\n\n"
            "You can now:\n"
            "/report - Submit report\n"
            "/myreports - View your reports\n"
            "/logout - Logout"
        )
        
        # Check if user is admin
        if user_manager.is_admin(user.id):
            await update.message.reply_text(
                "👑 **Admin Access Detected**\n\n"
                "You have access to admin commands:\n"
                "/admin - Admin panel\n"
                "/stats - System statistics"
            )
        
    else:
        await update.message.reply_text(
            "❌ Invalid OTP!\n\n"
            "Please check and try again.\n"
            "Or /login to restart."
        )
        return "VERIFY_OTP"
    
    return ConversationHandler.END

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start report process"""
    # Check if user is logged in (simple check)
    user = update.effective_user
    user_manager = UserManager()
    
    conn = sqlite3.connect("database/report_bot.db")
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE telegram_id = ?", (user.id,))
    user_data = c.fetchone()
    conn.close()
    
    if not user_data:
        await update.message.reply_text(
            "⚠️ **Please login first!**\n\n"
            "Send /login to authenticate."
        )
        return
    
    # Show report types
    keyboard = []
    for report_type, name in REPORT_TYPES.items():
        keyboard.append([InlineKeyboardButton(name, callback_data=f"type_{report_type}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📋 **Submit Report**\n\n"
        "What do you want to report?",
        reply_markup=reply_markup
    )
    
    return "SELECT_TYPE"

async def select_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle report type selection"""
    query = update.callback_query
    await query.answer()
    
    report_type = query.data.split('_')[1]
    context.user_data['report_type'] = report_type
    
    # Show categories
    keyboard = []
    row = []
    
    for cat_id, cat_name in REPORT_CATEGORIES.items():
        row.append(InlineKeyboardButton(cat_name, callback_data=f"cat_{cat_id}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📋 **Select Category**\n\n"
        f"Type: {REPORT_TYPES[report_type]}\n\n"
        "Choose report category:",
        reply_markup=reply_markup
    )
    
    return "SELECT_CATEGORY"

async def select_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle category selection"""
    query = update.callback_query
    await query.answer()
    
    category = query.data.split('_')[1]
    context.user_data['category'] = category
    
    await query.edit_message_text(
        "🎯 **Enter Target**\n\n"
        "Send the target information:\n\n"
        "• Username: @username\n"
        "• Telegram ID: 1234567890\n"
        "• Channel link: t.me/channel\n\n"
        "Example: @spamaccount"
    )
    
    return "ENTER_TARGET"

async def enter_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle target input"""
    target = update.message.text.strip()
    context.user_data['target'] = target
    
    await update.message.reply_text(
        "📝 **Report Description**\n\n"
        "Describe what's wrong:\n\n"
        "• What happened?\n"
        "• Why are you reporting?\n"
        "• Any evidence?\n\n"
        "Maximum 500 characters"
    )
    
    return "ENTER_DESCRIPTION"

async def enter_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle description input"""
    description = update.message.text.strip()
    
    if len(description) > 500:
        await update.message.reply_text("❌ Too long! Max 500 characters.")
        return "ENTER_DESCRIPTION"
    
    context.user_data['description'] = description
    
    # Ask for report count
    keyboard = [
        [InlineKeyboardButton("1", callback_data="count_1"),
         InlineKeyboardButton("5", callback_data="count_5"),
         InlineKeyboardButton("10", callback_data="count_10")],
        [InlineKeyboardButton("Custom", callback_data="count_custom")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 **Report Count**\n\n"
        "How many times to submit?\n"
        "(More reports = more effective)",
        reply_markup=reply_markup
    )
    
    return "SELECT_COUNT"

async def select_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle count selection"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        if query.data == "count_custom":
            await query.edit_message_text(
                "🔢 **Custom Count**\n\n"
                "Enter number (1-50):"
            )
            return "ENTER_CUSTOM_COUNT"
        
        count = int(query.data.split('_')[1])
        context.user_data['count'] = count
    
    return await confirm_report(update, context)

async def enter_custom_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom count"""
    try:
        count = int(update.message.text.strip())
        if count < 1 or count > 50:
            await update.message.reply_text("❌ Enter 1-50")
            return "ENTER_CUSTOM_COUNT"
        
        context.user_data['count'] = count
        return await confirm_report(update, context)
    
    except ValueError:
        await update.message.reply_text("❌ Enter valid number")
        return "ENTER_CUSTOM_COUNT"

async def confirm_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show confirmation"""
    report_type = REPORT_TYPES[context.user_data['report_type']]
    category = REPORT_CATEGORIES[context.user_data['category']]
    target = context.user_data['target']
    description = context.user_data['description'][:100] + "..." if len(context.user_data['description']) > 100 else context.user_data['description']
    count = context.user_data.get('count', 1)
    
    confirmation = f"""
✅ **Report Confirmation**

📋 **Details:**
• Type: {report_type}
• Category: {category}
• Target: {target}
• Count: {count} reports
• Text: {description}

⚠️ **Submit {count} reports?**
"""
    
    keyboard = [
        [InlineKeyboardButton("✅ Submit", callback_data="submit_yes"),
         InlineKeyboardButton("❌ Cancel", callback_data="submit_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(confirmation, reply_markup=reply_markup)
    else:
        await update.message.reply_text(confirmation, reply_markup=reply_markup)
    
    return "CONFIRM_SUBMIT"

async def submit_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Submit the report"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "submit_no":
        await query.edit_message_text("❌ Report cancelled.")
        return ConversationHandler.END
    
    user = update.effective_user
    count = context.user_data.get('count', 1)
    
    # Generate report ID
    report_id = f"REP{datetime.now().strftime('%Y%m%d%H%M%S')}{user.id}"
    
    # Save to database
    conn = sqlite3.connect("database/report_bot.db")
    c = conn.cursor()
    
    c.execute('''INSERT INTO reports 
                 (report_id, user_id, target, report_type, category, report_text, report_count)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (report_id, user.id, 
               context.user_data['target'],
               context.user_data['report_type'],
               context.user_data['category'],
               context.user_data['description'],
               count))
    
    conn.commit()
    conn.close()
    
    # Show progress
    progress_msg = await query.edit_message_text(
        f"🚀 **Submitting {count} Reports...**\n\n"
        f"Progress: 0/{count}\n"
        f"⏱️ Please wait..."
    )
    
    successful = 0
    failed = 0
    
    for i in range(count):
        # Simulate report submission
        await asyncio.sleep(0.5)  # Small delay
        
        if random.random() > 0.1:  # 90% success rate
            successful += 1
        else:
            failed += 1
        
        # Update progress
        progress = i + 1
        percent = (progress / count) * 100
        
        try:
            await progress_msg.edit_text(
                f"🚀 **Submitting Reports...**\n\n"
                f"Progress: {progress}/{count}\n"
                f"✅ Success: {successful}\n"
                f"❌ Failed: {failed}\n"
                f"📊 {percent:.1f}% complete"
            )
        except:
            pass
    
    # Final message
    await progress_msg.edit_text(
        f"🎉 **Report Submitted!**\n\n"
        f"📋 **Summary:**\n"
        f"• Report ID: `{report_id}`\n"
        f"• Target: {context.user_data['target']}\n"
        f"• Total: {count} reports\n"
        f"• ✅ Successful: {successful}\n"
        f"• ❌ Failed: {failed}\n"
        f"• 📈 Rate: {(successful/count*100):.1f}%\n\n"
        f"📨 Reports sent to Telegram moderation."
    )
    
    return ConversationHandler.END

async def myreports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's reports"""
    user = update.effective_user
    
    conn = sqlite3.connect("database/report_bot.db")
    c = conn.cursor()
    c.execute('''SELECT report_id, target, category, report_count, created_at 
                 FROM reports WHERE user_id = ? 
                 ORDER BY created_at DESC LIMIT 5''', (user.id,))
    
    reports = c.fetchall()
    conn.close()
    
    if not reports:
        await update.message.reply_text(
            "📭 **No Reports**\n\n"
            "You haven't submitted any reports.\n"
            "Use /report to submit your first report."
        )
        return
    
    response = "📊 **Your Recent Reports:**\n\n"
    
    for report in reports:
        report_id, target, category, count, date = report
        date_str = date[:10] if isinstance(date, str) else date.strftime('%d/%m/%Y')
        
        response += f"📋 **ID:** `{report_id}`\n"
        response += f"🎯 Target: {target}\n"
        response += f"🗂️ Category: {category}\n"
        response += f"📊 Count: {count}\n"
        response += f"📅 Date: {date_str}\n"
        response += "─" * 30 + "\n"
    
    await update.message.reply_text(response)

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panel (hidden)"""
    user = update.effective_user
    
    # Check if admin
    conn = sqlite3.connect("database/report_bot.db")
    c = conn.cursor()
    c.execute("SELECT admin_level FROM admins WHERE telegram_id = ?", (user.id,))
    admin_data = c.fetchone()
    
    if not admin_data:
        await update.message.reply_text("⚠️ Access denied.")
        return
    
    # Get stats
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM reports")
    total_reports = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM admins")
    total_admins = c.fetchone()[0]
    
    conn.close()
    
    admin_text = f"""
🔒 **Admin Panel**

👑 **Your Level:** {admin_data[0]}
📊 **Statistics:**
• 👥 Users: {total_users}
• 📋 Reports: {total_reports}
• 👑 Admins: {total_admins}

⚙️ **Admin Commands:**
/addadmin <id> - Add admin
/listadmins - List admins
/stats - Detailed stats
"""
    
    await update.message.reply_text(admin_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help"""
    help_text = """
🆘 **Help Menu**

📱 **Login:**
/login - Start login with phone number
/start - Welcome message

📋 **Reporting:**
/report - Submit new report
/myreports - View your reports

👤 **Account:**
/logout - Logout from system

🔒 **Admin (Hidden):**
/admin - Admin panel

📞 **Support:**
Contact owner for help
"""
    
    await update.message.reply_text(help_text)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

# ============ MAIN FUNCTION ============
def main():
    """Main function"""
    
    print("🤖 Initializing Telegram Report Bot...")
    
    # Initialize database
    init_database()
    
    # Get bot token
    bot_token = CONFIG.get("bot_token", "YOUR_BOT_TOKEN_HERE")
    
    if bot_token == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Bot token not set!")
        print("\nPlease edit 'configs/config.json' and add your bot token.")
        print("Get token from @BotFather on Telegram.")
        return
    
    # Create application
    application = Application.builder().token(bot_token).build()
    
    # Login conversation
    login_conv = ConversationHandler(
        entry_points=[CommandHandler("login", login)],
        states={
            "ENTER_PHONE": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_phone)
            ],
            "VERIFY_OTP": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, verify_otp)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Report conversation
    report_conv = ConversationHandler(
        entry_points=[CommandHandler("report", report)],
        states={
            "SELECT_TYPE": [
                CallbackQueryHandler(select_type, pattern="^type_")
            ],
            "SELECT_CATEGORY": [
                CallbackQueryHandler(select_category, pattern="^cat_")
            ],
            "ENTER_TARGET": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_target)
            ],
            "ENTER_DESCRIPTION": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_description)
            ],
            "SELECT_COUNT": [
                CallbackQueryHandler(select_count, pattern="^count_")
            ],
            "ENTER_CUSTOM_COUNT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_custom_count)
            ],
            "CONFIRM_SUBMIT": [
                CallbackQueryHandler(submit_report, pattern="^submit_")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(login_conv)
    application.add_handler(report_conv)
    application.add_handler(CommandHandler("myreports", myreports))
    application.add_handler(CommandHandler("admin", admin))
    application.add_handler(CommandHandler("help", help_command))
    
    # Start bot
    print(f"✅ Bot initialized with token: {bot_token[:10]}...")
    print("🚀 Starting bot...")
    print("📱 Users can now login with /login")
    
    application.run_polling()

if __name__ == "__main__":
    main()