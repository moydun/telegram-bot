import asyncio
import logging
from abc import ABC, abstractmethod

import httpx

log = logging.getLogger(__name__)

_KEY_HINTS = ("iframe", "url", "src")


class Balancer(ABC):
    name: str
    enabled: bool = False

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=4.0))

    async def close(self) -> None:
        await self._client.aclose()

    @abstractmethod
    async def by_kp(self, kp_id: int) -> list[dict]: ...

    def _extract(self, node, out: list[dict]) -> None:
        """Защитный обход ответа: собираем любые iframe/url + озвучку/качество."""
        if isinstance(node, list):
            for x in node:
                self._extract(x, out)
            return
        if not isinstance(node, dict):
            return
        url = next((node[k] for k in _KEY_HINTS if isinstance(node.get(k), str)
                    and node[k].startswith("http")), None)
        if url:
            out.append({
                "provider": self.name,
                "url": url,
                "translation": node.get("translation") or node.get("voiceover"),
                "quality": str(node.get("quality") or node.get("max_quality") or ""),
            })
        for v in node.values():
            if isinstance(v, (list, dict)):
                self._extract(v, out)


class Videoseed(Balancer):
    name = "videoseed"

    def __init__(self, token: str) -> None:
        super().__init__()
        self.token = token
        self.enabled = bool(token)

    async def by_kp(self, kp_id: int) -> list[dict]:
        r = await self._client.get(
            "https://api.videoseed.ru/api/videos",
            params={"token": self.token, "kp_id": kp_id},
        )
        r.raise_for_status()
        out: list[dict] = []
        self._extract(r.json(), out)
        # сезон/серия подставляются прямо в URL плеера
        return out


class Collaps(Balancer):
    name = "collaps"

    def __init__(self, token: str) -> None:
        super().__init__()
        self.token = token
        self.enabled = bool(token)

    async def by_kp(self, kp_id: int) -> list[dict]:
        r = await self._client.get(
            "https://api.bhcesh.me/list",
            params={"token": self.token, "kinopoisk_id": kp_id},
        )
        r.raise_for_status()
        out: list[dict] = []
        for item in r.json().get("results", []):
            if not item.get("iframe_url"):
                continue
            out.append({
                "provider": self.name,
                "url": item["iframe_url"],
                "translation": item.get("translation"),
                "quality": str(item.get("quality") or ""),
            })
        return out


class Registry:
    """Опрос всех включённых балансеров разом, ошибки одного не роняют выдачу."""

    def __init__(self, balancers: list[Balancer]) -> None:
        self._items = [b for b in balancers if b.enabled]

    def __bool__(self) -> bool:
        return bool(self._items)

    async def close(self) -> None:
        await asyncio.gather(*(b.close() for b in self._items))

    async def by_kp(self, kp_id: int) -> list[dict]:
        results = await asyncio.gather(
            *(b.by_kp(kp_id) for b in self._items), return_exceptions=True
        )
        collected: list[dict] = []
        seen: set[str] = set()
        for res in results:
            if isinstance(res, BaseException):
                log.warning("балансер упал: %s", res)
                continue
            for item in res:
                if item["url"] in seen:
                    continue
                seen.add(item["url"])
                collected.append(item)
        return collected