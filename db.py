import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "grievtrack.db"


def get_db() -> sqlite3.Connection:
    """Return a SQLite connection with rows accessible by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create required tables if they do not already exist."""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS complaints (
                complaint_id TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                category TEXT,
                priority TEXT,
                citizen_id TEXT,
                current_status TEXT,
                created_at TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS complaint_events (
                event_id TEXT PRIMARY KEY,
                complaint_id TEXT,
                event_type TEXT,
                actor_id TEXT,
                remarks TEXT,
                timestamp TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ledger_hashes (
                ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT,
                complaint_id TEXT,
                event_hash TEXT,
                timestamp TEXT
            )
            """
        )

        conn.commit()


if __name__ == "__main__":
    init_db()
