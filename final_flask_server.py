#Verifies QR Codes for Remote Pickup and for QR Payment
from flask import Flask, request, jsonify
import json
import os
from time import sleep

app = Flask(__name__)

CODES_FILE = "codes.json"
STOCK_FILE = "stock.json"
WALLET_FILE = "qrwallet.json"

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

def dispense_drink():
    print("⚙️ Simulated servo: Drink dispensed!")

def display_lcd_success(drink):
    print(f"✅ LCD: Dispensing {drink}...")

def display_lcd_failure(msg):
    print(f"❌ LCD: {msg}")

def display_lcd_done():
    print("✅ LCD: Enjoy your drink!")

def load_wallet():
    if os.path.exists(WALLET_FILE):
        with open(WALLET_FILE, "r") as f:
            return json.load(f)
    return {}

def save_wallet(wallet):
    with open(WALLET_FILE, "w") as f:
        json.dump(wallet, f, indent=2)



@app.route('/verify', methods=['POST'])
def verify_code():
    try:
        print("🔍 Received request:")
        print(request.data)

        data = request.get_json()
        if not data or "code" not in data:
            print("❌ Missing code in request")
            return jsonify({"status": "error", "message": "Missing code"}), 400

        code = str(data["code"]).strip()
        print(f"➡️ Code received: {code}")

        codes = load_json(CODES_FILE)
        stock = load_json(STOCK_FILE)

        if code not in codes:
            display_lcd_failure("Invalid QR Code")
            print("❌ Invalid code")
            return jsonify({"status": "error", "message": "Invalid code"}), 400

        if codes[code]["used"]:
            display_lcd_failure("Code Already Used")
            print("⚠️ Code already used")
            return jsonify({"status": "error", "message": "Code already used"}), 400

        drink = codes[code]["drink"]
        print(f"🧃 Drink associated with code: {drink}")

        if drink not in stock or stock[drink]["stock"] <= 0:
            display_lcd_failure("Out of Stock")
            print("🚫 Out of stock")
            return jsonify({"status": "error", "message": "Out of stock"}), 400

        # Mark code as used
        codes[code]["used"] = True
        stock[drink]["stock"] -= 1
        save_json(CODES_FILE, codes)
        save_json(STOCK_FILE, stock)

        display_lcd_success(drink)
        dispense_drink()
        sleep(3)
        display_lcd_done()

        print("✅ Success")
        return jsonify({"status": "success", "drink": drink})

    except Exception as e:
        print("💥 Exception occurred:")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Internal server error"}), 500

@app.route("/verify_payment", methods=["POST"])
def verify_payment():
    try:
        print("[SERVER] Raw data:", request.data)
        data = request.get_json(force=True)
        print("[SERVER] Parsed JSON:", data)

        user_id = data.get("user_id")
        price = data.get("price")

        wallet = load_wallet()
        print(f"[SERVER] Checking user_id={user_id}, price={price}, wallet={wallet}")

        if user_id in wallet and wallet[user_id] >= price:
            wallet[user_id] -= price
            save_wallet(wallet)
            return jsonify({"success": True, "new_balance": wallet[user_id]})
        else:
            return jsonify({"success": False, "error": "Insufficient balance or invalid ID"}), 400
    except Exception as e:
        print(f"[SERVER ERROR] {e}")
        return jsonify({"success": False, "error": "Server exception"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)