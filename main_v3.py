#Everything works only left rfid untested, but tested on other kit it works.
#devops-admin-monitor bot is integrated here

import threading
import RPi.GPIO as GPIO
import I2C_LCD_driver
from time import sleep
from picamera import PiCamera
from picamera.array import PiRGBArray
import cv2
from pyzbar import pyzbar
import requests
import dht11
import datetime
from mfrc522 import SimpleMFRC522
import sys
import json
import math
import smbus
import time

# --- Constants and Global Configs ---
DEVICE_ADDRESS = 0x53
POWER_CTL = 0x2D
DATA_FORMAT = 0x31
DATAX0 = 0x32
bus = smbus.SMBus(1)
MOVEMENT_THRESHOLD = 280

VALID_SERVICE_CODES = ["1234", "4321"]
WALLET_FILE = "wallet.json"
FLASK_VERIFY_URL = "http://192.168.0.101:5000/verify"
FLASK_QR_PAYMENT_URL = "http://192.168.0.101:5000/verify_payment"
SERVO_PIN = 26
DHT_PIN = 21
LED_PIN = 24
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
instance = dht11.DHT11(pin=DHT_PIN)
TELEGRAM_TOKEN = "token"
TELEGRAM_CHAT_ID = "id"
TEMP_THRESHOLD = 30
BUZZER_PIN = 18
THINGSPEAK_API_KEY = "83KJJ5TERTPI3C3T"

GPIO.setup(BUZZER_PIN, GPIO.OUT)
GPIO.setup(SERVO_PIN, GPIO.OUT)
GPIO.setup(LED_PIN,GPIO.OUT)
servo = GPIO.PWM(SERVO_PIN, 50)
servo.start(0)

reader = SimpleMFRC522()
MATRIX = [[1, 2, 3], [4, 5, 6], [7, 8, 9], ['*', 0, '#']]
ROW = [6, 20, 19, 13]
COL = [12, 5, 16]

LCD = I2C_LCD_driver.lcd()
dht_instance = dht11.DHT11(pin=DHT_PIN)

camera = PiCamera()
camera.resolution = (1024, 768)
sleep(2)

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
    "4": {"name": "Green Tea", "price": 2.00, "stock": 6},
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
            enableRemotePickup()
            break
        elif choice == '#':   # Servicing mode trigger
            servicing_mode()
            break

def displayDrinkOptions():
    lcd_message("1.Cola $1.40", "2.Sprite $1.50")
    sleep(2)
    lcd_message("3.Iced Tea $1.35", "4.Green Tea $2.00")
    sleep(2)
    lcd_message("5.Water $1.00","")

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
            if handlePayment(choice):
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
def enableRemotePickup():
    rawCapture = PiRGBArray(camera, size=(640, 480))
    camera.resolution = (640, 480)
    camera.framerate = 24

    lcd_message("Scan QR Code")
    sleep(2)

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
                        resp = requests.post(FLASK_VERIFY_URL, json={"code": code}, timeout=5)
                        if resp.status_code == 200 and resp.json().get("status") == "success":
                            drink_name =resp.json().get("drink")
                            drink_id = get_drink_key_by_name(drink_name)
                            
                            if drink_id and checkDrinkStock(drink_id):
                                lcd_message("Verified",f"Dispensing {drink_name}")
                                dispenseDrink(drink_id)
                            else:
                                lcd_message("Drink Invalid","Try Again")
                                sleep(2)
                        else:
                            lcd_message("Invalid Code", "Try Again")
                            sleep(2)
                            displayMainMenu()
                            selectMainMenu()
                            

                    except:
                        lcd_message("Network Error", "Check server")
                        sleep(2)
                        displayMainMenu()
                        selectMainMenu()
            rawCapture.truncate(0)
    except KeyboardInterrupt:
        pass

def setup_adxl345():
    bus.write_byte_data(DEVICE_ADDRESS, POWER_CTL, 0x08)
    bus.write_byte_data(DEVICE_ADDRESS, DATA_FORMAT, 0x08)

def read_axes():
    data = bus.read_i2c_block_data(DEVICE_ADDRESS, DATAX0, 6)
    x = int.from_bytes(data[0:2], 'little', signed=True)
    y = int.from_bytes(data[2:4], 'little', signed=True)
    z = int.from_bytes(data[4:6], 'little', signed=True)
    return x, y, z

def magnitude(x, y, z):
    return math.sqrt(x*x + y*y + z*z)

