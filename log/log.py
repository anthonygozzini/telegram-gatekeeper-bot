import os
import datetime
import sqlite3
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, CallbackContext
import logging

# Constants and Setup
load_dotenv()
TOKEN = os.getenv("TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Initialize the global variable for last check time
last_check_time = datetime.datetime.min

# Configure logging
def setup_logging():
    logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)

# Database operations
class Database:
    def __init__(self, db_path):
        self.db_path = db_path

    def execute_query(self, query, parameters=(), fetch=False):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, parameters)
            if fetch:
                return cursor.fetchall()
            conn.commit()

    def initialize(self):
        self.execute_query('''CREATE TABLE IF NOT EXISTS user_activity (
                              id INTEGER PRIMARY KEY AUTOINCREMENT,
                              user_id INTEGER,
                              username TEXT,
                              first_name TEXT,
                              last_name TEXT,
                              action TEXT,
                              group_name TEXT,
                              group_username TEXT,
                              timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')

# Utility functions
def escape_markdown(text):
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

def generate_user_info(member, action, group_name, group_username):
    member_mention = f"[{escape_markdown(member.first_name)} {escape_markdown(member.last_name) if member.last_name else ''}](tg://user?id={member.id})"
    return (
        f"{action}\n"
        f"Group: {group_name} @{escape_markdown(group_username)}\n"
        f"User: {member_mention}\n"
        f"Username: @{escape_markdown(member.username)}\n"
        f"UserID: {member.id}\n"
    )

# User update handler
async def handle_user_update(db, member, action, group_name, group_username, context):
    user_info = generate_user_info(member, action, group_name, group_username)
    user_data = (member.id, member.username, member.first_name, member.last_name, action, group_name, group_username)
    db.execute_query('''INSERT INTO user_activity 
                        (user_id, username, first_name, last_name, action, group_name, group_username) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)''', user_data)
    await context.bot.send_message(chat_id=CHANNEL_ID, text=user_info, parse_mode='MarkdownV2')

# Message handler for user status updates
async def user_status_update(update: Update, context: CallbackContext, action):
    group_name = update.message.chat.title
    group_username = update.message.chat.username
    member = update.message.new_chat_members[0] if action == "📥 User Joined" else update.message.left_chat_member
    await handle_user_update(db, member, action, group_name, group_username, context)

# Main function to start the bot
def main():
    global db
    setup_logging()
    db = Database('users.db')
    db.initialize()

    application = Application.builder().token(TOKEN).build()

    # Configure MessageHandlers
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, lambda u, c: user_status_update(u, c, "📥 User Joined")))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, lambda u, c: user_status_update(u, c, "📤 User Left")))
    
    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
