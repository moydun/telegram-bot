# Telegram Channel Search Bot

A bot that finds files in a private Telegram channel by name. A user sends
`/search "filename"` and the bot sends back the post with `filename.jpg`.

## How it works

1. The bot is an admin of your channel and receives every new post.
2. For each post it saves the file name (or caption) and the message ID
   in a local SQLite database (`posts.db`).
3. On `/search <name>` it looks the name up and copies the matching
   post(s) to the user.

Telegram bots cannot read channel history, so only posts made **after**
the bot was added are indexed.

## Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and copy the token.
2. Add the bot to your private channel as an **admin**.
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Open `bot.py` and set:

   - `TOKEN` - your bot token
   - `CHANNEL_ID` - your channel ID (starts with `-100`)

   To find the channel ID, temporarily add `print(m.chat.id)` to
   `index_post`, run the bot, and publish any post in the channel.

5. Run the bot:

   ```bash
   python bot.py
   ```

## Usage

- Upload files to the channel **as File (document)**, not as Photo.
  Photos lose their file name, so `filename.jpg` would not be found.
  (If you must post a photo, put the name in the caption.)
- In a chat with the bot, send:

  ```
  /search filename
  ```

  Search is partial and case-insensitive, and returns up to 5 matches.

## Notes

- Keep the bot running while you upload. If it is offline for more than
  about 24 hours, Telegram drops the missed updates and those files are
  never indexed.
- Do not delete `posts.db`. It is the only record of which file is which
  message.
- Anyone who finds the bot can search and receive files from the channel.
- If the channel has "Restrict saving content" enabled, copying will fail.
  Store `m.document.file_id` instead and send it with `bot.send_document`.
