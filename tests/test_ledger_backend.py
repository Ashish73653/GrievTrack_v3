import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import get_db, init_db
from ledger_backend import FabricStubLedgerBackend, SQLiteLedgerBackend, get_ledger_backend


@pytest.fixture(autouse=True)
def reset_storage():
    init_db()
    with get_db() as conn:
        conn.execute("DELETE FROM ledger_hashes")
        conn.commit()

    log_path = ROOT / "fabric_stub" / "anchored_log.jsonl"
    if log_path.exists():
        log_path.unlink()
    yield


def test_get_ledger_backend_defaults_to_sqlite(monkeypatch):
    monkeypatch.delenv("GRIEVTRACK_LEDGER_BACKEND", raising=False)
    backend = get_ledger_backend()
    assert isinstance(backend, SQLiteLedgerBackend)


def test_sqlite_backend_anchor_and_get():
    backend = SQLiteLedgerBackend()
    meta = backend.anchor_hash(
        event_id="EVT-1234",
        complaint_id="CMP-0001",
        event_hash="abc123",
        timestamp="2024-01-01T00:00:00+00:00",
    )

    assert meta["backend"] == "sqlite"
    assert meta["tx_id"] == ""
    assert meta["anchored_at"]

    anchor = backend.get_anchor("EVT-1234")
    assert anchor is not None
    assert anchor["event_id"] == "EVT-1234"
    assert anchor["complaint_id"] == "CMP-0001"
    assert anchor["event_hash"] == "abc123"


def test_fabric_stub_writes_jsonl_and_sqlite(monkeypatch):
    monkeypatch.setenv("GRIEVTRACK_LEDGER_BACKEND", "fabric_stub")
    backend = get_ledger_backend()
    meta = backend.anchor_hash(
        event_id="EVT-9999",
        complaint_id="CMP-9999",
        event_hash="hash9999",
        timestamp="2024-05-05T05:05:05+00:00",
    )

    assert isinstance(backend, FabricStubLedgerBackend)
    assert meta["backend"] == "fabric_stub"
    assert meta["tx_id"].startswith("TX-")
    assert meta["anchored_at"]

    log_path = ROOT / "fabric_stub" / "anchored_log.jsonl"
    assert log_path.exists()
    with log_path.open("r", encoding="utf-8") as fh:
        lines = [line.strip() for line in fh if line.strip()]
    assert lines
    record = json.loads(lines[-1])
    assert record["tx_id"] == meta["tx_id"]
    assert record["event_id"] == "EVT-9999"
    assert record["complaint_id"] == "CMP-9999"
    assert record["event_hash"] == "hash9999"
    assert record["timestamp"] == "2024-05-05T05:05:05+00:00"
    assert record["anchored_at"] == meta["anchored_at"]

    anchor = backend.get_anchor("EVT-9999")
    assert anchor is not None
    assert anchor["event_hash"] == "hash9999"
