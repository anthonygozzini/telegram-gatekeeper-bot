# Telegram Gatekeeper Bot

A Telegram bot that screens people before they join a private group. Applicants answer a short
questionnaire in a private chat; the bot checks the answers, looks for signs of fake or farmed
accounts, and either admits them with a **single-use invite link** or passes the request to your
admins.

Everything the applicant sees — questions, rules, messages — is set in one `config.toml` file, so the
same bot works for any community without touching the code.

## What it checks

- **Answers.** Three question types: a link to a social profile (X, Instagram, TikTok, YouTube,
  GitHub, LinkedIn — the bot checks it is a real profile link, not just any URL), a yes/no question
  that can be required for approval, and free text with a minimum length.
- **Signals of fake or farmed accounts.** No Telegram username; a username full of digits; a name
  that contains words you choose (for example "admin", "support", "airdrop"); a social profile
  already used by another applicant. A signal never rejects anyone by itself: it sends the request to
  a human.
- **Re-applications.** The same person cannot apply again until a cooldown has passed.

## How decisions are made

- **`mode = "auto"`** — approved automatically when every required answer is right and there are no
  signals; rejected automatically when a required answer is wrong; anything with a signal goes to the
  admins.
- **`mode = "manual"`** — every request goes to the admins.

Admins get each request in their group with the answers, clickable profile links and any signals, plus
**Approve** / **Reject** buttons. Every decision, automatic or not, is posted there and stored in a
local SQLite database. Invite links work for one person and can expire after a set number of hours.

Optionally, the bot also posts every **join and leave** of the private group to a log channel.

## Setup

Requires Python 3.11 or newer.

```sh
git clone https://github.com/anthonygozzini/telegram-gatekeeper-bot.git
cd telegram-gatekeeper-bot
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp envexample .env                   # bot token and chat IDs
cp config.example.toml config.toml   # questions, rules and messages
python -m gatekeeper
```

In Telegram, the bot must be an **administrator of the private group** (to create invite links and see
joins and leaves), a member of the **admin group**, and — if you use it — an administrator of the log
channel.

| Variable | Meaning |
|---|---|
| `TOKEN` | Bot token from @BotFather |
| `ADMIN_GROUP_ID` | Group where admins receive requests and decisions |
| `GROUP_CHAT_ID` | The private group people are admitted to |
| `LOG_CHANNEL_ID` | Optional: channel for joins and leaves |
| `DATABASE_PATH`, `CONFIG_PATH` | Optional: where the database and the config file live |

## Development

```sh
pip install -r requirements-dev.txt
./check
```

`./check` compiles everything, runs the tests (rules, configuration, storage, the Telegram calls the
bot makes) and fails if a bot token or a real chat ID ends up in a tracked file.

The rules and the storage are covered by tests; the Telegram flow itself has not yet been run against a
live group.

## Versions

- **v1.0.0** — questionnaire with manual review.
- **v2.0.0** — automatic approval with a Twitter/X profile check, decision log, separate join/leave
  logger.
- **v3.0.0** — one configurable bot: questions and rules in `config.toml`, six social platforms,
  anti-farm signals, auto or manual mode, SQLite history, join/leave logging built in.

## License

MIT
