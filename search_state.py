from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass


@dataclass
class _SearchSession:
    message_ids: list[int]
    expires_at: float
    offset: int = 0


class PageStore:
    """Keep only temporary message references needed to serve More pages."""

    def __init__(self, ttl_seconds: int = 600, max_sessions: int = 1000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self._sessions: dict[int, _SearchSession] = {}

    def _prune(self, now: float) -> None:
        expired = [
            user_id
            for user_id, session in self._sessions.items()
            if session.expires_at <= now
        ]
        for user_id in expired:
            del self._sessions[user_id]

    def set_results(self, user_id: int, message_ids: list[int]) -> None:
        now = time.monotonic()
        self._prune(now)
        if user_id not in self._sessions and len(self._sessions) >= self.max_sessions:
            oldest_user_id = next(iter(self._sessions))
            del self._sessions[oldest_user_id]
        self._sessions[user_id] = _SearchSession(
            message_ids=list(message_ids),
            expires_at=now + self.ttl_seconds,
        )

    def next_page(self, user_id: int, page_size: int = 5) -> list[int]:
        now = time.monotonic()
        self._prune(now)
        session = self._sessions.get(user_id)
        if session is None:
            return []
        page = session.message_ids[session.offset : session.offset + page_size]
        session.offset += len(page)
        session.expires_at = now + self.ttl_seconds
        return page

    def has_more(self, user_id: int) -> bool:
        now = time.monotonic()
        self._prune(now)
        session = self._sessions.get(user_id)
        return bool(session and session.offset < len(session.message_ids))


class SlidingWindowRateLimiter:
    def __init__(self, limit: int = 5, window_seconds: int = 60) -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[int, deque[float]] = {}

    def allow(self, user_id: int, now: float | None = None) -> bool:
        current_time = time.monotonic() if now is None else now
        events = self._events.setdefault(user_id, deque())
        while events and current_time - events[0] >= self.window_seconds:
            events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(current_time)
        if not events:
            self._events.pop(user_id, None)
        return True