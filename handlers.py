import asyncio
import html
import logging
import time

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from balancers import Registry
from config import Config
from db import DB
from keyboards import results_kb, sources_kb
from kp import Kinopoisk

log = logging.getLogger(__name__)
router = Router()

THROTTLE_SEC = 1.5
_last_hit: dict[int, float] = {}


def throttled(user_id: int) -> bool:
    now = time.monotonic()
    if now - _last_hit.get(user_id, 0) < THROTTLE_SEC:
        return True
    _last_hit[user_id] = now
    return False


@router.message(CommandStart())
async def cmd_start(message: Message, cfg: Config) -> None:
    await message.answer(
        "Пришлите название фильма или сериала — покажу, где посмотреть.\n"
        "Для сериала добавьте сезон: <code>Во все тяжкие s1e1</code>."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer("Поиск по названию. Кнопка «Не работает» убирает мёртвый источник.")


@router.message(F.text & ~F.text.startswith("/"))
async def on_query(
    message: Message, kp: Kinopoisk, db: DB, cfg: Config
) -> None:
    if throttled(message.from_user.id):
        return
    query = message.text.strip()[:120]
    if len(query) < 2:
        await message.answer("Слишком короткий запрос.")
        return

    try:
        found = await kp.search(query)
    except Exception:
        log.exception("поиск не удался")
        await message.answer("Поисковик не ответил, попробуйте через минуту.")
        return

    if not found:
        await message.answer("Ничего не нашлось. Попробуйте оригинальное название.")
        return

    for m in found:
        await db.cache_title(m["kp_id"], m)

    await message.answer(
        f"Нашёл {len(found)} вариант(ов) по запросу «{html.escape(query)}»:",
        reply_markup=results_kb(found),
    )


@router.callback_query(F.data.startswith("card:"))
async def on_card(call: CallbackQuery, db: DB, reg: Registry, cfg: Config) -> None:
    kp_id = int(call.data.split(":", 1)[1])
    title = await db.get_title(kp_id)
    if not title:
        await call.answer("Карточка устарела, поищите заново.", show_alert=True)
        return

    await call.answer("Ищу источники…")

    sources = await db.sources(kp_id)
    if not sources:
        fresh = await reg.by_kp(kp_id)
        if fresh:
            await db.add_sources(kp_id, fresh)
            sources = await db.sources(kp_id)

    caption = (
        f"<b>{html.escape(title['name'])}</b> ({title['year'] or '—'})\n"
        f"рейтинг КП: {title['rating'] or '—'}"
    )
    if title.get("description"):
        caption += f"\n\n{html.escape(title['description'])}"

    if not sources:
        caption += "\n\n<i>Источников нет.</i>"
        await call.message.answer(caption)
        return

    await call.message.answer(caption, reply_markup=sources_kb(sources, cfg.webapp_base))


@router.callback_query(F.data.startswith("refresh:"))
async def on_refresh(call: CallbackQuery, db: DB, reg: Registry, cfg: Config) -> None:
    kp_id = int(call.data.split(":", 1)[1])
    await call.answer("Обновляю…")
    fresh = await reg.by_kp(kp_id)
    if fresh:
        await db.add_sources(kp_id, fresh)
    sources = await db.sources(kp_id)
    if not sources:
        await call.message.answer("Источники не нашлись.")
        return
    await call.message.edit_reply_markup(reply_markup=sources_kb(sources, cfg.webapp_base))


@router.callback_query(F.data.startswith("dead:"))
async def on_dead(call: CallbackQuery, db: DB, cfg: Config) -> None:
    source_id = int(call.data.split(":", 1)[1])
    src = await db.get_source(source_id)
    if not src:
        await call.answer("Источник не найден.", show_alert=True)
        return
    await db.mark_fail(source_id, threshold=3)
    sources = await db.sources(src["kp_id"])
    alive = [s for s in sources if s["id"] != source_id]
    await call.answer("Пометил, спасибо")
    if alive:
        await call.message.edit_reply_markup(reply_markup=sources_kb(alive, cfg.webapp_base))
    else:
        await call.message.answer("Больше источников нет — обновите позже.")