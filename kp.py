import httpx
from config import Config

BASE = "https://api.poiskkino.dev"


class Kinopoisk:
    def __init__(self, cfg: Config) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE,
            headers={"X-API-KEY": cfg.kp_api_key},
            timeout=httpx.Timeout(10.0, connect=5.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        r = await self._client.get(
            "/v1.4/movie/search",
            params={"query": query, "limit": limit, "page": 1},
        )
        r.raise_for_status()
        out = []
        for m in r.json().get("docs", []):
            out.append({
                "kp_id": m.get("id"),
                "name": m.get("name") or m.get("alternativeName") or "Без названия",
                "year": m.get("year"),
                "rating": (m.get("rating") or {}).get("kp"),
                "poster": (m.get("poster") or {}).get("previewUrl"),
                "description": (m.get("description") or "")[:600],
                "is_series": m.get("isSeries", False),
            })
        return [o for o in out if o["kp_id"]]