def send_telegram_photo(img_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
    with open(img_path, 'rb') as photo:
        files = {"photo": photo}
        data = {"chat_id": TELEGRAM_CHAT_ID}
        response = requests.post(url, files=files, data=data)
        if response.status_code == 200:
            print("[Telegram] Photo sent.")
        else:
            print(f"[Telegram] Failed: {response.text}")

def upload_dht_to_thingspeak():
    while True:
        result = dht_instance.read()
        if result.is_valid():
            temp = result.temperature
            hum = result.humidity
            print(f"[DHT] Temp={temp}C  Humidity={hum}%")

            # --- ALERT: Telegram if too hot ---
            if temp >= TEMP_THRESHOLD:
                send_telegram_alert(temp)

            # Upload to ThingSpeak
            payload = {
                "api_key": THINGSPEAK_API_KEY,
                "field1": temp,
                "field2": hum
            }
            try:
                r = requests.post("https://api.thingspeak.com/update", data=payload, timeout=5)
                print("[ThingSpeak] Response:", r.text)
            except Exception as e:
                print(f"[ThingSpeak] Error: {e}")
        
        sleep(15)

def send_telegram_alert(temp):
    message = f"\U0001F6A8 ALERT: Temp = {temp:.1f}°C exceeds limit!"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("[Telegram] Alert sent successfully.")
        else:
            print(f"[Telegram] Failed: {response.text}")
    except Exception as e:
        print(f"[Telegram] Exception: {e}")


def takePhoto():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    img_path = f"/home/pi/burglary_{timestamp}.jpg"
    camera.capture(img_path)
    send_telegram_photo(img_path)
    print(f"[Camera] Photo taken and sent: {img_path}")

def monitor_system():
    setup_adxl345()
    previous_mag = 0

    while True:
        x, y, z = read_axes()
        mag = magnitude(x, y, z)
        smoothed = 0.7 * previous_mag + 0.3 * mag
        previous_mag = smoothed

        print(f"[ADXL345] X={x} Y={y} Z={z} Mag={smoothed:.2f}")

        if smoothed > MOVEMENT_THRESHOLD:
            print(" Movement detected!")
            takePhoto()
            activate_buzzer_led()
            sleep(5)
        else:
            print("All normal")
        sleep(1)

buzzer_pwm = GPIO.PWM(BUZZER_PIN, 200)

def activate_buzzer_led():
    start = time.time()
    while time.time() - start <30:
        GPIO.output(LED_PIN,GPIO.HIGH)
        GPIO.output(BUZZER_PIN,GPIO.HIGH)
        sleep(0.5)
        GPIO.output(LED_PIN,GPIO.LOW)
        GPIO.output(BUZZER_PIN,GPIO.LOW)
        sleep(0.5)
    

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

# --- RFID PAYMENT ---
def enableRFID():
    setup_keypad()
    while True:
        print("RFID reader Enabled")
        sleep(2)
        lcd_message("RFID ENABLED","")
        sleep(2)
        print("Hold Card near the reader")
        lcd_message("Tap Card","")
        id = str(reader.read_id())
        with open("authlist.txt", "a+"):
            pass  # Ensure file exists
        with open("authlist.txt", "r+") as f:
            auth = f.read().splitlines()
            if id in auth:
                print("Card:", id, "read successfully")
                sleep(2)
                lcd_message(id,"read succesfully")
                sleep(2)
                return True
            else:
                print("Card Not Registered")
                sleep(2)
                lcd_message("Card","Not Recognised")
                sleep(2)
                print("Do you want to register?")
                sleep(2)
                lcd_message("Do you want","to register?")
                sleep(2)
                print("Press 1 to Register")
                print("Press * to Not Register")
                lcd_message("1.Register","2.Not Register")
                sleep(2)
                confirm = read_keypad()
                if confirm == '1':
                    f.write(id + '\n')
                    print("Card:", id, "has been successfully registered")
                    lcd_message("Successfully","Registered")
                    return True
                else:
                        print("Card not registered. Returning to main loop.")
                        return False

def processCash():
    lcd_message("Insert Cash", "Waiting...")
    sleep(3)
    return True  # Simulate success

def enableQRpayment(price):
    rawCapture = PiRGBArray(camera, size=(640, 480))
    camera.resolution = (640, 480)
    camera.framerate = 24
    lcd_message("Scan QR","for Payment")
    try:
        for frame in camera.capture_continuous( rawCapture, format="bgr",use_video_port=True):
            img=frame.array
            qr_codes = pyzbar.decode(img)
            if qr_codes:
                user_id = qr_codes[0].data.decode("utf-8")
                print(f"QR Scanned: {user_id}")
                lcd_message("Code Scanned",user_id[:16])

                try:
                    res = requests.post(FLASK_QR_PAYMENT_URL, json ={
                        "user_id": user_id,
                        "price": price
                    })

                    if res.status_code == 200:
                        result = res.json()
                        new_balance = result.get("new_balance",0)
                        lcd_message("Payment OK",f"New: ${new_balance:.2f}")
                        sleep(2)
                        return True
                    else:
                        lcd_message("Payment Failed",res.json().get("error","Unknown"))
                        sleep(2)
                        return False
                
                except Exception as e:
                    print(f"[HTTP] Error: {e}")
                    lcd_message("Server Error","Try Again")
                    sleep(2)
                    return False
            
            rawCapture.truncate(0)
    
    except KeyboardInterrupt:
        pass


def handlePayment(choice):
    drink = drinks[choice]
    price = drink["price"]
    displayPaymentMethod()
    method = selectPaymentMethod()
    if method == '1':
        success = enableRFID()
    elif method == '2':
        success = enableQRpayment(price)
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
    lcd_message("Select Service:", "3.Clear RFID Database")
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
        elif key == '3':
            print("Clearing database...")
            f=open("authlist.txt","r+")
            auth=f.read() #read list of UID's
            num=auth.count('\n') #count how many UID's in list
            for n in range(0, num): #print "Deleted entry #1.. etc
                print("Deleted entry #", n)
            f=open("authlist.txt", "w")
            #this recreates an empty authlist.txt file
            f.close()
            print("Database cleared.")

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



# --- Main ---
if __name__ == "__main__":
    try:
        setup_keypad()
        lcd_message("Starting System", "Please wait...")

        # Background threads
        dht_thread = threading.Thread(target=monitor_system, daemon=True)
        thingspeak_thread = threading.Thread(target=upload_dht_to_thingspeak, daemon=True)
        dht_thread.start()
        thingspeak_thread.start()

        # Main menu
        lcd_message("Welcome!", "Select Option")
        displayMainMenu()
        selectMainMenu()

    except KeyboardInterrupt:
        print("Exiting program...")
    finally:
        camera.close()
        LCD.lcd_clear()
        servo.stop()
        GPIO.cleanup()