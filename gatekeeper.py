import logging
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
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

# Command handler for /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [[InlineKeyboardButton("Verify Yourself", callback_data='verify')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Welcome! Please verify yourself to join our group chat.', reply_markup=reply_markup)

# Callback Query Handler for Verification
async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Please post your social media account with most followers (Can be more than one):")

    # Change state to expect social media link
    context.user_data['expecting'] = 'social_media'

# Message Handler to collect responses
async def collect_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = context.user_data
    if user_data.get('expecting') == 'social_media':
        social_media_link = update.message.text
        user_data['social_media'] = social_media_link
        await update.message.reply_text("Do you support projects and care about their success? Reply with Yes or No.")

        # Change state to expect yes/no answer
        user_data['expecting'] = 'support_response'

    elif user_data.get('expecting') == 'support_response':
        support_response = update.message.text.lower()
        if support_response in ['yes', 'no']:
            user_data['support_response'] = support_response
            await update.message.reply_text("Please wait up to 24 hours for a reply. Your request will be manually reviewed.")

            # Send details to admin group with 'await'
            message_to_admin = (
                f"User @{update.message.from_user.username} ({update.message.from_user.id})\n"
                f"Social Media: {user_data['social_media']}\n"
                f"Supports projects: {user_data['support_response']}"
            )
            keyboard = [
                [InlineKeyboardButton("Approve", callback_data=f"approve_{update.message.from_user.id}"),
                InlineKeyboardButton("Reject", callback_data=f"reject_{update.message.from_user.id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=message_to_admin, reply_markup=reply_markup)

            # Clear user data
            context.user_data.clear()
        else:
            await update.message.reply_text("Please reply with Yes or No.")

async def handle_admin_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = int(query.data.split('_')[1])
    decision = query.data.split('_')[0]

    if decision == 'approve':
        try:
            # Generate a one-time use invite link
            chat_invite_link = await context.bot.create_chat_invite_link(chat_id=GROUP_CHAT_ID, member_limit=1)
            invite_link = chat_invite_link.invite_link
            await context.bot.send_message(chat_id=user_id, text=f"Your request has been approved. Here is your invite link: {invite_link}")
        except Exception as e:
            logger.error(f"Error generating invite link: {e}")
            # Handle error

    elif decision == 'reject':
        await context.bot.send_message(chat_id=user_id, text="Your request has been denied.")

    # Update the message in the admin chat to reflect the decision
    await query.edit_message_text(text=f"{query.message.text}\n\nDecision: {decision.title()}")

# Main function to start the bot
def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(verify, pattern='^verify$'))
    application.add_handler(CallbackQueryHandler(handle_admin_decision, pattern=r'^(approve|reject)_\d+$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, collect_info))

    application.run_polling()

if __name__ == '__main__':
    main()