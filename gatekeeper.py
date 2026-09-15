import logging
import re
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, helpers
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

import os
from dotenv import load_dotenv

# Constants and Setup
load_dotenv()
TOKEN = os.getenv("TOKEN")
ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Function to validate Twitter/X.com URL
def is_valid_twitter_url(url):
    return bool(re.match(r"(https?://)?(www\.)?(twitter\.com|x\.com)/[A-Za-z0-9_]+", url, re.IGNORECASE))

# Command handler for /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton("Verify Yourself", callback_data='verify')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Welcome! Please verify yourself to join our group chat.', reply_markup=reply_markup)

# Callback Query Handler for Verification
async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Put your Twitter account URL (LINK)")

    # Change state to expect social media link
    context.user_data['expecting'] = 'social_media'

# Message Handler to collect responses
async def collect_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = context.user_data
    if user_data.get('expecting') == 'social_media':
        social_media_link = update.message.text
        valid_url = is_valid_twitter_url(social_media_link)

        if valid_url:
            user_data['social_media'] = social_media_link
            user_data['expecting'] = 'support_response'
            await update.message.reply_text("Do you always do your own research and invest what you are willing to lose? Please reply with Yes or No.")
        else:
            # Keep the state as 'social_media' and prompt again for a valid URL
            await update.message.reply_text("Invalid Twitter URL. Please provide a valid Twitter profile link.")

    elif user_data.get('expecting') == 'support_response':
        support_response = update.message.text.lower()
        if support_response == 'yes':
            user_data['support_response'] = support_response
            await auto_approve(update, context)  # Call a function to handle auto-approval
        elif support_response == 'no':
            await auto_reject(update, context)  # Call a function to handle auto-rejection
        else:
            await update.message.reply_text("Please reply with Yes or No.")

# Auto-approve function
async def auto_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        chat_invite_link = await context.bot.create_chat_invite_link(chat_id=GROUP_CHAT_ID, member_limit=1)
        invite_link = chat_invite_link.invite_link
        await context.bot.send_message(chat_id=update.message.from_user.id, text=f"Your request has been approved. Here is your invite link: {invite_link}")
        await log_admin_decision(update, context, "Approved", invite_link)  # Log the decision
    except Exception as e:
        logger.error(f"Error generating invite link: {e}")
    finally:
        context.user_data.clear()

# Auto-reject function
async def auto_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(chat_id=update.message.from_user.id, text="Your request has been denied.")
    await log_admin_decision(update, context, "Rejected", None)  # Log the decision
    context.user_data.clear()

# Function to escape Markdown special characters
def escape_markdown(text):
    escape_chars = '_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

# Function to log decision in admin group
async def log_admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE, decision: str, invite_link: str) -> None:
    user_data = context.user_data
    user = update.message.from_user
    user_mention = f"[{escape_markdown(user.first_name)} {escape_markdown(user.last_name) if user.last_name else ''}](tg://user?id={user.id})"
    
    message_to_admin = (
        f"User: {user_mention}\n"
        f"Username: @{escape_markdown(user.username)}\n"
        f"User ID: {user.id}\n"
        f"Social Media: {escape_markdown(user_data.get('social_media', 'N/A'))}\n"
        f"Do Your own research and invest what you are willing to lose? : {escape_markdown(user_data.get('support_response', 'N/A'))}\n"
        f"Decision: {decision}\n"
        f"Invite Link: {escape_markdown(invite_link) if invite_link else 'N/A'}"
    )

    await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=message_to_admin, parse_mode='MarkdownV2')

# Main function to start the bot
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(verify, pattern='^verify$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_info))

    application.run_polling()

if __name__ == '__main__':
    main()
