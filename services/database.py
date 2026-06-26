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


# ---------------------------------------------------------------------------
# Schema initialization & migrations (non-destructive)
# ---------------------------------------------------------------------------

def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


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

            # ---- Migrations: add columns to lookups for richer analytics ----
            existing = _table_columns(conn, "lookups")
            migrations = [
                ("country", "TEXT"),
                ("city", "TEXT"),
                ("isp", "TEXT"),
                ("asn", "TEXT"),
                ("lat", "REAL"),
                ("lon", "REAL"),
                ("risk_level", "TEXT"),
                ("lookup_time_ms", "INTEGER"),
            ]
            for col, coltype in migrations:
                if col not in existing:
                    conn.execute(f"ALTER TABLE lookups ADD COLUMN {col} {coltype}")
                    logging.info("Migrated lookups: added column %s", col)

            # ---- Index for faster history queries ----
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lookups_user "
                "ON lookups(user_id, id DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_lookups_created "
                "ON lookups(created_at)"
            )

            conn.commit()
            logging.info("Database initialized at %s", config.DB_PATH)
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Lookups (extended)
# ---------------------------------------------------------------------------

def save_lookup(
    user_id: int,
    lookup_type: str,
    query_value: str,
    result_json: str,
    *,
    country: str | None = None,
    city: str | None = None,
    isp: str | None = None,
    asn: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    risk_level: str | None = None,
    lookup_time_ms: int | None = None,
) -> None:
    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                """INSERT INTO lookups
                   (user_id, lookup_type, query_value, result_json,
                    country, city, isp, asn, lat, lon, risk_level, lookup_time_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id, lookup_type, query_value, result_json,
                    country, city, isp, asn, lat, lon, risk_level, lookup_time_ms,
                ),
            )
            conn.commit()
        finally:
            conn.close()


def get_user_history(user_id: int, limit: int = 10) -> list[sqlite3.Row]:
    with _lock:
        conn = _get_conn()
        try:
            return conn.execute(
                "SELECT lookup_type, query_value, result_json, created_at, risk_level "
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


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

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


def count_cache_entries() -> int:
    with _lock:
        conn = _get_conn()
        try:
            return conn.execute("SELECT COUNT(*) AS c FROM cache").fetchone()["c"]
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

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


def get_advanced_stats() -> dict:
    """Extended statistics for the upgraded /stats command."""
    with _lock:
        conn = _get_conn()
        try:
            total_users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
            total_lookups = conn.execute("SELECT COUNT(*) AS c FROM lookups").fetchone()["c"]
            today = conn.execute(
                "SELECT COUNT(*) AS c FROM lookups WHERE DATE(created_at) = DATE('now')"
            ).fetchone()["c"]

            # Type breakdown
            type_rows = conn.execute(
                "SELECT lookup_type, COUNT(*) AS c FROM lookups GROUP BY lookup_type"
            ).fetchall()
            type_breakdown = {r["lookup_type"]: r["c"] for r in type_rows}

            # Top queries (general)
            top_rows = conn.execute(
                "SELECT query_value, COUNT(*) AS c FROM lookups "
                "GROUP BY query_value ORDER BY c DESC LIMIT 5"
            ).fetchall()
            top_queries = [(r["query_value"], r["c"]) for r in top_rows]

            # Top countries (from lookups that have country populated)
            country_rows = conn.execute(
                "SELECT country, COUNT(*) AS c FROM lookups "
                "WHERE country IS NOT NULL AND country != '' "
                "GROUP BY country ORDER BY c DESC LIMIT 5"
            ).fetchall()
            top_countries = [(r["country"], r["c"]) for r in country_rows]

            # Top ISPs
            isp_rows = conn.execute(
                "SELECT isp, COUNT(*) AS c FROM lookups "
                "WHERE isp IS NOT NULL AND isp != '' "
                "GROUP BY isp ORDER BY c DESC LIMIT 5"
            ).fetchall()
            top_isps = [(r["isp"], r["c"]) for r in isp_rows]

            # Top domains (lookup_type = 'domain')
            domain_rows = conn.execute(
                "SELECT query_value, COUNT(*) AS c FROM lookups "
                "WHERE lookup_type = 'domain' "
                "GROUP BY query_value ORDER BY c DESC LIMIT 5"
            ).fetchall()
            top_domains = [(r["query_value"], r["c"]) for r in domain_rows]

            # Daily lookup counts (last 14 days)
            daily_rows = conn.execute(
                "SELECT DATE(created_at) AS d, COUNT(*) AS c FROM lookups "
                "WHERE created_at >= DATE('now', '-14 days') "
                "GROUP BY DATE(created_at) ORDER BY d ASC"
            ).fetchall()
            daily_graph = [(r["d"], r["c"]) for r in daily_rows]

            # Average lookup time (ms)
            avg_time_row = conn.execute(
                "SELECT AVG(lookup_time_ms) AS a FROM lookups "
                "WHERE lookup_time_ms IS NOT NULL"
            ).fetchone()
            avg_lookup_time = avg_time_row["a"] if avg_time_row and avg_time_row["a"] else 0.0

            # Cache hit ratio: compare total lookups vs cache entries.
            # A higher cache count relative to lookups indicates more reuse.
            cache_count = conn.execute("SELECT COUNT(*) AS c FROM cache").fetchone()["c"]
            cache_ratio = (cache_count / total_lookups * 100) if total_lookups > 0 else 0.0

            return {
                "total_users": total_users,
                "total_lookups": total_lookups,
                "lookups_today": today,
                "type_breakdown": type_breakdown,
                "top_queries": top_queries,
                "top_countries": top_countries,
                "top_isps": top_isps,
                "top_domains": top_domains,
                "daily_graph": daily_graph,
                "avg_lookup_time_ms": round(avg_lookup_time, 1) if avg_lookup_time else 0.0,
                "cache_count": cache_count,
                "cache_ratio": round(cache_ratio, 1),
            }
        finally:
            conn.close()