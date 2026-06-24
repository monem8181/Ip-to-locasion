import os
import sqlite3
import json
import time
import threading
import logging

import config

_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    db_dir = os.path.dirname(config.DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    with _lock:
        conn = _get_conn()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id    INTEGER PRIMARY KEY,
                    username   TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    banned     INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS lookups (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id      INTEGER NOT NULL,
                    lookup_type  TEXT NOT NULL,
                    query_value  TEXT NOT NULL,
                    result_json  TEXT,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE TABLE IF NOT EXISTS cache (
                    cache_key   TEXT PRIMARY KEY,
                    result_json TEXT,
                    cached_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()
            logging.info("Database initialized at %s", config.DB_PATH)
        finally:
            conn.close()


def get_or_create_user(user_id: int, username: str | None = None) -> sqlite3.Row:
    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO users (user_id, username) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET username = excluded.username",
                (user_id, username),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            return row
        finally:
            conn.close()


def is_banned(user_id: int) -> bool:
    with _lock:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT banned FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row is None:
                return False
            return bool(row["banned"])
        finally:
            conn.close()


def set_banned(user_id: int, banned: bool) -> None:
    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                "UPDATE users SET banned = ? WHERE user_id = ?",
                (1 if banned else 0, user_id),
            )
            conn.commit()
        finally:
            conn.close()


def save_lookup(user_id: int, lookup_type: str, query_value: str, result_json: str) -> None:
    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO lookups (user_id, lookup_type, query_value, result_json) "
                "VALUES (?, ?, ?, ?)",
                (user_id, lookup_type, query_value, result_json),
            )
            conn.commit()
        finally:
            conn.close()


def get_user_history(user_id: int, limit: int = 10) -> list[sqlite3.Row]:
    with _lock:
        conn = _get_conn()
        try:
            return conn.execute(
                "SELECT lookup_type, query_value, result_json, created_at "
                "FROM lookups WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        finally:
            conn.close()


def get_user_history_all(user_id: int) -> list[sqlite3.Row]:
    with _lock:
        conn = _get_conn()
        try:
            return conn.execute(
                "SELECT lookup_type, query_value, result_json, created_at "
                "FROM lookups WHERE user_id = ? ORDER BY id ASC",
                (user_id,),
            ).fetchall()
        finally:
            conn.close()


def get_all_user_ids() -> list[int]:
    with _lock:
        conn = _get_conn()
        try:
            rows = conn.execute("SELECT user_id FROM users").fetchall()
            return [r["user_id"] for r in rows]
        finally:
            conn.close()


def get_cache(cache_key: str) -> tuple[str | None, float]:
    with _lock:
        conn = _get_conn()
        try:
            row = conn.execute(
                "SELECT result_json, cached_at FROM cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
            if row is None:
                return None, 0.0
            cached_at = 0.0
            try:
                cached_at = float(row["cached_at"])
            except (ValueError, TypeError):
                # SQLite CURRENT_TIMESTAMP stores "YYYY-MM-DD HH:MM:SS";
                # convert via epoch for accurate TTL checks.
                import datetime as _dt
                parsed = _dt.datetime.fromisoformat(str(row["cached_at"]))
                cached_at = parsed.timestamp()
            return row["result_json"], cached_at
        finally:
            conn.close()


def set_cache(cache_key: str, result_json: str) -> None:
    ts = str(time.time())
    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO cache (cache_key, result_json, cached_at) "
                "VALUES (?, ?, ?) ON CONFLICT(cache_key) "
                "DO UPDATE SET result_json = excluded.result_json, cached_at = excluded.cached_at",
                (cache_key, result_json, ts),
            )
            conn.commit()
        finally:
            conn.close()


def get_stats() -> dict:
    with _lock:
        conn = _get_conn()
        try:
            total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
            total_lookups = conn.execute("SELECT COUNT(*) AS c FROM lookups").fetchone()["c"]
            today = conn.execute(
                "SELECT COUNT(*) AS c FROM lookups WHERE DATE(created_at) = DATE('now')"
            ).fetchone()["c"]

            type_rows = conn.execute(
                "SELECT lookup_type, COUNT(*) AS c FROM lookups GROUP BY lookup_type"
            ).fetchall()
            type_breakdown = {r["lookup_type"]: r["c"] for r in type_rows}

            top_rows = conn.execute(
                "SELECT query_value, COUNT(*) AS c FROM lookups "
                "GROUP BY query_value ORDER BY c DESC LIMIT 5"
            ).fetchall()
            top_queries = [(r["query_value"], r["c"]) for r in top_rows]

            return {
                "total_users": total_users,
                "total_lookups": total_lookups,
                "lookups_today": today,
                "type_breakdown": type_breakdown,
                "top_queries": top_queries,
            }
        finally:
            conn.close()