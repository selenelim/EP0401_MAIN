#thingspeak section untested, flask not connecting properly

import threading
import RPi.GPIO as GPIO
import I2C_LCD_driver
from time import sleep
from picamera.array import PiRGBArray
from picamera import PiCamera
import cv2
from pyzbar import pyzbar
import requests
import dht11
import datetime

VALID_SERVICE_CODES = ["1234", "4321"]  # Add your valid 4-digit servicing codes here

# --- Configuration ---
FLASK_VERIFY_URL = "http://192.168.0.1:5000/verify"  # Replace with your Pi's IP
SERVO_PIN = 26
DHT_PIN = 21  # DHT11 connected to GPIO 21
instance = dht11.DHT11(pin=DHT_PIN)

# --- Buzzer setup ---
BUZZER_PIN = 18  # Ensure this is set globally
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUZZER_PIN, GPIO.OUT)


# --- Servo setup ---
SERVO_PIN = 26
GPIO.setmode(GPIO.BCM)
GPIO.setup(SERVO_PIN, GPIO.OUT)
servo = GPIO.PWM(SERVO_PIN, 50)  # 50Hz frequency
servo.start(0)
GPIO.setwarnings(False)

# --- Keypad setup ---
MATRIX = [
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9],
    ['*', 0, '#']
]

ROW = [6, 20, 19, 13]
COL = [12, 5, 16]

def setup_keypad():
    GPIO.setwarnings(False)
    for i in range(3):
        GPIO.setup(COL[i], GPIO.OUT)
        GPIO.output(COL[i], 1)
    for j in range(4):
        GPIO.setup(ROW[j], GPIO.IN, pull_up_down=GPIO.PUD_UP)

def read_keypad():
    while True:
        for i in range(3):
            GPIO.output(COL[i], 0)
            for j in range(4):
                if GPIO.input(ROW[j]) == 0:
                    key = MATRIX[j][i]
                    while GPIO.input(ROW[j]) == 0:
                        sleep(0.1)
                    GPIO.output(COL[i], 1)
                    return str(key)
            GPIO.output(COL[i], 1)

# --- LCD setup ---
LCD = I2C_LCD_driver.lcd()

def lcd_clear():
    LCD.lcd_clear()

def lcd_message(line1, line2=""):
    lcd_clear()
    LCD.lcd_display_string(line1, 1)
    if line2:
        LCD.lcd_display_string(line2, 2)

# --- Drinks ---
drinks = {
    "1": {"name": "Coke", "price": 1.40, "stock": 0},
    "2": {"name": "Sprite", "price": 1.50, "stock": 7},
    "3": {"name": "Iced Tea", "price": 1.35, "stock": 9},
    "4": {"name": "Green Tea", "price": 5.00, "stock": 6},
    "5": {"name": "Mineral Water", "price": 1.00, "stock": 5}
}
# --- DHT setup ---
dht_instance = dht11.DHT11(pin=DHT_PIN)

# --- Menu Functions ---

def displayMainMenu():
    lcd_message("1.Select Drink", "2.Remote Pickup")

def selectMainMenu():
    while True:
        choice = read_keypad()
        if choice == '1':
            displayDrinkOptions()
            selectDrinkOptions()
            break
        elif choice == '2':
            lcd_message("Remote Pickup", "Enabling Camera")
            sleep(2)
            enableCamera()
            break
        elif choice == '#':   # Servicing mode trigger
            servicing_mode()
            break

def displayDrinkOptions():
    lcd_message("1.Cola $1.40", "2.Sprite $1.50")
    sleep(2)
    lcd_message("3.Tea $1.35", "4.Water $1.00")

def selectDrinkOptions():
    while True:
        choice = read_keypad()
        if choice in drinks:
            if checkDrinkStock(choice):
                displayPurchaseConfirmation(choice)
                break
            else:
                displayDrinkOptions()

def checkDrinkStock(choice):
    if drinks[choice]["stock"] == 0:
        lcd_message("Out of Stock!", "Choose again")
        sleep(2)
        return False
    return True

def displayPurchaseConfirmation(choice):
    drink = drinks[choice]
    lcd_message(f"{drink['name']} ${drink['price']:.2f}", "*=Buy #=Cancel")
    while True:
        confirm = read_keypad()
        if confirm == '*':
            if handlePayment():
                dispenseDrink(choice)
            else:
                lcd_message("Payment Failed", "Try again")
                sleep(2)
                displayPurchaseConfirmation(choice)
            break
        elif confirm == '#':
            displayDrinkOptions()
            selectDrinkOptions()
            break
# --- Remote Pickup ---
def get_drink_key_by_name(name):
    for key, info in drinks.items():
        if info["name"].lower() == name.lower():
            return key
    return None


