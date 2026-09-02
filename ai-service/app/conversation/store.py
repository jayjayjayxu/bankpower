"""Small durable store for auditable conversation state and completed turns."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class SQLiteConversationStore:
    """Persist only user messages, public outcomes and structured state.

    This deliberately excludes model-private reasoning. Each write replaces the
    session snapshot and its compact completed-turn records atomically.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        connection = self._connect()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversation_session (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    state_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation_turn (
                    turn_number INTEGER NOT NULL,
                    session_id TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    effective_question TEXT NOT NULL,
                    route TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (session_id, turn_number),
                    FOREIGN KEY (session_id) REFERENCES conversation_session(session_id)
                );
                """
            )
        finally:
            connection.close()

    def save(self, state: dict[str, Any], turns: list[dict[str, Any]]) -> None:
        with self._lock:
            connection = self._connect()
            try:
                with connection:
                    self._save(connection, state, turns)
            finally:
                connection.close()

    @staticmethod
    def _save(connection: sqlite3.Connection, state: dict[str, Any], turns: list[dict[str, Any]]) -> None:
        connection.execute(
            """
            INSERT INTO conversation_session(session_id, created_at, updated_at, status, state_json)
            VALUES (?, ?, ?, 'ACTIVE', ?)
            ON CONFLICT(session_id) DO UPDATE SET updated_at=excluded.updated_at, state_json=excluded.state_json
            """,
            (state["session_id"], state["created_at"], state["updated_at"], json.dumps(state, ensure_ascii=False, sort_keys=True)),
        )
        connection.execute("DELETE FROM conversation_turn WHERE session_id=?", (state["session_id"],))
        connection.executemany(
            """INSERT INTO conversation_turn(turn_number, session_id, user_message, effective_question, route, result_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (index, state["session_id"], item["question"], item["effective_question"], item["result"].get("route", "UNKNOWN"),
                 json.dumps(item["result"], ensure_ascii=False, sort_keys=True, default=str), item["created_at"])
                for index, item in enumerate(turns, 1)
            ],
        )

    def load(self, session_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        with self._lock:
            connection = self._connect()
            try:
                session = connection.execute(
                    "SELECT state_json FROM conversation_session WHERE session_id=? AND status='ACTIVE'", (session_id,)
                ).fetchone()
                if session is None:
                    return None
                turns = connection.execute(
                    "SELECT user_message,effective_question,result_json,created_at FROM conversation_turn WHERE session_id=? ORDER BY turn_number",
                    (session_id,),
                ).fetchall()
            finally:
                connection.close()
        return json.loads(session[0]), [
            {"question": row[0], "effective_question": row[1], "result": json.loads(row[2]), "created_at": row[3]}
            for row in turns
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
