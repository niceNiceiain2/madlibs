"""
db.py — Database layer that works with BOTH SQLite (local) and PostgreSQL (Railway).

How it decides which to use:
- If the DATABASE_URL environment variable exists (set automatically by Railway), use PostgreSQL.
- Otherwise, fall back to a local SQLite file so you can still develop/test on your Mac.
"""

import os
import sqlite3

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras


# ── Connection ────────────────────────────────────────────────────────────────
def get_db():
    """Return a database connection with dict-like row access."""
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), "novalib.db"))
        conn.row_factory = sqlite3.Row
        return conn


# ── Placeholder translation ───────────────────────────────────────────────────
# SQLite uses "?" placeholders, PostgreSQL uses "%s".
# Write all queries with "?" and this converts them automatically for Postgres.
def q(query: str) -> str:
    if USE_POSTGRES:
        return query.replace("?", "%s")
    return query


# ── Schema ────────────────────────────────────────────────────────────────────
def init_db():
    """Create all tables if they don't exist. Handles both database types."""
    conn = get_db()
    cur  = conn.cursor()

    if USE_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id        SERIAL PRIMARY KEY,
                username  TEXT UNIQUE NOT NULL,
                password  TEXT NOT NULL,
                created   TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_achievements (
                id           SERIAL PRIMARY KEY,
                user_id      INTEGER NOT NULL,
                achievement  TEXT NOT NULL,
                earned_at    TEXT NOT NULL,
                UNIQUE(user_id, achievement)
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id        INTEGER PRIMARY KEY,
                stories_played INTEGER DEFAULT 0,
                slugs_played   TEXT DEFAULT ''
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS completed_stories (
                id               SERIAL PRIMARY KEY,
                user_id          INTEGER,
                slug             TEXT NOT NULL,
                title            TEXT NOT NULL,
                answers          TEXT NOT NULL,
                completed_story  TEXT NOT NULL,
                created_at       TEXT NOT NULL
            );
        """)
    else:
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                username  TEXT UNIQUE NOT NULL,
                password  TEXT NOT NULL,
                created   TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_achievements (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                achievement  TEXT NOT NULL,
                earned_at    TEXT NOT NULL,
                UNIQUE(user_id, achievement)
            );
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id        INTEGER PRIMARY KEY,
                stories_played INTEGER DEFAULT 0,
                slugs_played   TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS completed_stories (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER,
                slug             TEXT NOT NULL,
                title            TEXT NOT NULL,
                answers          TEXT NOT NULL,
                completed_story  TEXT NOT NULL,
                created_at       TEXT NOT NULL
            );
        """)

    conn.commit()
    cur.close()
    conn.close()