def enableCamera():
    camera = PiCamera()
    camera.resolution = (640, 480)
    camera.framerate = 32
    rawCapture = PiRGBArray(camera, size=(640, 480))

    lcd_message("Scan QR Code")

    try:
        for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
            image = frame.array
            decoded_objs = pyzbar.decode(image)
            if decoded_objs:
                for obj in decoded_objs:
                    code = obj.data.decode("utf-8")
                    lcd_message("Code Scanned!", code[:16])
                    print(f"Scanned Code: {code}")
                    try:
                        resp = requests.post(FLASK_VERIFY_URL, json={"code": code})
                        print("[Flask Response]", resp.status_code, resp.text)  # Debug print

                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("status") == "success":
                                drink_name = data.get("drink", "Drink")
                                drink_key = get_drink_key_by_name(drink_name)
                                if drink_key:
                                    lcd_message("Verified!", "Dispensing...")
                                    sleep(2)
                                    dispenseDrink(choice=drink_key)
                                else:
                                    lcd_message("Drink Not Found")
                                    sleep(2)
                                    displayMainMenu()
                                    selectMainMenu()
                           
                        else:
                            lcd_message("Invalid Code", "")
                            sleep(2)
                            displayMainMenu()
                            selectMainMenu()

                    except Exception as e:
                        lcd_message("Network Error", 1)
                        sleep(2)
                        lcd_clear()
                        displayMainMenu()
                        selectMainMenu
            rawCapture.truncate(0)
    except KeyboardInterrupt:
        pass
    finally:
        camera.close()
        displayMainMenu()
        selectMainMenu()
# --- Payment System ---

def displayPaymentMethod():
    lcd_message("Choose Payment:", "")
    sleep(2)
    lcd_message("1.RFID 2.QR Code", "3.Cash")
    sleep(2)

def selectPaymentMethod():
    while True:
        method = read_keypad()
        if method in ['1', '2', '3']:
            return method

def enableRFID():
    lcd_message("RFID Enabled", "Scan your tag")
    sleep(3)
    return True

def enableQRPayment():
    lcd_message("Camera Enabled", "Scan QR Code")
    sleep(3)
    return False # Simulate Failure

def processCash():
    lcd_message("Insert Cash", "Waiting...")
    sleep(3)
    return True  # Simulate success

def handlePayment():
    displayPaymentMethod()
    method = selectPaymentMethod()
    if method == '1':
        success = enableRFID()
    elif method == '2':
        success = enableQRPayment()
    elif method == '3':
        success = processCash()
    else:
        success = False

    if success:
        lcd_message("Processing...", "Please wait")
        sleep(2)
        lcd_message("Payment Success", "")
        sleep(2)
        return True
    else:
        lcd_message("Payment Failed", "")
        sleep(2)
        return False

# --- Dispense Function ---

def dispenseDrink(choice):
    drink = drinks[choice]
    if drink["stock"] <= 0:
        lcd_message("Out of Stock!", drink["name"])
        sleep(2)
        displayMainMenu()
        selectMainMenu()
        return

    drinks[choice]["stock"] -= 1
    lcd_message("Dispensing...", drink['name'])

    # Servo rotate to 90 degrees then back
    servo.ChangeDutyCycle(7.5)  # ~90°
    sleep(2)
    servo.ChangeDutyCycle(2.5)  # ~0°
    sleep(0.5)
    servo.ChangeDutyCycle(0)    # Stop signal

    sleep(1)
    lcd_message("Enjoy your drink!")
    sleep(2)
    displayMainMenu()
    selectMainMenu()

# --- Serviving Function ---
def servicing_mode():
    lcd_message("Key 4-digit Code", "Press 0 to exit")
    code = ""
    while True:
        key = read_keypad()
        if key == '0':  # exit servicing mode
            displayMainMenu()
            selectMainMenu()
            return
        elif key.isdigit():
            code += key
            lcd_message("Code: " + "*"*len(code), "Press 0 to exit")
            if len(code) == 4:
                if code in VALID_SERVICE_CODES:
                    lcd_message("Access Granted", "Opening Door")
                    open_door()
                    sleep(2)
                    displayServicingMode()
                    
                    return
                else:
                    lcd_message("Invalid Code", "")
                    sleep(5)
                    displayMainMenu()
                    selectMainMenu()
                    return
                
def open_door():
    # Example servo operation to unlock door
    servo.ChangeDutyCycle(7.5)  # rotate to open position
    sleep(3)
    servo.ChangeDutyCycle(0)    # stop signal

def close_door():
    servo.ChangeDutyCycle(2.5)  # rotate back to close position
    sleep(3)
    servo.ChangeDutyCycle(0)    # stop signal

