from app import AUDIT_HISTORY, _fabric_log_path
from db import get_db


def _latest_complaint_id():
    with get_db() as conn:
        row = conn.execute(
            "SELECT complaint_id FROM complaints ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return row["complaint_id"] if row else None


def _seed_single_complaint(client):
    client.post(
        "/submit",
        data={
            "citizen_id": "citizen-reset",
            "title": "Reset test",
            "description": "Ensure reset clears state",
            "category": "Test",
            "priority": "HIGH",
        },
    )
    return _latest_complaint_id()


def test_reset_requires_confirmation_does_not_clear_data(client):
    complaint_id = _seed_single_complaint(client)
    client.post("/audit", data={"complaint_id": complaint_id, "action": "verify"})

    response = client.post("/reset", data={"confirmation": "NOPE"})

    assert response.status_code == 200
    with get_db() as conn:
        complaints = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
        events = conn.execute("SELECT COUNT(*) FROM complaint_events").fetchone()[0]
        ledger = conn.execute("SELECT COUNT(*) FROM ledger_hashes").fetchone()[0]
    assert complaints == 1
    assert events >= 1
    assert ledger >= 1
    assert AUDIT_HISTORY, "Audit history should remain when confirmation fails"


def test_reset_clears_all_tables_and_history(client):
    complaint_id = _seed_single_complaint(client)
    client.post("/audit", data={"complaint_id": complaint_id, "action": "verify"})
    log_path = _fabric_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("stub-log")

    response = client.post("/reset", data={"confirmation": "RESET"})

    assert response.status_code == 200
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM complaint_events").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ledger_hashes").fetchone()[0] == 0
    assert not AUDIT_HISTORY
    assert not log_path.exists()


def test_benchmark_caps_inputs_and_runs_audits(client):
    response = client.post(
        "/benchmark/run",
        data={"complaints": 50, "events_per_complaint": 12},
    )

    assert response.status_code == 200
    with get_db() as conn:
        complaints = conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
        events = conn.execute("SELECT COUNT(*) FROM complaint_events").fetchone()[0]
        ledger = conn.execute("SELECT COUNT(*) FROM ledger_hashes").fetchone()[0]
    assert complaints == 20
    assert events == 20 * 7
    assert ledger == 20 * 7
    assert len(AUDIT_HISTORY) == 20
    assert b"Used N=20, M=6" in response.data
