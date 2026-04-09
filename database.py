import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "xing_lite.db")


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_cache (
                discord_url    TEXT PRIMARY KEY,
                claude_file_id TEXT NOT NULL,
                filename       TEXT,
                mime_type      TEXT,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quests (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    TEXT NOT NULL,
                user_id     TEXT NOT NULL,
                title       TEXT NOT NULL,
                description TEXT,
                due_at      TEXT,
                notified    INTEGER DEFAULT 0,
                completed   INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now'))
            )
        """)


def get_file_id(url: str) -> str | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT claude_file_id FROM file_cache WHERE discord_url = ?", (url,)
        ).fetchone()
    return row[0] if row else None


# ── Quest functions ───────────────────────────────────────────────────────────

def add_quest(guild_id: str, user_id: str, title: str,
              description: str | None, due_at: str | None) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO quests (guild_id, user_id, title, description, due_at) VALUES (?,?,?,?,?)",
            (guild_id, user_id, title, description, due_at),
        )
        return cur.lastrowid


def get_quests(guild_id: str, user_id: str, include_completed: bool = False) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM quests WHERE guild_id=? AND user_id=?"
        params: list = [guild_id, user_id]
        if not include_completed:
            query += " AND completed=0"
        query += " ORDER BY due_at IS NULL, due_at ASC, created_at ASC"
        return [dict(r) for r in conn.execute(query, params).fetchall()]


def get_due_quests() -> list[dict]:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(
            "SELECT * FROM quests WHERE due_at IS NOT NULL AND due_at<=? AND notified=0 AND completed=0",
            (now,),
        ).fetchall()]


def mark_notified(quest_id: int) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("UPDATE quests SET notified=1 WHERE id=?", (quest_id,))


def complete_quest(quest_id: int, user_id: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "UPDATE quests SET completed=1 WHERE id=? AND user_id=?", (quest_id, user_id)
        )
        return cur.rowcount > 0


def delete_quest(quest_id: int, user_id: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "DELETE FROM quests WHERE id=? AND user_id=?", (quest_id, user_id)
        )
        return cur.rowcount > 0


def save_file_id(url: str, file_id: str, filename: str, mime_type: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """INSERT OR REPLACE INTO file_cache
               (discord_url, claude_file_id, filename, mime_type, created_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (url, file_id, filename, mime_type),
        )
