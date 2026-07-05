from __future__ import annotations
import redis


class ValkeyKVStorage:
    def __init__(self, host: str, port: int = 6379, password: str = "", **kwargs):
        self._host = host
        self._port = port
        self._password = password or None
        self._client = None

    def _ensure(self):
        if self._client is None:
            self._client = redis.Redis(
                host=self._host, port=self._port,
                password=self._password, decode_responses=True,
            )

    def get(self, db: int, key: str) -> str | None:
        self._ensure()
        self._client.execute_command("SELECT", db)
        return self._client.get(key)

    def set(self, db: int, key: str, value: str, ttl: int | None = None) -> None:
        self._ensure()
        self._client.execute_command("SELECT", db)
        self._client.set(key, value, ex=ttl)

    def delete(self, db: int, key: str) -> bool:
        self._ensure()
        self._client.execute_command("SELECT", db)
        return self._client.delete(key) > 0

    def scan(self, db: int, pattern: str = "*", limit: int = 1000) -> list[str]:
        self._ensure()
        self._client.execute_command("SELECT", db)
        return list(self._client.scan_iter(match=pattern, count=limit))

    def health(self) -> bool:
        try:
            self._ensure()
            return self._client.ping()
        except Exception:
            return False
