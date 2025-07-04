from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import random

orders = {}
payments = {}  # Track who paid for what
available_drinks = ["Coke", "Sprite", "Iced Tea", "Green Tea", "Mineral Water"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome! Use /menu to see drinks.\n"
        "First, simulate payment with /pay <drink>.\n"
        "Then order with /order <drink> to get your pickup code."
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu_text = "🧃 Available Drinks:\n" + "\n".join(f"- {drink}" for drink in available_drinks)
    await update.message.reply_text(menu_text)

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    drink = " ".join(context.args).title()

    if not drink:
        await update.message.reply_text("⚠️ Please specify a drink to pay for. Example: /pay Coke")
        return

    if drink not in available_drinks:
        await update.message.reply_text("❌ That drink isn't available. Type /menu to see options.")
        return

    payments[user.id] = drink
    await update.message.reply_text(f"💰 Payment received for {drink}, {user.first_name}! Now order with /order {drink}")

async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    drink = " ".join(context.args).title()

    if not drink:
        await update.message.reply_text("⚠️ Please specify a drink to order. Example: /order Coke")
        return

    if drink not in available_drinks:
        await update.message.reply_text("❌ That drink isn't available. Type /menu to see options.")
        return

    # Check if user paid
    if payments.get(user.id) != drink:
        await update.message.reply_text("❌ You must pay first! Use /pay <drink> to simulate payment.")
        return

    # Generate pickup code
    code = str(random.randint(1000, 9999))
    orders[code] = {"user": user.username, "drink": drink}

    # Remove payment after ordering
    payments.pop(user.id, None)

    await update.message.reply_text(f"✅ Thanks {user.first_name}! Your pickup code is: {code}")

async def list_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not orders:
        await update.message.reply_text("📭 No pending orders.")
        return
    msg = "\n".join([f"{c} - {v['drink']} (by @{v['user']})" for c, v in orders.items()])
    await update.message.reply_text(f"📦 Pending orders:\n{msg}")

TOKEN = "Go tele BotFather for the token"

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("menu", menu))
app.add_handler(CommandHandler("pay", pay))
app.add_handler(CommandHandler("order", order))
app.add_handler(CommandHandler("list", list_codes))

app.run_polling()
