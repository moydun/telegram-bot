import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

import webapp
from balancers import Collaps, Registry, Videoseed
from config import Config
from db import DB
from handlers import router
from kp import Kinopoisk

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    cfg = Config.from_env()
    db = DB(cfg.db_path)
    await db.connect()

    kp = Kinopoisk(cfg)
    registry = Registry([Videoseed(cfg.videoseed_token), Collaps(cfg.collaps_token)])

    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp["cfg"] = cfg
    dp["db"] = db
    dp["kp"] = kp
    dp["reg"] = registry
    dp.include_router(router)

    app = webapp.build(db)
    SimpleRequestHandler(
        dispatcher=dp, bot=bot, secret_token=cfg.webhook_secret
    ).register(app, path=cfg.webhook_path)

    async def on_startup(_: web.Application) -> None:
        # Render поднимает сервис на случайном порту из $PORT
        await bot.set_webhook(
            f"{cfg.webapp_base}{cfg.webhook_path}",
            secret_token=cfg.webhook_secret,
            drop_pending_updates=True,
            allowed_updates=dp.resolve_used_update_types(),
        )

    async def on_cleanup(_: web.Application) -> None:
        await bot.session.close()
        await registry.close()
        await kp.close()
        await db.close()

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())