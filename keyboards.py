from aiogram.types import InlineKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder


def results_kb(items: list[dict]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i, m in enumerate(items):
        label = f"{m['name']} ({m['year'] or '—'})"[:60]
        kb.button(text=label, callback_data=f"card:{m['kp_id']}")
    kb.adjust(1)
    return kb.as_markup()


def sources_kb(sources, base_url: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in sources:
        tag = " / ".join(filter(None, [s["translation"], s["quality"]])) or s["provider"]
        kb.button(
            text=f"▶ {tag}"[:60],
            web_app=WebAppInfo(url=f"{base_url}/play/{s['id']}"),
        )
    kb.button(text="🔄 Обновить источники", callback_data=f"refresh:{sources[0]['kp_id']}")
    kb.button(text="⚠️ Не работает", callback_data=f"dead:{sources[0]['id']}")
    kb.adjust(1)
    return kb.as_markup()