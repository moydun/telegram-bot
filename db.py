import json
import time
from pathlib import Path

import aiosqlite

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS titles (
    kp_id      INTEGER PRIMARY KEY,
    payload    TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kp_id       INTEGER NOT NULL,
    provider    TEXT NOT NULL,
    url         TEXT NOT NULL,
    translation TEXT,
    quality     TEXT,
    ok          INTEGER NOT NULL DEFAULT 1,
    fails       INTEGER NOT NULL DEFAULT 0,
    last_check  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (provider, url)
);
CREATE INDEX IF NOT EXISTS idx_sources_kp ON sources (kp_id, ok, fails);
"""


class DB:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    async def cache_title(self, kp_id: int, payload: dict) -> None:
        await self._conn.execute(
            "INSERT INTO titles (kp_id, payload, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT (kp_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
            (kp_id, json.dumps(payload, ensure_ascii=False), int(time.time())),
        )
        await self._conn.commit()

    async def get_title(self, kp_id: int) -> dict | None:
        cur = await self._conn.execute("SELECT payload FROM titles WHERE kp_id = ?", (kp_id,))
        row = await cur.fetchone()
        return json.loads(row["payload"]) if row else None

    async def add_sources(self, kp_id: int, items: list[dict]) -> None:
        await self._conn.executemany(
            "INSERT OR IGNORE INTO sources (kp_id, provider, url, translation, quality) "
            "VALUES (?, ?, ?, ?, ?)",
            [(kp_id, i["provider"], i["url"], i.get("translation"), i.get("quality")) for i in items],
        )
        await self._conn.commit()

    async def sources(self, kp_id: int, limit: int = 8) -> list[aiosqlite.Row]:
        cur = await self._conn.execute(
            "SELECT * FROM sources WHERE kp_id = ? ORDER BY ok DESC, fails ASC, id ASC LIMIT ?",
            (kp_id, limit),
        )
        return list(await cur.fetchall())

    async def get_source(self, source_id: int) -> aiosqlite.Row | None:
        cur = await self._conn.execute("SELECT * FROM sources WHERE id = ?", (source_id,))
        return await cur.fetchone()

    async def mark_fail(self, source_id: int, threshold: int = 2) -> None:
        await self._conn.execute(
            "UPDATE sources SET fails = fails + 1, "
            "ok = CASE WHEN fails + 1 >= ? THEN 0 ELSE ok END, last_check = ? WHERE id = ?",
            (threshold, int(time.time()), source_id),
        )
        await self._conn.commit()

    async def mark_ok(self, source_id: int) -> None:
        await self._conn.execute(
            "UPDATE sources SET ok = 1, fails = 0, last_check = ? WHERE id = ?",
            (int(time.time()), source_id),
        )
        await self._conn.commit()