import asyncio
import sqlite3

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

TOKEN = ""        # from @BotFather
CHANNEL_ID = -1000000000000    # your private channel's ID

db = sqlite3.connect("posts.db")
db.execute(
    "CREATE TABLE IF NOT EXISTS posts (message_id INTEGER PRIMARY KEY, name TEXT)"
)

bot = Bot(TOKEN)
dp = Dispatcher()


@dp.channel_post(F.chat.id == CHANNEL_ID)
async def index_post(m: Message):
    """Save the file name (or caption) of every new channel post."""
    name = m.document.file_name if m.document else (m.caption or "")
    if name:
        db.execute(
            "INSERT OR REPLACE INTO posts VALUES (?, ?)",
            (m.message_id, name.lower()),
        )
        db.commit()


@dp.message(CommandStart())
async def start(m: Message):
    await m.answer("Send /search <name> to get a file, e.g. /search vale")


@dp.message(Command("search"))
async def search(m: Message, command: CommandObject):
    q = (command.args or "").strip().lower()
    if not q:
        return await m.answer("Usage: /search <name>")

    rows = db.execute(
        "SELECT message_id FROM posts WHERE name LIKE ? LIMIT 5", (f"%{q}%",)
    ).fetchall()
    if not rows:
        return await m.answer("Nothing found")

    for (message_id,) in rows:
        await bot.copy_message(m.chat.id, CHANNEL_ID, message_id)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
