"""
🤖 ULTRA SMS BOT - With Admin ID
Telegram Bot - Single File for Render
"""

import os
import re
import random
import secrets
import string
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, request, jsonify
from twilio.rest import Client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ===== CONFIG =====
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TWILIO_SID = os.environ.get("TWILIO_SID")
TWILIO_AUTH = os.environ.get("TWILIO_AUTH")
TWILIO_PHONE = os.environ.get("TWILIO_PHONE")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
ADMIN_ID = os.environ.get("ADMIN_ID")  # Your Telegram User ID

# ===== CHECK CONFIG =====
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set!")

if not ADMIN_ID:
    print("⚠️ ADMIN_ID not set! Some admin features disabled.")

DEMO_MODE = not (TWILIO_SID and TWILIO_AUTH and TWILIO_PHONE)

# ===== TWILIO CLIENT =====
twilio_client = None
if not DEMO_MODE:
    twilio_client = Client(TWILIO_SID, TWILIO_AUTH)

# ===== THREAD POOL =====
executor = ThreadPoolExecutor(max_workers=50)

# ===== FLASK APP =====
app = Flask(__name__)

# ===== TELEGRAM BOT =====
bot_app = None

# ===== STATS (In-Memory) =====
stats = {
    "total_sent": 0,
    "total_failed": 0,
    "quick250_used": 0,
    "users": set(),
    "logs": []
}

# ===== ADMIN CHECK =====
def is_admin(user_id):
    return str(user_id) == str(ADMIN_ID) if ADMIN_ID else False

# ===== VALIDATION =====
def validate_number(number):
    clean = re.sub(r"[^0-9]", "", number or "")
    if clean.startswith("91") and len(clean) > 10:
        clean = clean[2:]
    if clean.startswith("0"):
        clean = clean[1:]
    if len(clean) == 10 and clean[0] in "6789":
        return "+91" + clean
    return None

# ===== SMS SEND =====
def send_sms_sync(phone, message):
    if DEMO_MODE:
        return {"success": True, "sid": "DEMO" + secrets.token_hex(8), "demo": True}
    try:
        msg = twilio_client.messages.create(body=message, from_=TWILIO_PHONE, to=phone)
        return {"success": True, "sid": msg.sid, "demo": False}
    except Exception as e:
        return {"success": False, "error": str(e), "demo": False}

def send_bulk_parallel(numbers, message):
    results = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(send_sms_sync, phone, message) for phone in numbers]
        for future in futures:
            results.append(future.result())
    return results

# ===== LOG ACTIVITY =====
def log_activity(user_id, action, details):
    stats["logs"].append({
        "time": datetime.now().isoformat(),
        "user_id": user_id,
        "action": action,
        "details": details
    })
    if len(stats["logs"]) > 1000:
        stats["logs"] = stats["logs"][-1000:]

# ===== TELEGRAM HANDLERS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats["users"].add(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🔥 Quick 250", callback_data="quick250")],
        [InlineKeyboardButton("📨 Single SMS", callback_data="single")],
        [InlineKeyboardButton("📤 Bulk SMS", callback_data="bulk")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")],
        [InlineKeyboardButton("📋 Templates", callback_data="templates")],
    ]
    
    # Admin buttons
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"🤖 *ULTRA SMS BOT v3.0*\n\n"
        f"📱 {250} SMS in One Click!\n"
        f"⚡ 100x Faster than Neo\n"
        f"🔐 Demo Mode: {'ON' if DEMO_MODE else 'OFF'}\n\n"
        f"*Commands:*\n"
        f"/start - Show menu\n"
        f"/quick250 - Send 250 SMS\n"
        f"/send +919876543210 - Single SMS\n"
        f"/bulk +919876543210,9876543211 - Bulk send\n"
        f"/stats - Bot statistics\n"
        f"/templates - All templates\n"
        f"/help - Help menu"
    )
    
    if is_admin(user_id):
        welcome_text += f"\n\n👑 *Admin ID:* {user_id}"
    
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Help Menu*\n\n"
        "*Quick 250:*\n"
        "/quick250 +919876543210\n\n"
        "*Single SMS:*\n"
        "/send +919876543210 Hello\n\n"
        "*Bulk SMS:*\n"
        "/bulk +919876543210,9876543211 Hello\n\n"
        "*Templates:*\n"
        "/templates - View all\n\n"
        "*Stats:*\n"
        "/stats - View stats\n\n"
        "*Admin (if you are admin):*\n"
        "/admin - Admin panel\n"
        "/broadcast - Send message to all users\n"
        "/users - List all users",
        parse_mode='Markdown'
    )

