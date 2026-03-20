import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from db import get_db
from utils import now_iso


class SQLiteLedgerBackend:
    backend = "sqlite"

    def anchor_hash(
        self, event_id: str, complaint_id: str, event_hash: str, timestamp: str
    ) -> Dict[str, Any]:
        """Store hash data in the local SQLite ledger_hashes table."""
        anchored_at = now_iso()
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO ledger_hashes (event_id, complaint_id, event_hash, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, complaint_id, event_hash, timestamp),
            )
            conn.commit()

        return {"backend": self.backend, "tx_id": "", "anchored_at": anchored_at}

    def get_anchor(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Return anchor row for the given event_id or None if not found."""
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ledger_id, event_id, complaint_id, event_hash, timestamp
                FROM ledger_hashes
                WHERE event_id = ?
                """,
                (event_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None


class FabricStubLedgerBackend(SQLiteLedgerBackend):
    backend = "fabric_stub"
    _log_path = Path(__file__).resolve().parent / "fabric_stub" / "anchored_log.jsonl"

    def anchor_hash(
        self, event_id: str, complaint_id: str, event_hash: str, timestamp: str
    ) -> Dict[str, Any]:
        anchored_at = now_iso()
        tx_id = f"TX-{uuid4()}"

        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "tx_id": tx_id,
            "event_id": event_id,
            "complaint_id": complaint_id,
            "event_hash": event_hash,
            "timestamp": timestamp,
            "anchored_at": anchored_at,
        }
        with self._log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(entry, separators=(",", ":")) + "\n")

        super().anchor_hash(event_id, complaint_id, event_hash, timestamp)

        return {"backend": self.backend, "tx_id": tx_id, "anchored_at": anchored_at}


def get_ledger_backend():
    backend_choice = os.getenv("GRIEVTRACK_LEDGER_BACKEND", "sqlite").lower()
    if backend_choice == "fabric_stub":
        return FabricStubLedgerBackend()
    if backend_choice == "sqlite":
        return SQLiteLedgerBackend()
    raise ValueError(f"Unsupported ledger backend: {backend_choice}")
