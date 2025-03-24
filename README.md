# Line OA Flask Application

This is a Flask application that implements a Line Official Account (OA) bot with SQLite database integration.

## Features

- Line OA message handling
- User management
- Message history storage
- RESTful API endpoints

## Prerequisites

- Python 3.7 or higher
- Line Developer Account
- Line Messaging API Channel

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the root directory with your Line OA credentials:
   ```
   LINE_CHANNEL_ACCESS_TOKEN=your_channel_access_token
   LINE_CHANNEL_SECRET=your_channel_secret
   ```

4. Run the application:
   ```bash
   python app.py
   ```

## API Endpoints

- `POST /callback`: Webhook endpoint for Line OA messages
- `GET /users`: Get all registered users
- `GET /messages/<user_id>`: Get message history for a specific user

## Database Schema

### Users Table
- user_id (TEXT, PRIMARY KEY)
- display_name (TEXT)
- created_at (TIMESTAMP)

### Messages Table
- id (INTEGER, PRIMARY KEY)
- user_id (TEXT, FOREIGN KEY)
- message (TEXT)
- created_at (TIMESTAMP)

## Security Notes

- Keep your `.env` file secure and never commit it to version control
- Use HTTPS in production
- Implement proper authentication for API endpoints in production 