async def quick250_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text("❌ Use: /quick250 +919876543210")
        return
    
    phone = validate_number(args[0])
    if not phone:
        await update.message.reply_text("❌ Invalid Indian number!\nUse: +919876543210 or 9876543210")
        return
    
    await update.message.reply_text(f"⏳ Sending 250 SMS to {phone}...\n⚡ Using 50 threads")
    
    message = "🎉 Welcome to our service! Reply STOP to unsubscribe."
    numbers = [phone] * 250
    
    start_time = time.time()
    results = send_bulk_parallel(numbers, message)
    elapsed = time.time() - start_time
    
    sent = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if not r["success"])
    
    stats["total_sent"] += sent
    stats["total_failed"] += failed
    stats["quick250_used"] += 1
    
    log_activity(user_id, "quick250", {"phone": phone, "sent": sent, "failed": failed})
    
    await update.message.reply_text(
        f"✅ *250 SMS Complete!*\n\n"
        f"📱 Target: {phone}\n"
        f"📤 Sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"⏱️ Time: {elapsed:.2f}s\n"
        f"⚡ Speed: {250/elapsed:.1f} SMS/sec\n"
        f"📊 Total Sent: {stats['total_sent']}",
        parse_mode='Markdown'
    )

async def send_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 1:
        await update.message.reply_text("❌ Use: /send +919876543210 Hello")
        return
    
    phone = validate_number(args[0])
    if not phone:
        await update.message.reply_text("❌ Invalid Indian number!\nUse: +919876543210 or 9876543210")
        return
    
    message = " ".join(args[1:]) if len(args) > 1 else "Hello! Welcome to our service."
    
    await update.message.reply_text(f"⏳ Sending to {phone}...")
    
    result = send_sms_sync(phone, message)
    
    if result["success"]:
        stats["total_sent"] += 1
        log_activity(user_id, "single_sms", {"phone": phone, "message": message[:30]})
        await update.message.reply_text(
            f"✅ *Sent!*\n📱 {phone}\n💬 {message}",
            parse_mode='Markdown'
        )
    else:
        stats["total_failed"] += 1
        await update.message.reply_text(f"❌ Failed: {result.get('error', 'Unknown error')}")

async def bulk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 1:
        await update.message.reply_text("❌ Use: /bulk +919876543210,9876543211 Hello")
        return
    
    numbers_input = args[0].split(',')
    message = " ".join(args[1:]) if len(args) > 1 else "Hello! Welcome to our service."
    
    valid_numbers = []
    invalid_numbers = []
    
    for num in numbers_input:
        v = validate_number(num.strip())
        if v:
            valid_numbers.append(v)
        else:
            invalid_numbers.append(num.strip())
    
    if not valid_numbers:
        await update.message.reply_text("❌ No valid numbers found!")
        return
    
    if len(valid_numbers) > 500:
        await update.message.reply_text("❌ Max 500 numbers per bulk!")
        return
    
    await update.message.reply_text(f"⏳ Sending to {len(valid_numbers)} numbers...")
    
    start_time = time.time()
    results = send_bulk_parallel(valid_numbers, message)
    elapsed = time.time() - start_time
    
    sent = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if not r["success"])
    
    stats["total_sent"] += sent
    stats["total_failed"] += failed
    
    log_activity(user_id, "bulk_sms", {"count": len(valid_numbers), "sent": sent, "failed": failed})
    
    await update.message.reply_text(
        f"✅ *Bulk Complete!*\n\n"
        f"📤 Sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"📱 Total: {len(valid_numbers)}\n"
        f"⏱️ Time: {elapsed:.2f}s\n"
        f"⚡ Speed: {len(valid_numbers)/elapsed:.1f} SMS/sec",
        parse_mode='Markdown'
    )

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stats["users"].add(user_id)
    
    await update.message.reply_text(
        f"📊 *Bot Statistics*\n\n"
        f"🤖 Bot: ULTRA SMS BOT\n"
        f"📱 Version: v3.0\n"
        f"🔐 Demo Mode: {'ON' if DEMO_MODE else 'OFF'}\n"
        f"📤 Total Sent: {stats['total_sent']}\n"
        f"❌ Total Failed: {stats['total_failed']}\n"
        f"🔥 Quick 250 Used: {stats['quick250_used']}\n"
        f"👥 Total Users: {len(stats['users'])}\n"
        f"📊 Logs: {len(stats['logs'])}\n"
        f"⚡ Speed: 100x faster\n\n"
        f"*Powered by Twilio & Render*",
        parse_mode='Markdown'
    )

