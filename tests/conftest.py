import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app
from db import get_db, init_db


@pytest.fixture(autouse=True)
def clean_db():
    init_db()
    with get_db() as conn:
        conn.execute("DELETE FROM complaint_events")
        conn.execute("DELETE FROM complaints")
        conn.execute("DELETE FROM ledger_hashes")
        conn.commit()

    log_path = ROOT / "fabric_stub" / "anchored_log.jsonl"
    if log_path.exists():
        log_path.unlink()
    yield


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    return app.test_client()
