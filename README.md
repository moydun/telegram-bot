# Telegram Post Search & Delivery

A small bot that searches one configured channel on demand and forwards matching posts through a separately authenticated Telegram user account. It does not store a post database; only message IDs for the current result page are held in memory for up to ten minutes.

## Requirements

- Python 3.10 or newer
- A bot token from BotFather
- Telegram API ID and hash from https://my.telegram.org
- A Telegram reader account that can access the source channel

## Setup

1. Create and activate a local environment: `python3 -m venv .venv` then `source .venv/bin/activate`.
2. Install dependencies: `python -m pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set `BOT_TOKEN`, `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, and `SOURCE_CHANNEL`.
4. Optionally set `ALLOWED_USER_IDS` to comma-separated Telegram user IDs. Leaving it empty allows any user who can start a private chat with the bot to search the channel.
5. Sign in the reader account: `python bot.py --login`. Enter its phone number, Telegram login code, and 2FA password if requested. This creates a local Telethon session under `.secrets/`.
6. Start the bot: `python bot.py`.

Keep `.env` and `.secrets/` private. A logged-in reader session can access the reader account and must not be shared or committed.

## Commands

- `/start` and `/help` show basic instructions.
- `/search <query>` searches the configured channel and delivers up to five posts.
- Select **More** to receive the next page. Search references expire after ten minutes or when a new search replaces them.

Forwarding is performed by the reader account, not the bot. If Telegram blocks forwarding for a post, the bot sends a channel link when one can be constructed. Users who can access the bot can search and receive matching channel content, so configure an allowlist when that is not intended.

## Checks

Run the local state tests with `python -m unittest discover -s tests`.