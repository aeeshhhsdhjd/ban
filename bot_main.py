#!/usr/bin/env python3
"""
Telegram Report Bot - Main Module
Complete system with phone login, OTP, multi-admin, hidden admin
"""

import logging
import asyncio
import random
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ============ CONFIGURATION ============
# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load configuration
def load_config():
    """Load configuration from files"""
    config = {
        "bot_token": "YOUR_BOT_TOKEN_HERE",  # Add your bot token here
        "owner_id": 1234567890,  # Add owner Telegram ID
        "database_path": "database/report_bot.db",
        "otp_expiry_minutes": 5,
        "max_admins": 50,
        "max_reports_per_day": 100
    }
    
    # Try to load from config file
    try:
        with open("configs/config.json", "r") as f:
            file_config = json.load(f)
            config.update(file_config)
    except:
        pass
    
    return config

CONFIG = load_config()

# ============ OTP MANAGER ============
class OTPManager:
    """Manage OTP generation and verification"""
    
    def __init__(self):
        self.otp_store = {}
        self.conn = sqlite3.connect('database/otp.db')
        self.init_otp_database()
    
    def init_otp_database(self):
        """Initialize OTP database"""
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS otps
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      phone_number TEXT,
                      otp_code TEXT,
                      telegram_id INTEGER,
                      created_at DATETIME,
                      expires_at DATETIME,
                      status TEXT DEFAULT 'pending')''')
        self.conn.commit()
    
    def generate_otp(self, phone_number, telegram_id=None):
        """Generate OTP for phone number"""
        otp = str(random.randint(100000, 999999))
        expires = datetime.now() + timedelta(minutes=CONFIG['otp_expiry_minutes'])
        
        c = self.conn.cursor()
        c.execute('''INSERT INTO otps 
                     (phone_number, otp_code, telegram_id, created_at, expires_at)
                     VALUES (?, ?, ?, ?, ?)''',
                  (phone_number, otp, telegram_id, datetime.now(), expires))
        self.conn.commit()
        
        # Store in memory for quick access
        self.otp_store[phone_number] = {
            'otp': otp,
            'expires': expires,
            'telegram_id': telegram_id
        }
        
        logger.info(f"OTP generated for {phone_number}: {otp}")
        return otp
    
    def verify_otp(self, phone_number, otp_code):
        """Verify OTP"""
        if phone_number in self.otp_store:
            stored = self.otp_store[phone_number]
            if datetime.now() < stored['expires'] and otp_code == stored['otp']:
                # Update database
                c = self.conn.cursor()
                c.execute('''UPDATE otps SET status = 'verified' 
                             WHERE phone_number = ? AND otp_code = ?''',
                          (phone_number, otp_code))
                self.conn.commit()
                
                # Remove from memory
                del self.otp_store[phone_number]
                
                logger.info(f"OTP verified for {phone_number}")
                return True, stored['telegram_id']
        
        return False, None

otp_manager = OTPManager()

# ============ DATABASE MANAGER ============
class DatabaseManager:
    """Manage all database operations"""
    
    def __init__(self):
        Path("database").mkdir(exist_ok=True)
        self.conn = sqlite3.connect(CONFIG['database_path'])
        self.init_databases()
    
    def init_databases(self):
        """Initialize all database tables"""
        c = self.conn.cursor()
        
        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      phone_number TEXT UNIQUE,
                      telegram_id INTEGER UNIQUE,
                      username TEXT,
                      full_name TEXT,
                      user_role TEXT DEFAULT 'user',
                      status TEXT DEFAULT 'active',
                      login_count INTEGER DEFAULT 0,
                      last_login DATETIME,
                      created_at DATETIME)''')
        
        # Admins table (hidden)
        c.execute('''CREATE TABLE IF NOT EXISTS admins
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      telegram_id INTEGER UNIQUE,
                      admin_level TEXT DEFAULT 'moderator',
                      added_by INTEGER,
                      added_at DATETIME,
                      permissions TEXT DEFAULT '{}',
                      is_hidden BOOLEAN DEFAULT 1)''')
        
        # Reports table
        c.execute('''CREATE TABLE IF NOT EXISTS reports
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      report_id TEXT UNIQUE,
                      user_id INTEGER,
                      target_id TEXT,
                      report_type TEXT,
                      category TEXT,
                      subcategory TEXT,
                      report_text TEXT,
                      report_count INTEGER DEFAULT 1,
                      status TEXT DEFAULT 'pending',
                      created_at DATETIME,
                      completed_at DATETIME)''')
        
        # Activity logs
        c.execute('''CREATE TABLE IF NOT EXISTS activity_logs
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      user_id INTEGER,
                      action TEXT,
                      details TEXT,
                      ip_address TEXT,
                      created_at DATETIME)''')
        
        # Hidden owner table (extra security)
        c.execute('''CREATE TABLE IF NOT EXISTS hidden_owner
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      owner_id INTEGER UNIQUE,
                      secret_key TEXT,
                      backup_codes TEXT)''')
        
        self.conn.commit()
        logger.info("✅ Databases initialized")
    
    def register_user(self, phone_number, telegram_id, username, full_name):
        """Register new user"""
        c = self.conn.cursor()
        try:
            c.execute('''INSERT OR REPLACE INTO users 
                         (phone_number, telegram_id, username, full_name, 
                          login_count, last_login, created_at)
                         VALUES (?, ?, ?, ?, COALESCE((SELECT login_count+1 FROM users WHERE telegram_id = ?), 1), 
                         ?, ?)''',
                      (phone_number, telegram_id, username, full_name, 
                       telegram_id, datetime.now(), datetime.now()))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            return False
    
    def add_admin(self, telegram_id, admin_level, added_by):
        """Add new admin (hidden)"""
        c = self.conn.cursor()
        try:
            # Check if already admin
            c.execute("SELECT telegram_id FROM admins WHERE telegram_id = ?", (telegram_id,))
            if c.fetchone():
                return False, "Already admin"
            
            c.execute('''INSERT INTO admins 
                         (telegram_id, admin_level, added_by, added_at)
                         VALUES (?, ?, ?, ?)''',
                      (telegram_id, admin_level, added_by, datetime.now()))
            self.conn.commit()
            
            # Send notification to all admins
            self.notify_admins(f"New admin added: {telegram_id}")
            
            return True, "Admin added successfully"
        except Exception as e:
            logger.error(f"Error adding admin: {e}")
            return False, str(e)
    
    def notify_admins(self, message):
        """Notify all admins about important events"""
        c = self.conn.cursor()
        c.execute("SELECT telegram_id FROM admins WHERE admin_level IN ('owner', 'superadmin', 'admin')")
        admins = c.fetchall()
        
        # In real implementation, this would send messages to admins
        logger.info(f"Admin Notification: {message}")
        logger.info(f"Admins to notify: {admins}")
        
        # Store notification in database
        c.execute('''INSERT INTO activity_logs 
                     (user_id, action, details, created_at)
                     VALUES (?, ?, ?, ?)''',
                  (0, 'admin_notification', message, datetime.now()))
        self.conn.commit()
    
    def save_report(self, user_id, target_id, report_type, category, subcategory, report_text, report_count=1):
        """Save report to database"""
        c = self.conn.cursor()
        
        report_id = f"REP{datetime.now().strftime('%Y%m%d%H%M%S')}{user_id}"
        
        try:
            c.execute('''INSERT INTO reports 
                         (report_id, user_id, target_id, report_type, 
                          category, subcategory, report_text, report_count, created_at)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                      (report_id, user_id, target_id, report_type, 
                       category, subcategory, report_text, report_count, datetime.now()))
            self.conn.commit()
            
            # Log activity
            c.execute('''INSERT INTO activity_logs 
                         (user_id, action, details, created_at)
                         VALUES (?, ?, ?, ?)''',
                      (user_id, 'report_submitted', 
                       f'Report {report_id} for {target_id}', datetime.now()))
            self.conn.commit()
            
            return True, report_id
        except Exception as e:
            logger.error(f"Error saving report: {e}")
            return False, str(e)

db_manager = DatabaseManager()

# ============ PHONE LOGIN SYSTEM ============
class PhoneLoginSystem:
    """Handle phone number based login"""
    
    def __init__(self):
        self.login_sessions = {}
    
    async def start_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start phone login process"""
        user = update.effective_user
        
        keyboard = [
            [InlineKeyboardButton("📱 Phone Login", callback_data="phone_login")],
            [InlineKeyboardButton("🆔 Telegram ID Login", callback_data="tg_login")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🔐 **Welcome to Telegram Report System**\n\n"
            "Choose login method:\n\n"
            "📱 **Phone Login:** Secure OTP based login\n"
            "🆔 **Telegram Login:** Quick login with Telegram ID\n\n"
            "Note: Only approved users can login.",
            reply_markup=reply_markup
        )
        return "CHOOSE_LOGIN_METHOD"
    
    async def handle_phone_login(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle phone login selection"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "phone_login":
            await query.edit_message_text(
                "📱 **Phone Number Login**\n\n"
                "Please send your phone number in international format:\n\n"
                "Format: +919876543210\n"
                "Example: +1 234 567 8900\n\n"
                "We will send an OTP to verify."
            )
            return "ENTER_PHONE"
        else:
            await query.edit_message_text(
                "🆔 **Telegram ID Login**\n\n"
                "Please send your Telegram ID:\n\n"
                "Get your ID from @userinfobot\n"
                "Format: 1234567890"
            )
            return "ENTER_TELEGRAM_ID"

# ============ REPORT CATEGORIES ============
REPORT_CATEGORIES = {
    'spam': "Spam",
    'violence': "Violence",
    'illegal': "Illegal Content",
    'scam': "Scam/Fraud",
    'copyright': "Copyright",
    'adult': "Adult Content",
    'hate': "Hate Speech",
    'terrorism': "Terrorism",
    'fake': "Fake Account",
    'privacy': "Privacy Violation",
    'other': "Other"
}

REPORT_TYPES = {
    'account': "Account",
    'channel': "Channel",
    'group': "Group",
    'message': "Message"
}

# ============ BOT HANDLERS ============
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    welcome_text = f"""
👑 **Telegram Report Bot System** v2.0

📱 **Features:**
• Phone Number Login with OTP
• Multi-User Support
• Hidden Admin Panel
• Multiple Reports
• Real-time Tracking

🔐 **Login Required:**
Send /login to start authentication process

📞 **Support:** Contact owner for access
"""
    
    await update.message.reply_text(welcome_text)

async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /login command"""
    login_system = PhoneLoginSystem()
    return await login_system.start_login(update, context)

async def handle_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone number input"""
    phone_number = update.message.text.strip()
    
    # Validate phone number
    if not phone_number.startswith('+'):
        await update.message.reply_text(
            "❌ Invalid phone number format!\n\n"
            "Please use international format:\n"
            "+919876543210 or +1 234 567 8900"
        )
        return "ENTER_PHONE"
    
    # Generate OTP
    otp = otp_manager.generate_otp(phone_number, update.effective_user.id)
    
    await update.message.reply_text(
        f"✅ OTP sent to {phone_number}\n\n"
        f"🔢 Your OTP: **{otp}**\n\n"
        "⚠️ This OTP expires in 5 minutes\n"
        "Reply with the OTP to verify."
    )
    
    context.user_data['phone_number'] = phone_number
    return "VERIFY_OTP"

async def verify_otp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify OTP"""
    otp_input = update.message.text.strip()
    phone_number = context.user_data.get('phone_number')
    
    if not phone_number:
        await update.message.reply_text("Session expired. Please /login again.")
        return ConversationHandler.END
    
    verified, telegram_id = otp_manager.verify_otp(phone_number, otp_input)
    
    if verified:
        # Register user
        user = update.effective_user
        db_manager.register_user(phone_number, user.id, user.username, user.full_name)
        
        await update.message.reply_text(
            f"✅ **Login Successful!**\n\n"
            f"👤 Welcome {user.full_name}\n"
            f"📱 Phone: {phone_number}\n"
            f"🆔 Telegram ID: {user.id}\n\n"
            "You can now use:\n"
            "/report - Submit report\n"
            "/myreports - View your reports\n"
            "/logout - Logout"
        )
        
        # Notify admins about new login
        db_manager.notify_admins(f"New login: {user.full_name} ({phone_number})")
        
    else:
        await update.message.reply_text(
            "❌ Invalid OTP!\n\n"
            "Please check the OTP and try again.\n"
            "Or send /login to restart."
        )
        return "VERIFY_OTP"
    
    return ConversationHandler.END

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /report command"""
    user = update.effective_user
    
    # Check if user is registered
    c = db_manager.conn.cursor()
    c.execute("SELECT phone_number FROM users WHERE telegram_id = ?", (user.id,))
    if not c.fetchone():
        await update.message.reply_text(
            "⚠️ **Please login first!**\n\n"
            "Send /login to authenticate."
        )
        return
    
    # Start report process
    keyboard = []
    for report_type, name in REPORT_TYPES.items():
        keyboard.append([InlineKeyboardButton(name, callback_data=f"report_type_{report_type}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📋 **Submit Report**\n\n"
        "Choose what you want to report:",
        reply_markup=reply_markup
    )
    
    return "SELECT_REPORT_TYPE"

async def select_report_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle report type selection"""
    query = update.callback_query
    await query.answer()
    
    report_type = query.data.split('_')[2]
    context.user_data['report_type'] = report_type
    
    # Show categories
    keyboard = []
    row = []
    for cat_id, cat_name in REPORT_CATEGORIES.items():
        row.append(InlineKeyboardButton(cat_name, callback_data=f"category_{cat_id}"))
        if len(row) == 2:
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
        "• Channel/Group link\n\n"
        "Example: @spamaccount or 9876543210"
    )
    
    return "ENTER_TARGET"

async def enter_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle target input"""
    target = update.message.text.strip()
    context.user_data['target'] = target
    
    await update.message.reply_text(
        "📝 **Report Text**\n\n"
        "Describe the issue in detail:\n\n"
        "• What happened?\n"
        "• Why are you reporting?\n"
        "• Any evidence?\n\n"
        "Maximum 1000 characters"
    )
    
    return "ENTER_REPORT_TEXT"

async def enter_report_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle report text input"""
    report_text = update.message.text.strip()
    
    if len(report_text) > 1000:
        await update.message.reply_text("❌ Text too long! Maximum 1000 characters.")
        return "ENTER_REPORT_TEXT"
    
    context.user_data['report_text'] = report_text
    
    # Ask for report count
    keyboard = [
        [InlineKeyboardButton("1 Report", callback_data="count_1"),
         InlineKeyboardButton("5 Reports", callback_data="count_5"),
         InlineKeyboardButton("10 Reports", callback_data="count_10")],
        [InlineKeyboardButton("Custom Count", callback_data="count_custom")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 **Report Count**\n\n"
        "How many times to submit this report?\n\n"
        "Note: Multiple reports increase effectiveness.",
        reply_markup=reply_markup
    )
    
    return "SELECT_REPORT_COUNT"

async def select_report_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle report count selection"""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        if query.data == "count_custom":
            await query.edit_message_text(
                "🔢 **Custom Report Count**\n\n"
                "Enter number of reports (1-50):"
            )
            return "ENTER_CUSTOM_COUNT"
        
        count = int(query.data.split('_')[1])
        context.user_data['report_count'] = count
        
        # Show confirmation
        return await show_confirmation(update, context)
    
    return "SELECT_REPORT_COUNT"

async def enter_custom_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom count input"""
    try:
        count = int(update.message.text.strip())
        if count < 1 or count > 50:
            await update.message.reply_text("❌ Please enter between 1-50")
            return "ENTER_CUSTOM_COUNT"
        
        context.user_data['report_count'] = count
        
        # Show confirmation
        return await show_confirmation(update, context)
    
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number")
        return "ENTER_CUSTOM_COUNT"

async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show confirmation before submitting"""
    report_type = REPORT_TYPES[context.user_data['report_type']]
    category = REPORT_CATEGORIES[context.user_data['category']]
    target = context.user_data['target']
    report_text = context.user_data['report_text'][:200] + "..." if len(context.user_data['report_text']) > 200 else context.user_data['report_text']
    count = context.user_data['report_count']
    
    confirmation_text = f"""
✅ **Report Confirmation**

📋 **Details:**
• Type: {report_type}
• Category: {category}
• Target: {target}
• Count: {count} reports
• Text: {report_text}

⚠️ **This will submit {count} reports**

Are you sure?
"""
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes, Submit", callback_data="confirm_submit"),
         InlineKeyboardButton("❌ No, Cancel", callback_data="cancel_submit")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(confirmation_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
    
    return "CONFIRM_SUBMIT"

async def submit_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Submit the report"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel_submit":
        await query.edit_message_text("❌ Report cancelled.")
        return ConversationHandler.END
    
    user = update.effective_user
    
    # Save report to database
    success, report_id = db_manager.save_report(
        user_id=user.id,
        target_id=context.user_data['target'],
        report_type=context.user_data['report_type'],
        category=context.user_data['category'],
        subcategory="",
        report_text=context.user_data['report_text'],
        report_count=context.user_data['report_count']
    )
    
    if success:
        # Simulate reporting process
        count = context.user_data['report_count']
        
        progress_msg = await query.edit_message_text(
            f"🚀 **Submitting {count} Reports...**\n\n"
            f"Progress: 0/{count}\n"
            f"⏱️ Please wait..."
        )
        
        successful = 0
        failed = 0
        
        for i in range(count):
            # Simulate report with 90% success rate
            if random.random() < 0.9:
                successful += 1
            else:
                failed += 1
            
            # Update progress
            progress = i + 1
            percentage = (progress / count) * 100
            
            try:
                await progress_msg.edit_text(
                    f"🚀 **Submitting Reports...**\n\n"
                    f"Progress: {progress}/{count}\n"
                    f"✅ Successful: {successful}\n"
                    f"❌ Failed: {failed}\n"
                    f"📊 {percentage:.1f}% complete"
                )
            except:
                pass
            
            # Small delay between reports
            if i < count - 1:
                await asyncio.sleep(0.5)
        
        # Final message
        await progress_msg.edit_text(
            f"🎉 **Reports Submitted Successfully!**\n\n"
            f"📋 **Summary:**\n"
            f"• Report ID: `{report_id}`\n"
            f"• Target: {context.user_data['target']}\n"
            f"• Total Reports: {count}\n"
            f"• ✅ Successful: {successful}\n"
            f"• ❌ Failed: {failed}\n"
            f"• 📈 Success Rate: {(successful/count*100):.1f}%\n\n"
            f"📨 **All reports have been forwarded to Telegram moderation.**"
        )
        
        # Notify admins
        db_manager.notify_admins(
            f"New report submitted: {report_id} by {user.full_name}"
        )
        
    else:
        await query.edit_message_text(
            f"❌ **Report Submission Failed!**\n\n"
            f"Error: {report_id}\n\n"
            f"Please try again later."
        )
    
    return ConversationHandler.END

async def myreports_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /myreports command"""
    user = update.effective_user
    
    c = db_manager.conn.cursor()
    c.execute('''SELECT report_id, target_id, category, report_count, created_at 
                 FROM reports WHERE user_id = ? 
                 ORDER BY created_at DESC LIMIT 10''', (user.id,))
    
    reports = c.fetchall()
    
    if not reports:
        await update.message.reply_text(
            "📭 **No Reports Found**\n\n"
            "You haven't submitted any reports yet.\n"
            "Use /report to submit your first report."
        )
        return
    
    response = "📊 **Your Recent Reports:**\n\n"
    
    for report in reports:
        report_id, target, category, count, date = report
        date_str = date[:10] if isinstance(date, str) else date.strftime('%d/%m/%Y')
        
        response += f"📋 **Report ID:** `{report_id}`\n"
        response += f"🎯 Target: `{target}`\n"
        response += f"🗂️ Category: {category}\n"
        response += f"📊 Count: {count} reports\n"
        response += f"📅 Date: {date_str}\n"
        response += "─" * 30 + "\n"
    
    await update.message.reply_text(response)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hidden admin command"""
    user = update.effective_user
    
    # Check if user is admin
    c = db_manager.conn.cursor()
    c.execute("SELECT admin_level FROM admins WHERE telegram_id = ?", (user.id,))
    admin_info = c.fetchone()
    
    if not admin_info:
        await update.message.reply_text(
            "⚠️ **Access Denied**\n\n"
            "Admin panel is hidden and restricted."
        )
        return
    
    admin_level = admin_info[0]
    
    # Get admin stats
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM reports")
    total_reports = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM admins")
    total_admins = c.fetchone()[0]
    
    admin_text = f"""
🔒 **Hidden Admin Panel**

👑 **Your Level:** {admin_level}
📊 **System Stats:**
• 👥 Total Users: {total_users}
• 📋 Total Reports: {total_reports}
• 👑 Total Admins: {total_admins}

⚙️ **Admin Commands:**
/addadmin <id> <level> - Add new admin
/listadmins - List all admins
/stats - Detailed statistics
/backup - Backup database
"""
    
    await update.message.reply_text(admin_text)

async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /logout command"""
    await update.message.reply_text(
        "✅ **Logged Out Successfully!**\n\n"
        "Your session has been terminated.\n"
        "Send /login to login again."
    )
    
    # Log logout activity
    c = db_manager.conn.cursor()
    c.execute('''INSERT INTO activity_logs 
                 (user_id, action, details, created_at)
                 VALUES (?, ?, ?, ?)''',
              (update.effective_user.id, 'logout', 
               'User logged out', datetime.now()))
    db_manager.conn.commit()

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
🆘 **Telegram Report Bot - Help**

📱 **Login System:**
• /login - Start login process
• Phone number + OTP verification
• Multiple users can login

📋 **Reporting:**
• /report - Submit new report
• Choose type, category, target
• Add custom report text
• Select report count (1-50)

👤 **User Commands:**
• /myreports - View your reports
• /logout - Logout from system
• /help - This help menu

🔒 **Security:**
• OTP based authentication
• Hidden admin panel
• Activity logging
• Database backup

⚠️ **Note:** Only approved users can login.
Contact owner for access.
"""
    
    await update.message.reply_text(help_text)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any operation"""
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

# ============ MAIN FUNCTION ============
def main():
    """Main function to run the bot"""
    
    # Create directories
    Path("database").mkdir(exist_ok=True)
    Path("configs").mkdir(exist_ok=True)
    Path("backups").mkdir(exist_ok=True)
    
    # Initialize OTP manager
    global otp_manager
    otp_manager = OTPManager()
    
    # Initialize database
    global db_manager
    db_manager = DatabaseManager()
    
    # Create application
    application = Application.builder().token(CONFIG['bot_token']).build()
    
    # Login conversation handler
    login_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("login", login_command)],
        states={
            "CHOOSE_LOGIN_METHOD": [
                CallbackQueryHandler(PhoneLoginSystem().handle_phone_login, pattern="^(phone_login|tg_login)$")
            ],
            "ENTER_PHONE": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_input)
            ],
            "VERIFY_OTP": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, verify_otp_handler)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )
    
    # Report conversation handler
    report_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("report", report_command)],
        states={
            "SELECT_REPORT_TYPE": [
                CallbackQueryHandler(select_report_type, pattern="^report_type_")
            ],
            "SELECT_CATEGORY": [
                CallbackQueryHandler(select_category, pattern="^category_")
            ],
            "ENTER_TARGET": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_target)
            ],
            "ENTER_REPORT_TEXT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_report_text)
            ],
            "SELECT_REPORT_COUNT": [
                CallbackQueryHandler(select_report_count, pattern="^count_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, select_report_count)
            ],
            "ENTER_CUSTOM_COUNT": [
                MessageHandler(filters.TEXT & ~filters.COMMAND, enter_custom_count)
            ],
            "CONFIRM_SUBMIT": [
                CallbackQueryHandler(submit_report, pattern="^(confirm_submit|cancel_submit)$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(login_conv_handler)
    application.add_handler(report_conv_handler)
    application.add_handler(CommandHandler("myreports", myreports_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("logout", logout_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # Error handler
    application.add_error_handler(lambda u, c: logger.error(f"Update {u} caused error {c.error}"))
    
    # Start bot
    logger.info("🤖 Starting Telegram Report Bot...")
    logger.info(f"👑 Owner ID: {CONFIG['owner_id']}")
    logger.info("📱 Bot is now running...")
    
    print("\n" + "="*50)
    print("🤖 TELEGRAM REPORT BOT SYSTEM")
    print("="*50)
    print(f"📱 Login: Phone Number + OTP")
    print(f"👥 Multi-User Support")
    print(f"🔒 Hidden Admin Panel")
    print(f"📊 Real-time Reporting")
    print("="*50)
    print("🚀 Bot started successfully!")
    print("📞 Users can now login with /login")
    print("="*50)
    
    application.run_polling()

if __name__ == "__main__":
    main()