async def templates_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    templates = [
        "🔥 Welcome",
        "⚡ Promotional",
        "🔐 OTP",
        "📦 Order",
        "💰 Payment",
        "⏰ Reminder",
        "👑 VIP",
        "🎂 Birthday",
        "🎊 Festival",
        "📊 Survey",
        "🛒 Cart",
        "🚚 Shipping",
        "✅ Delivery"
    ]
    
    text = "📋 *Available Templates*\n\n"
    for i, t in enumerate(templates, 1):
        text += f"{i}. {t}\n"
    
    text += "\n*Usage:*\n/send +919876543210 Your message"
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ===== ADMIN COMMANDS =====

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized to use admin commands!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 Full Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 All Users", callback_data="admin_users")],
        [InlineKeyboardButton("📝 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📋 Logs", callback_data="admin_logs")],
        [InlineKeyboardButton("🔄 Reset Stats", callback_data="admin_reset")],
        [InlineKeyboardButton("🔙 Back", callback_data="back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👑 *Admin Panel*\n\n"
        f"User ID: {user_id}\n"
        f"Total Users: {len(stats['users'])}\n"
        f"Total Sent: {stats['total_sent']}\n"
        f"Quick250 Used: {stats['quick250_used']}\n\n"
        f"Select an option:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized!")
        return
    
    args = context.args
    if not args:
        await update.message.reply_text("❌ Use: /broadcast Your message here")
        return
    
    message = " ".join(args)
    users = list(stats["users"])
    
    if not users:
        await update.message.reply_text("❌ No users to broadcast!")
        return
    
    await update.message.reply_text(f"⏳ Broadcasting to {len(users)} users...")
    
    sent = 0
    failed = 0
    
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user,
                text=f"📢 *Broadcast Message*\n\n{message}",
                parse_mode='Markdown'
            )
            sent += 1
        except:
            failed += 1
    
    log_activity(user_id, "broadcast", {"users": len(users), "sent": sent, "failed": failed})
    
    await update.message.reply_text(
        f"✅ *Broadcast Complete!*\n\n"
        f"📤 Sent: {sent}\n"
        f"❌ Failed: {failed}\n"
        f"📱 Total: {len(users)}",
        parse_mode='Markdown'
    )

