import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str
    kp_api_key: str
    videoseed_token: str
    collaps_token: str
    webapp_base: str
    db_path: str
    webhook_secret: str
    webhook_path: str

    @classmethod
    def from_env(cls) -> "Config":
        missing = [
            k for k in ("BOT_TOKEN", "KP_API_KEY")
            if not os.getenv(k)
        ]
        if not (os.getenv("WEBAPP_BASE") or os.getenv("RENDER_EXTERNAL_URL")):
            missing.append("WEBAPP_BASE or RENDER_EXTERNAL_URL")
        if not os.getenv("WEBHOOK_SECRET"):
            missing.append("WEBHOOK_SECRET")
        if missing:
            raise SystemExit(f"Не заданы переменные: {', '.join(missing)}")
        return cls(
            bot_token=os.environ["BOT_TOKEN"],
            kp_api_key=os.environ["KP_API_KEY"],
            videoseed_token=os.getenv("VIDEOSEED_TOKEN", ""),
            collaps_token=os.getenv("COLLAPS_TOKEN", ""),
            webapp_base=(os.getenv("WEBAPP_BASE") or os.environ["RENDER_EXTERNAL_URL"]).rstrip("/"),
            db_path=os.getenv("DB_PATH", "data/catalog.sqlite3"),
            webhook_secret=os.getenv("WEBHOOK_SECRET", ""),
            webhook_path=f"/webhook/{os.getenv('WEBHOOK_SECRET', '')}",
        )