
import random
import json
import os
import qrcode
from io import BytesIO
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = "REPLACE WITH BOT TOKEN"
ADMINS = [USER ID HERE]  # Your Telegram user IDs here

CODES_FILE = "codes.json"
STOCK_FILE = "stock.json"

# --- File utilities ---
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

# --- Initialize ---
available_drinks = load_json(STOCK_FILE)  # Should be dict like {"Cola": {"price": 1.40, "stock": 5}, ...}
codes = load_json(CODES_FILE)
payments = {}  # user_id -> drink
sales = {drink: 0 for drink in available_drinks}

# --- Bot commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Welcome! Use /menu to see drinks.\n"
        "Pay with /pay <drink>.\n"
        "Then order with /order <drink> to get your unique QR code."
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Available Drinks:\n"
    for d, info in available_drinks.items():
        text += f"- {d} (RM{info['price']}) — Stock: {info['stock']}\n"
    await update.message.reply_text(text)

async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not context.args:
        await update.message.reply_text("Usage: /pay <drink>")
        return

    drink = " ".join(context.args).title()
    if drink not in available_drinks:
        await update.message.reply_text("Invalid drink. Use /menu to see available drinks.")
        return

    if available_drinks[drink]["stock"] <= 0:
        await update.message.reply_text(f"❌ {drink} is out of stock. Please choose another drink.")
        return

    payments[user.id] = drink
    await update.message.reply_text(f"✅ Payment recorded for {drink}. Now use /order {drink}.")

async def order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if not context.args:
        await update.message.reply_text("Usage: /order <drink>")
        return

    drink = " ".join(context.args).title()
    if drink not in available_drinks:
        await update.message.reply_text("Invalid drink. Use /menu to see available drinks.")
        return

    if available_drinks[drink]["stock"] <= 0:
        await update.message.reply_text(f"❌ {drink} is out of stock. Please choose another drink.")
        return

    if payments.get(user.id) != drink:
        await update.message.reply_text("You must pay first using /pay <drink>.")
        return

    # Generate unique 6-digit code
    while True:
        code = str(random.randint(100000, 999999))
        if code not in codes:
            break

    codes[code] = {"drink": drink, "used": False}
    save_json(CODES_FILE, codes)
    payments.pop(user.id)

    # Update stock and sales locally (stock.json will be synced by Flask later on dispense)
    if available_drinks[drink]["stock"] > 0:
        available_drinks[drink]["stock"] -= 1
    sales[drink] += 1
    save_json(STOCK_FILE, available_drinks)

    # Generate QR code
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    bio = BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)

    await update.message.reply_photo(
        photo=InputFile(bio, filename=f"{code}.png"),
        caption=f"🎫 QR Code: {code}\nShow this to the vending machine to get your {drink}!"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.id not in ADMINS:
        await update.message.reply_text("🚫 You are not authorized to view stats.")
        return

    total = sum(sales.values())
    msg = f"📊 Total drinks sold: {total}\n\n"
    for drink, count in sales.items():
        stock = available_drinks[drink]["stock"]
        msg += f"- {drink}: Sold: {count} | Stock left: {stock}\n"

    await update.message.reply_text(msg)

async def restock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if user.id not in ADMINS:
        await update.message.reply_text("🚫 You are not authorized to restock.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /restock <drink> <quantity>")
        return

    drink = " ".join(context.args[:-1]).title()
    try:
        qty = int(context.args[-1])
    except ValueError:
        await update.message.reply_text("Please enter a valid quantity.")
        return

    if drink not in available_drinks:
        await update.message.reply_text("Invalid drink.")
        return

    available_drinks[drink]["stock"] += qty
    save_json(STOCK_FILE, available_drinks)
    await update.message.reply_text(f"✅ Restocked {drink}. New stock: {available_drinks[drink]['stock']}")

# --- Run Bot ---
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CommandHandler("pay", pay))
    app.add_handler(CommandHandler("order", order))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("restock", restock))  # Admin only

    print("Bot started...")
    app.run_polling()
