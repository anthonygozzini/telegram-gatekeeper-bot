# Telegram Gatekeeper Bot

A Telegram bot that screens people before they can join a private group. Applicants answer a short
questionnaire in a private chat with the bot; if they pass, they receive a **one-time invite link**
that works for a single person only.

## How it works (v1 — manual review)

1. The applicant sends `/start` and taps **Verify Yourself**.
2. The bot asks for their main social media account, then asks whether they support the projects
   they join (Yes/No).
3. The answers are posted to a private **admin group** with **Approve** / **Reject** buttons.
4. On approval the bot creates a single-use invite link to the private group and sends it to the
   applicant; on rejection it tells them the request was denied. The admin message is updated with
   the decision.

## Setup

```sh
git clone https://github.com/anthonygozzini/telegram-gatekeeper-bot.git
cd telegram-gatekeeper-bot
pip install -r requirements.txt
cp envexample .env   # then fill in the values
python gatekeeper.py
```

The bot must be an administrator of the private group (to create invite links) and a member of the
admin group.

| Variable | Meaning |
|---|---|
| `TOKEN` | Bot token from @BotFather |
| `ADMIN_GROUP_ID` | Chat ID of the group where admins review applications |
| `GROUP_CHAT_ID` | Chat ID of the private group applicants are admitted to |

## License

MIT
