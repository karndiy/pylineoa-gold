from flask import Flask, request, jsonify
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration
from linebot.v3.messaging.api_client import ApiClient
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)
from linebot.v3.webhooks.models import Source
from linebot.v3.messaging.models import (
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.messaging.api import MessagingApi
import sqlite3
import os
from datetime import datetime
from dotenv import load_dotenv
from contextlib import contextmanager
import requests

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Line OA Configuration
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
LINE_CHANNEL_ID = os.getenv('LINE_CHANNEL_ID')
LINE_USER_ID = os.getenv('LINE_USER_ID')

# Validate required environment variables
if not all([LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET, LINE_CHANNEL_ID, LINE_USER_ID]):
    raise ValueError("Missing required environment variables. Please check your .env file.")

# Initialize Line Bot API v3
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
api_client = ApiClient(configuration)
messaging_api = MessagingApi(api_client)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

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

# Database connection context manager
@contextmanager
def get_db_connection():
    conn = sqlite3.connect('line_oa.db')
    try:
        yield conn
    finally:
        conn.close()

# Database initialization
def init_db():
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                display_name TEXT,
                created_at TIMESTAMP
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                message TEXT,
                created_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        conn.commit()

# Initialize database
init_db()

def handle_webhook(body, signature):
    """Common webhook handling logic for both /callback and /webhook endpoints"""
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return jsonify({"error": "Invalid signature"}), 400
    except Exception as e:
        print(f"Error handling webhook: {e}")
        return jsonify({"error": "Internal server error"}), 500
    return jsonify({"message": "OK"})

@app.route("/callback", methods=['POST'])
def callback():
    """Handle LINE webhook events at /callback endpoint"""
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    return handle_webhook(body, signature)

@app.route("/webhook", methods=['POST'])
def webhook():
    """Handle LINE webhook events at /webhook endpoint"""
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        return jsonify({"error": "Missing X-Line-Signature header"}), 400
    
    body = request.get_data(as_text=True)
    return handle_webhook(body, signature)

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    try:
        # Get user ID based on source type
        source = event.source
        if source.type == "user":
            user_id = source.user_id
        elif source.type == "group":
            user_id = source.group_id
        elif source.type == "room":
            user_id = source.room_id
        else:
            return

        message_text = event.message.text.lower()
        
        # Store user and message in database
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Check if user exists
            c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user = c.fetchone()
            
            if not user:
                try:
                    # Get user profile (only for user messages)
                    if source.type == "user":
                        profile = messaging_api.get_profile(user_id)
                        display_name = profile.display_name
                    else:
                        display_name = f"{source.type.capitalize()} {user_id}"
                        
                    c.execute('INSERT INTO users (user_id, display_name, created_at) VALUES (?, ?, ?)',
                             (user_id, display_name, datetime.now()))
                except Exception as e:
                    print(f"Error getting profile: {e}")
                    display_name = f"User {user_id}"
            
            # Store message
            c.execute('INSERT INTO messages (user_id, message, created_at) VALUES (?, ?, ?)',
                     (user_id, message_text, datetime.now()))
            
            conn.commit()
        
        # Handle gold price request
        if "gold" in message_text or "ทอง" in message_text:
            gold_data = get_gold_price()
            reply_text = format_gold_message(gold_data)
        else:
            reply_text = f"ได้รับข้อความ: {message_text}"
        
        # Send reply
        reply_message_request = ReplyMessageRequest(
            reply_token=event.reply_token,
            messages=[TextMessage(text=reply_text)]
        )
        messaging_api.reply_message(reply_message_request)
    except Exception as e:
        print(f"Error handling message: {e}")
        # Try to send error message to user
        try:
            error_message = ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="ขออภัย เกิดข้อผิดพลาดในการประมวลผลข้อความ")]
            )
            messaging_api.reply_message(error_message)
        except:
            pass

@app.route("/users", methods=['GET'])
def get_users():
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM users')
            users = c.fetchall()
            
            return jsonify([{
                "user_id": user[0],
                "display_name": user[1],
                "created_at": user[2]
            } for user in users])
    except Exception as e:
        print(f"Error getting users: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/messages/<user_id>", methods=['GET'])
def get_user_messages(user_id):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM messages WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
            messages = c.fetchall()
            
            return jsonify([{
                "id": msg[0],
                "user_id": msg[1],
                "message": msg[2],
                "created_at": msg[3]
            } for msg in messages])
    except Exception as e:
        print(f"Error getting messages: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route("/info", methods=['GET'])
def get_bot_info():
    return jsonify({
        "channel_id": LINE_CHANNEL_ID,
        "user_id": LINE_USER_ID,
        "status": "active",
        "webhook_endpoints": ["/callback", "/webhook"]
    })

@app.route("/")
def index():
    return "Hello World"

if __name__ == "__main__":
    app.run(debug=True, port=5000)
