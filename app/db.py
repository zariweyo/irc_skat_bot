import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get("DB_PATH", "./data/irc_bot.db"))


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS score_events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                nick       TEXT    NOT NULL,
                channel    TEXT    NOT NULL,
                game       TEXT    NOT NULL,
                points     INTEGER NOT NULL,
                earned_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            );
        """)
    print(f"[DB] Inicializada en {DB_PATH}")


def add_points(nick: str, channel: str, game: str, points: int):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO score_events (nick, channel, game, points) VALUES (?, ?, ?, ?)",
            (nick, channel, game, points),
        )


def get_top(channel: str | None = None, limit: int = 10) -> list[sqlite3.Row]:
    where  = "WHERE channel = ?" if channel else ""
    params = (channel, limit) if channel else (limit,)
    with _conn() as conn:
        return conn.execute(
            f"SELECT nick, SUM(points) AS total FROM score_events {where} "
            f"GROUP BY nick ORDER BY total DESC LIMIT ?",
            params,
        ).fetchall()


def get_player_total(nick: str, channel: str | None = None) -> int:
    where  = "AND channel = ?" if channel else ""
    params = (nick, channel) if channel else (nick,)
    with _conn() as conn:
        row = conn.execute(
            f"SELECT SUM(points) FROM score_events WHERE nick = ? {where}",
            params,
        ).fetchone()
    return row[0] or 0
