import json
import time
from pathlib import Path
from typing import Any

import aiosqlite


class ConversationStore:
    def __init__(self, state_dir: Path | None = None, path: Path | None = None) -> None:
        root = state_dir or Path.home() / ".local" / "state" / "ai-provider-gateway"
        self._path = path or root / "conversations.db"
        self._db: aiosqlite.Connection | None = None

    async def _connection(self) -> aiosqlite.Connection:
        if self._db is None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._db = await aiosqlite.connect(self._path)
            await self._db.execute(
                "CREATE TABLE IF NOT EXISTS conversations (key TEXT PRIMARY KEY, state TEXT NOT NULL, updated_at REAL NOT NULL)"
            )
            await self._db.commit()
        return self._db

    async def get(self, key: str) -> dict[str, Any] | None:
        db = await self._connection()
        cursor = await db.execute("SELECT state FROM conversations WHERE key = ?", (key,))
        row = await cursor.fetchone()
        if row is None:
            return None
        try:
            state = json.loads(row[0])
        except json.JSONDecodeError:
            return None
        return state if isinstance(state, dict) else None

    async def set(self, key: str, state: dict[str, Any]) -> None:
        db = await self._connection()
        await db.execute(
            "INSERT INTO conversations (key, state, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET state = excluded.state, updated_at = excluded.updated_at",
            (key, json.dumps(state), time.time()),
        )
        await db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None
