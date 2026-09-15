# Telegram Gatekeeper Bot

A Telegram bot that screens people before they can join a private group. Applicants answer a short
questionnaire in a private chat with the bot; if they pass, they receive a **one-time invite link**
that works for a single person only.

## How it works (v2 — automatic approval)

1. The applicant sends `/start` and taps **Verify Yourself**.
2. The bot asks for their **Twitter/X profile URL** and checks that it is a valid `twitter.com` or
   `x.com` profile link, asking again until it is.
3. The bot asks whether they do their own research and only invest what they can afford to lose
   (Yes/No).
4. **Yes** → approved automatically: the bot creates a single-use invite link to the private group and
   sends it. **No** → rejected automatically.
5. Every decision is logged to the **admin group** with the applicant's name, username, user ID,
   profile link, answer, decision and invite link.

v1 (manual review with Approve/Reject buttons) is available as the `v1.0.0` release.

## Join/leave logger (`log/`)

A second, independent bot that watches the groups it is added to and records every member who joins
or leaves: it stores the event in a local SQLite database (`users.db`) and posts a formatted notice
to a log channel. Run it with its own token and `.env` from inside `log/` (`python log.py`); see
`log/envexample`.

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