async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized!")
        return
    
    users = list(stats["users"])
    
    if not users:
        await update.message.reply_text("📭 No users registered yet.")
        return
    
    text = f"👥 *Total Users: {len(users)}*\n\n"
    for i, u in enumerate(users[:20], 1):
        text += f"{i}. `{u}`\n"
    
    if len(users) > 20:
        text += f"\n... and {len(users) - 20} more users"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def admin_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await query.edit_message_text("❌ You are not authorized!")
        return
    
    data = query.data
    
    if data == "admin_stats":
        await query.edit_message_text(
            f"📊 *Full Statistics*\n\n"
            f"Total Sent: {stats['total_sent']}\n"
            f"Total Failed: {stats['total_failed']}\n"
            f"Quick250 Used: {stats['quick250_used']}\n"
            f"Total Users: {len(stats['users'])}\n"
            f"Logs: {len(stats['logs'])}\n"
            f"Demo Mode: {'ON' if DEMO_MODE else 'OFF'}",
            parse_mode='Markdown'
        )
    
    elif data == "admin_users":
        users = list(stats["users"])
        text = f"👥 *Users ({len(users)})*\n\n"
        for i, u in enumerate(users[:30], 1):
            text += f"{i}. `{u}`\n"
        if len(users) > 30:
            text += f"\n... and {len(users) - 30} more"
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "admin_logs":
        logs = stats["logs"][-20:]
        text = "📋 *Recent Logs*\n\n"
        for log in logs:
            text += f"👤 {log['user_id']}\n"
            text += f"└ {log['action']}: {log['details']}\n"
            text += f"└ {log['time'][:16]}\n\n"
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif data == "admin_broadcast":
        await query.edit_message_text(
            "📢 *Broadcast*\n\n"
            "Send message to all users:\n"
            "/broadcast Your message here",
            parse_mode='Markdown'
        )
    
    elif data == "admin_reset":
        stats["total_sent"] = 0
        stats["total_failed"] = 0
        stats["quick250_used"] = 0
        await query.edit_message_text("✅ *Stats Reset Successfully!*", parse_mode='Markdown')
    
    elif data == "back":
        await start(update, context)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if data == "admin":
        await admin_cmd(update, context)
        return
    
    if data.startswith("admin_"):
        await admin_button_callback(update, context)
        return
    
    if data == "quick250":
        await query.edit_message_text(
            "📱 *Quick 250*\n\n"
            "Send the target phone number:\n"
            "/quick250 +919876543210",
            parse_mode='Markdown'
        )
    elif data == "single":
        await query.edit_message_text(
            "📨 *Single SMS*\n\n"
            "Send SMS with:\n"
            "/send +919876543210 Your message",
            parse_mode='Markdown'
        )
    elif data == "bulk":
        await query.edit_message_text(
            "📤 *Bulk SMS*\n\n"
            "Send to multiple numbers:\n"
            "/bulk +919876543210,9876543211 Your message",
            parse_mode='Markdown'
        )
    elif data == "stats":
        await query.edit_message_text(
            f"📊 *Stats*\n\n"
            f"Demo Mode: {'ON' if DEMO_MODE else 'OFF'}\n"
            f"Total Sent: {stats['total_sent']}\n"
            f"Total Failed: {stats['total_failed']}\n"
            f"Users: {len(stats['users'])}\n"
            f"Templates: 13\n"
            f"Speed: 100x faster",
            parse_mode='Markdown'
        )
    elif data == "templates":
        templates = [
            "🔥 Welcome",
            "⚡ Promotional",
            "🔐 OTP",
            "📦 Order",
            "💰 Payment",
            "⏰ Reminder",
            "👑 VIP",
            "🎂 Birthday",
            "🎊 Festival",
            "📊 Survey",
            "🛒 Cart",
            "🚚 Shipping",
            "✅ Delivery"
        ]
        text = "📋 *Templates:*\n\n"
        for i, t in enumerate(templates, 1):
            text += f"{i}. {t}\n"
        await query.edit_message_text(text, parse_mode='Markdown')

# ===== FLASK ROUTES =====

@app.route("/")
def index():
    return jsonify({
        "status": "ok",
        "bot": "ULTRA SMS BOT",
        "version": "v3.0",
        "demo_mode": DEMO_MODE,
        "admin_id": ADMIN_ID,
        "total_users": len(stats["users"]),
        "total_sent": stats["total_sent"]
    })

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    if request.method == "POST":
        data = request.get_json()
        if not data:
            return jsonify({"status": "ok"})
        
        update = Update.de_json(data, bot_app.bot)
        bot_app.process_update(update)
        return jsonify({"status": "ok"})
    return jsonify({"status": "ok"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

# ===== SET WEBHOOK =====
def set_webhook():
    import requests
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}/{BOT_TOKEN}"
    response = requests.get(url)
    print(f"Webhook set: {response.json()}")

# ===== BOT SETUP =====
def setup_bot():
    global bot_app
    
    if not bot_app:
        bot_app = Application.builder().token(BOT_TOKEN).build()
        
        # Commands
        bot_app.add_handler(CommandHandler("start", start))
        bot_app.add_handler(CommandHandler("help", help_cmd))
        bot_app.add_handler(CommandHandler("quick250", quick250_cmd))
        bot_app.add_handler(CommandHandler("send", send_cmd))
        bot_app.add_handler(CommandHandler("bulk", bulk_cmd))
        bot_app.add_handler(CommandHandler("stats", stats_cmd))
        bot_app.add_handler(CommandHandler("templates", templates_cmd))
        
        # Admin Commands
        bot_app.add_handler(CommandHandler("admin", admin_cmd))
        bot_app.add_handler(CommandHandler("broadcast", broadcast_cmd))
        bot_app.add_handler(CommandHandler("users", users_cmd))
        
        # Callbacks
        bot_app.add_handler(CallbackQueryHandler(button_callback))

# ===== INIT =====
setup_bot()

if WEBHOOK_URL and BOT_TOKEN:
    set_webhook()
    print(f"✅ Webhook set to: {WEBHOOK_URL}/{BOT_TOKEN}")
else:
    print("⚠️ WEBHOOK_URL not set, webhook not configured")

print(f"👑 Admin ID: {ADMIN_ID}")
print(f"🤖 Bot started!")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)