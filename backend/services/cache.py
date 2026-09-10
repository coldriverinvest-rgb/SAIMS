"""Minimal thread-safe TTL cache for expensive external fan-out responses."""
import time
from threading import Lock


class TTLCache:
    def __init__(self, ttl_seconds: float):
        self.ttl = max(0.0, float(ttl_seconds))
        self._store: dict[str, tuple[object, float]] = {}
        self._lock = Lock()

    def get(self, key: str):
        if self.ttl <= 0:
            return None
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value) -> None:
        if self.ttl <= 0:
            return
        with self._lock:
            self._store[key] = (value, time.monotonic() + self.ttl)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
