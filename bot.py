from __future__ import annotations

import argparse
import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from telethon import TelegramClient

from search_state import PageStore, SlidingWindowRateLimiter


LOGGER = logging.getLogger("telegram_post_search")
PAGE_SIZE = 5
MAX_QUERY_LENGTH = 128


@dataclass(frozen=True)
class Config:
    bot_token: str
    api_id: int
    api_hash: str
    source_channel: str | int
    session_path: Path
    allowed_user_ids: frozenset[int]
    search_limit: int
    rate_limit: int
    rate_window_seconds: int


def load_config() -> Config:
    load_dotenv()

    required = ("BOT_TOKEN", "TELEGRAM_API_ID", "TELEGRAM_API_HASH", "SOURCE_CHANNEL")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise ValueError(f"Missing required environment values: {', '.join(missing)}")

    raw_source = os.environ["SOURCE_CHANNEL"].strip()
    source_channel: str | int = (
        int(raw_source) if raw_source.lstrip("-").isdigit() else raw_source
    )
    try:
        allowed_user_ids = frozenset(
            int(value.strip())
            for value in os.getenv("ALLOWED_USER_IDS", "").split(",")
            if value.strip()
        )
        search_limit = int(os.getenv("SEARCH_LIMIT", "100"))
        rate_limit = int(os.getenv("RATE_LIMIT", "5"))
        rate_window_seconds = int(os.getenv("RATE_WINDOW_SECONDS", "60"))
        api_id = int(os.environ["TELEGRAM_API_ID"])
    except ValueError as exc:
        raise ValueError("Telegram IDs and limits must be valid integers") from exc

    if not 1 <= search_limit <= 500:
        raise ValueError("SEARCH_LIMIT must be between 1 and 500")
    if rate_limit < 1 or rate_window_seconds < 1:
        raise ValueError("RATE_LIMIT and RATE_WINDOW_SECONDS must be positive")

    session_path = Path(os.getenv("READER_SESSION", ".secrets/reader"))
    session_path.parent.mkdir(parents=True, exist_ok=True)

    return Config(
        bot_token=os.environ["BOT_TOKEN"],
        api_id=api_id,
        api_hash=os.environ["TELEGRAM_API_HASH"],
        source_channel=source_channel,
        session_path=session_path,
        allowed_user_ids=allowed_user_ids,
        search_limit=search_limit,
        rate_limit=rate_limit,
        rate_window_seconds=rate_window_seconds,
    )


def is_authorized(user_id: int, allowed_user_ids: frozenset[int]) -> bool:
    return not allowed_user_ids or user_id in allowed_user_ids


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "Send /search followed by a word or phrase to search the configured channel."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message:
        await update.message.reply_text(
            "/search <query> - find matching channel posts\n"
            "Results are sent by the connected reader account, five at a time."
        )


def _message_link(source: Any, message_id: int) -> str | None:
    username = getattr(source, "username", None)
    if username:
        return f"https://t.me/{username}/{message_id}"

    source_id = getattr(source, "id", None)
    if source_id:
        return f"https://t.me/c/{source_id}/{message_id}"
    return None