def displayServicingMode():
    lcd_message("Select Service:", "1.Cool 2.Restock")
    sleep(2)
    lcd_message("0.Exit Service","  Mode")
    selectServicingMode()


def selectServicingMode():
    while True:
        key = read_keypad()
        if key == '1':
            displayStorageTemp()
            break
        elif key == '2':
            displayRestockMenu()
            break
        elif key == '0':
            exitServicingMode()
            break

def exitServicingMode():
    lcd_message("Exiting Service", "Returning...")
    sleep(2)
    close_door()
    lcd_clear()
    # Return to main menu
    displayMainMenu()
    selectMainMenu()

def displayStorageTemp():
    temp = read_temperature()
    if temp is not None:
        lcd_message(f"Temp: {temp:.1f}C", "Press * to Cool")
        if read_keypad() == '*':
            enableCooling()
    else:
        lcd_message("Sensor Error", "Try Again")
        sleep(2)
        displayStorageTemp()

def read_temperature():
    result = instance.read()
    if result.is_valid():
        return round(result.temperature, 1)
    return None

def enableCooling():
    # Simulate cooling process
    lcd_message("Cooling Mode", "Running 2 min...")
    sleep(12)  # 2 min set to 120 for 2 min i shortened it for testing
    GPIO.output(18,1) #output logic high/'1'
    sleep(0.5) #delay 1 second
    GPIO.output(18,0) #output logic low/'0'
    lcd_message("Cooling Success", "Returning...")
    sleep(3)
    displayServicingMode()

def displayRestockMenu():
    print("Restock Menu:")
    for key, drink in drinks.items():
        print(f"{key}. {drink['name']}: {drink['stock']} in stock")

    lcd_message("Select Drink No.")
    displayDrinkOptions()
    selected = read_keypad()

    if selected in drinks:
        confirmRestock(selected)
    else:
        lcd_message("Invalid Selection")
        sleep(2)
        displayRestockMenu()


def confirmRestock(selected):
    lcd_message("Press * to", "Confirm Restock")
    key = read_keypad()

    if key == '*':
        performRestock(selected)
    else:
        lcd_message("Restock","Cancelled")
        sleep(2)
        displayServicingMode()

def performRestock(drink_id):
    drink = drinks[drink_id]
    name = drink["name"]
    current_stock = drink["stock"]

    new_stock, status = handleStockLimit(current_stock)
    drinks[drink_id]["stock"] = new_stock

    displayRestockResult(drink_id, name, new_stock, status)


def handleStockLimit(current_stock):
    if current_stock >= 30:
        return current_stock, "full"

    new_stock = current_stock + 5
    if new_stock > 30:
        new_stock = 30

    return new_stock, "restocked"


def displayRestockResult(drink_id, name, new_stock, status):
    if status == "full":
        lcd_message("Stock Full", "No Action Taken")
        sleep(3)

    elif status == "restocked":
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        sleep(0.5)
        GPIO.output(BUZZER_PIN, GPIO.LOW)

        lcd_message(f"{name}", "Restocked!")
        sleep(3)

        lcd_message(f"New Stock: {new_stock}")
        sleep(6)

    displayRestockMenu()

# --- ThingSpeak upload thread function ---
def upload_dht_to_thingspeak():
    THINGSPEAK_API_KEY = "83KJJ5TERTPI3C3T"
    THINGSPEAK_URL = 'https://api.thingspeak.com/update'

    while True:
        result = dht_instance.read()
        if result.is_valid():
            temp = result.temperature
            hum = result.humidity
            print(f"[DHT] Temp={temp:.1f}C  Humidity={hum:.1f}%")
            payload = {
                'api_key': THINGSPEAK_API_KEY,
                'field1': temp,
                'field2': hum
            }
            try:
                response = requests.get(THINGSPEAK_URL, params=payload, timeout=10)
                print(f"[DHT] Uploaded to ThingSpeak, response code: {response.status_code}")
            except Exception as e:
                print(f"[DHT] Upload failed: {e}")
        else:
            print("[DHT] Failed to get reading.")

        sleep(15)

# --- Main program start ---
if __name__ == "__main__":
    try:
        setup_keypad()
        lcd_message("Starting System", "Please wait...")

        # Start ThingSpeak upload in background thread
        dht_thread = threading.Thread(target=upload_dht_to_thingspeak, daemon=True)
        dht_thread.start()

        # Start main menu flow
        lcd_message("Welcome!", "Select Option")
        displayMainMenu()
        selectMainMenu()

    except KeyboardInterrupt:
        print("Exiting program...")

    finally:
        lcd_clear()
        servo.stop()
        GPIO.cleanup()
