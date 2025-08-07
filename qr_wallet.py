# For QR Payment, since we cant use actual paynow/paylah since requires a business.
import json
import qrcode
from io import BytesIO
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

WALLET_FILE = "qrwallet.json"
ADMIN_PASSWORD = "admin123"  # Change this

# --- Utility functions ---
def load_wallet():
    try:
        with open(WALLET_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_wallet(wallet):
    with open(WALLET_FILE, "w") as f:
        json.dump(wallet, f, indent=2)

def generate_qr(wallet_id):
    img = qrcode.make(wallet_id)
    bio = BytesIO()
    bio.name = f"{wallet_id}.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio

# --- Command Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"Hi {user.first_name}! 👋\nUse /myqr to get your QR code.\nUse /balance to check your wallet.")

async def myqr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    wallet = load_wallet()

    if user_id not in wallet:
        await update.message.reply_text("❌ Wallet not found. Ask admin to register you.")
        return

    qr_image = generate_qr(user_id)
    await update.message.reply_photo(photo=qr_image, caption=f"Here’s your QR code.\nWallet ID: {user_id}")

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    wallet = load_wallet()

    if user_id in wallet:
        bal = wallet[user_id]
        await update.message.reply_text(f"💰 Your balance: ${bal:.2f}\n/topup <amt> to top up!")
    else:
        await update.message.reply_text("❌ Wallet not found. /register to register")

async def adduser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 3:
        await update.message.reply_text("Usage: /adduser <wallet_id> <amount> <admin_pass>")
        return

    wallet_id, amount_str, password = args
    if password != ADMIN_PASSWORD:
        await update.message.reply_text("❌ Unauthorized.")
        return

    try:
        amount = float(amount_str)
    except ValueError:
        await update.message.reply_text("Invalid amount.")
        return

    wallet = load_wallet()
    wallet[wallet_id] = amount
    save_wallet(wallet)
    await update.message.reply_text(f"✅ User '{wallet_id}' added with ${amount:.2f}")

async def addbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 3:
        await update.message.reply_text("Usage: /addbalance <wallet_id> <amount> <admin_pass>")
        return

    wallet_id, amount_str, password = args
    if password != ADMIN_PASSWORD:
        await update.message.reply_text("❌ Unauthorized.")
        return

    try:
        amount = float(amount_str)
    except ValueError:
        await update.message.reply_text("Invalid amount.")
        return

    wallet = load_wallet()
    if wallet_id not in wallet:
        await update.message.reply_text("❌ Wallet ID not found.")
        return

    wallet[wallet_id] += amount
    save_wallet(wallet)
    await update.message.reply_text(f"✅ Added ${amount:.2f} to '{wallet_id}'")

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    wallet = load_wallet()

    if user_id in wallet:
        await update.message.reply_text("📝 You’re already registered!")
        return

    wallet[user_id] = 0.00
    save_wallet(wallet)
    await update.message.reply_text("✅ Registration complete! Your wallet has been created with $0.00.\nUse /topup to add funds or /myqr to get your QR code.")

async def topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    wallet = load_wallet()

    if user_id not in wallet:
        await update.message.reply_text("❌ You need to /register first.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /topup <amount>")
        return

    try:
        amount = float(context.args[0])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid positive amount.")
        return

    wallet[user_id] += amount
    save_wallet(wallet)
    await update.message.reply_text(f"✅ Topped up ${amount:.2f}. New balance: ${wallet[user_id]:.2f}")

# --- Main Bot Start ---
def main():
    TELEGRAM_TOKEN = "8145426423:AAEUyYZB-F_v2NOEjBHnAbBxFEj1CI_zv-s"  # Replace with real token

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myqr", myqr))
    app.add_handler(CommandHandler("balance", balance))
    app.add_handler(CommandHandler("adduser", adduser))
    app.add_handler(CommandHandler("addbalance", addbalance))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("topup", topup))



    print("🟢 Wallet Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()