async def _deliver_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
) -> None:
    page_store: PageStore = context.application.bot_data["page_store"]
    page_ids = page_store.next_page(user_id)
    if not page_ids:
        await context.bot.send_message(chat_id=user_id, text="There are no more results.")
        return

    reader: TelegramClient = context.application.bot_data["reader"]
    source = context.application.bot_data["source"]
    sent_count = 0
    for message_id in page_ids:
        try:
            await reader.forward_messages(entity=user_id, messages=message_id)
            sent_count += 1
        except Exception as exc:
            LOGGER.info("Forward unavailable; using link fallback (%s)", type(exc).__name__)
            link = _message_link(source, message_id)
            if link:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"This post could not be forwarded. Open it in Telegram: {link}",
                    disable_web_page_preview=True,
                )

    more_available = page_store.has_more(user_id)
    keyboard = (
        InlineKeyboardMarkup([[InlineKeyboardButton("More", callback_data="more")]])
        if more_available
        else None
    )
    if sent_count:
        status = f"Sent {sent_count} matching post(s)."
    else:
        status = "No posts could be forwarded. Links were sent when available."
    await context.bot.send_message(chat_id=user_id, text=status, reply_markup=keyboard)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if not user or not chat or not update.message:
        return
    if chat.type != "private":
        await update.message.reply_text("Please use this command in a private chat with the bot.")
        return

    config: Config = context.application.bot_data["config"]
    if not is_authorized(user.id, config.allowed_user_ids):
        await update.message.reply_text("You are not allowed to search this channel.")
        return

    limiter: SlidingWindowRateLimiter = context.application.bot_data["rate_limiter"]
    if not limiter.allow(user.id):
        await update.message.reply_text("Search limit reached. Please try again in a minute.")
        return

    query = " ".join(context.args).strip()
    if not query:
        await update.message.reply_text("Usage: /search <word or phrase>")
        return
    if len(query) > MAX_QUERY_LENGTH:
        await update.message.reply_text(
            f"Search text must be {MAX_QUERY_LENGTH} characters or fewer."
        )
        return

    await update.message.reply_text("Searching the configured channel...")
    reader: TelegramClient = context.application.bot_data["reader"]
    source = context.application.bot_data["source"]
    try:
        message_ids = [
            message.id
            async for message in reader.iter_messages(
                source,
                search=query,
                limit=config.search_limit,
            )
        ]
    except Exception as exc:
        LOGGER.exception("Channel search failed (%s)", type(exc).__name__)
        await context.bot.send_message(
            chat_id=user.id,
            text="Search failed. Check that the reader account can access the configured channel.",
        )
        return

    page_store: PageStore = context.application.bot_data["page_store"]
    page_store.set_results(user.id, message_ids)
    if not message_ids:
        await context.bot.send_message(chat_id=user.id, text="No matching posts found.")
        return
    await _deliver_page(update, context, user.id)


async def more_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    callback = update.callback_query
    chat = update.effective_chat
    if not callback or not chat:
        return
    await callback.answer()
    if chat.type != "private" or callback.from_user.id != chat.id:
        return

    config: Config = context.application.bot_data["config"]
    if not is_authorized(callback.from_user.id, config.allowed_user_ids):
        await callback.edit_message_text("You are not allowed to search this channel.")
        return
    await _deliver_page(update, context, callback.from_user.id)


async def authenticate_reader(config: Config) -> None:
    reader = TelegramClient(config.session_path, config.api_id, config.api_hash)
    try:
        await reader.start()
        print("Reader account authenticated. Session stored locally; keep it private.")
    finally:
        await reader.disconnect()


async def run_bot(config: Config) -> None:
    reader = TelegramClient(config.session_path, config.api_id, config.api_hash)
    await reader.connect()
    if not await reader.is_user_authorized():
        await reader.disconnect()
        raise RuntimeError("Reader account is not signed in. Run `python bot.py --login` first.")

    try:
        source = await reader.get_entity(config.source_channel)
        application: Application = ApplicationBuilder().token(config.bot_token).build()
        application.bot_data.update(
            {
                "config": config,
                "reader": reader,
                "source": source,
                "page_store": PageStore(ttl_seconds=600),
                "rate_limiter": SlidingWindowRateLimiter(
                    limit=config.rate_limit,
                    window_seconds=config.rate_window_seconds,
                ),
            }
        )
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("search", search_command))
        application.add_handler(CallbackQueryHandler(more_callback, pattern="^more$"))

        await application.initialize()
        await application.start()
        if application.updater is None:
            raise RuntimeError("Polling updater is not available")
        await application.updater.start_polling()
        LOGGER.info("Bot is running")
        try:
            await asyncio.Event().wait()
        finally:
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
    finally:
        await reader.disconnect()


def main() -> None:
    parser = argparse.ArgumentParser(description="Search and deliver Telegram channel posts")
    parser.add_argument(
        "--login",
        action="store_true",
        help="sign in the reader account and save its local Telethon session",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        config = load_config()
        if args.login:
            asyncio.run(authenticate_reader(config))
        else:
            asyncio.run(run_bot(config))
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        LOGGER.info("Bot stopped")


if __name__ == "__main__":
    main()