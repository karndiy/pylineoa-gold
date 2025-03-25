import requests
import schedule
import time
from flask import Flask, request, jsonify
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv
import os
from datetime import datetime
import threading

# Load environment variables
load_dotenv()

# Flask app
app = Flask(__name__)

# Line OA Configuration
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ID = os.getenv('LINE_CHANNEL_ID')
LINE_USER_ID = os.getenv('LINE_USER_ID')

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# Global variables for price tracking
last_price = None
subscribers = set()

def get_gold_price():
    """Fetch and format gold price data"""
    url = "https://karndiy.pythonanywhere.com/goldjsonv2"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                latest = data[0]
                return {
                    "asdate": latest["asdate"],
                    "blbuy": latest["blbuy"],
                    "blsell": latest["blsell"],
                    "diff": latest["diff"]
                }
    except Exception as e:
        print(f"Error fetching gold price: {e}")
    return None

def format_gold_message(gold_data):
    """Format gold price data into a readable message"""
    if not gold_data:
        return "ไม่สามารถดึงข้อมูลราคาทองได้ในขณะนี้"
    
    message = (
        f"ราคาทองคำล่าสุด\n"
        f"วันที่: {gold_data['asdate']}\n"
        f"ราคารับซื้อ: {gold_data['blbuy']} บาท\n"
        f"ราคาขาย: {gold_data['blsell']} บาท\n"
        f"ส่วนต่าง: {gold_data['diff']} บาท"
    )
    return message

def check_price_changes():
    """Check for gold price changes and notify subscribers"""
    global last_price
    
    current_price = get_gold_price()
    if current_price and last_price:
        # Check if price has changed
        if (current_price['blbuy'] != last_price['blbuy'] or 
            current_price['blsell'] != last_price['blsell']):
            
            # Calculate price changes
            buy_change = current_price['blbuy'] - last_price['blbuy']
            sell_change = current_price['blsell'] - last_price['blsell']
            
            # Format change message
            change_message = (
                f"🔔 แจ้งเตือนการเปลี่ยนแปลงราคาทอง\n"
                f"ราคารับซื้อ: {current_price['blbuy']} บาท "
                f"({'+' if buy_change > 0 else ''}{buy_change} บาท)\n"
                f"ราคาขาย: {current_price['blsell']} บาท "
                f"({'+' if sell_change > 0 else ''}{sell_change} บาท)\n"
                f"อัพเดทเมื่อ: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            # Notify all subscribers
            for user_id in subscribers:
                try:
                    line_bot_api.push_message(user_id, TextSendMessage(text=change_message))
                except Exception as e:
                    print(f"Error sending notification to {user_id}: {e}")
    
    last_price = current_price

def run_schedule():
    """Run the scheduler in a separate thread"""
    while True:
        schedule.run_pending()
        time.sleep(1)


# Webhook Route
@app.route("/")
def index():
    return "Hello, World!"

# Webhook Route
@app.route("/webhook", methods=['POST'])
def webhook():
    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400

    return "OK", 200

# Handle Incoming Messages
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_message = event.message.text.lower()
    user_id = event.source.user_id

    if "gold" in user_message or "ทอง" in user_message:
        gold_data = get_gold_price()
        reply_text = format_gold_message(gold_data)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
        
        # Add user to subscribers
        subscribers.add(user_id)
        line_bot_api.push_message(user_id, TextSendMessage(
            text="คุณได้ลงทะเบียนรับการแจ้งเตือนราคาทองแล้ว\n"
                 "ระบบจะแจ้งเตือนเมื่อมีการเปลี่ยนแปลงราคา"
        ))
    elif "ยกเลิก" in user_message or "unsubscribe" in user_message:
        if user_id in subscribers:
            subscribers.remove(user_id)
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text="คุณได้ยกเลิกการรับการแจ้งเตือนราคาทองแล้ว"
            ))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(
                text="คุณยังไม่ได้ลงทะเบียนรับการแจ้งเตือนราคาทอง"
            ))
    else:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"ได้รับข้อความ: {user_message}"))

# Start Flask app
if __name__ == "__main__":
    # Initialize last price
    last_price = get_gold_price()
    
    # Schedule price check every 5 minutes
    schedule.every(5).minutes.do(check_price_changes)
    
    # Start scheduler in a separate thread
    scheduler_thread = threading.Thread(target=run_schedule)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Start Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)
