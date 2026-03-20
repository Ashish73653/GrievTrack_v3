import json

from app import AUDIT_HISTORY
from db import get_db
from utils import canonical_event_payload, canonical_json, sha256


def _seed_complaint_with_updates(client):
    client.post(
        "/submit",
        data={
            "citizen_id": "citizen-audit",
            "title": "Audit trail check",
            "description": "Ensure audit verification works",
            "category": "Test",
            "priority": "HIGH",
        },
    )
    with get_db() as conn:
        complaint_id = conn.execute(
            "SELECT complaint_id FROM complaints ORDER BY created_at DESC LIMIT 1"
        ).fetchone()["complaint_id"]

    client.post(
        "/update",
        data={
            "complaint_id": complaint_id,
            "officer_id": "officer-1",
            "status": "ASSIGNED",
            "remarks": "Assigned to unit",
        },
    )
    client.post(
        "/update",
        data={
            "complaint_id": complaint_id,
            "officer_id": "officer-1",
            "status": "IN_PROGRESS",
            "remarks": "Investigation started",
        },
    )
    return complaint_id


def test_audit_verification_records_metrics(client):
    complaint_id = _seed_complaint_with_updates(client)

    response = client.post(
        "/audit", data={"complaint_id": complaint_id, "action": "verify"}
    )

    assert response.status_code == 200
    assert AUDIT_HISTORY
    run = AUDIT_HISTORY[-1]
    assert run["complaint_id"] == complaint_id
    assert run["summary"]["matched"] == run["summary"]["total"]
    assert run["summary"]["eis_score"] == 100.0
    assert run["summary"]["chain_status"] == "OK"
    assert run["summary"]["oai"]["status"] in {"WITHIN_SLA", "DELAYED"}


def test_tamper_simulation_reduces_eis(client):
    complaint_id = _seed_complaint_with_updates(client)
    client.post("/audit", data={"complaint_id": complaint_id, "action": "verify"})
    baseline_matched = AUDIT_HISTORY[-1]["summary"]["matched"]

    response = client.post(
        "/audit", data={"complaint_id": complaint_id, "action": "tamper"}
    )

    assert response.status_code == 200
    tampered_run = AUDIT_HISTORY[-1]
    assert tampered_run["summary"]["matched"] < baseline_matched
    assert tampered_run["summary"]["chain_status"] == "BROKEN"
    assert any(event["status"] == "TAMPERED" for event in tampered_run["events"])


def test_audit_report_downloads_latest_run(client):
    complaint_id = _seed_complaint_with_updates(client)
    client.post("/audit", data={"complaint_id": complaint_id, "action": "verify"})
    run_id = AUDIT_HISTORY[-1]["run_id"]

    response = client.get(f"/audit/report?run_id={run_id}")

    assert response.status_code == 200
    payload = json.loads(response.data)
    assert payload["run_id"] == run_id
    assert payload["complaint"]["complaint_id"] == complaint_id


def test_audit_handles_legacy_hashes(client):
    complaint_id = _seed_complaint_with_updates(client)

    with get_db() as conn:
        events = conn.execute(
            """
            SELECT event_id, event_type, actor_id, remarks, timestamp
            FROM complaint_events
            WHERE complaint_id = ?
            ORDER BY timestamp ASC, rowid ASC
            """,
            (complaint_id,),
        ).fetchall()
        prev_hash = ""
        for event in events:
            payload = canonical_event_payload(
                complaint_id=complaint_id,
                event_id=event["event_id"],
                event_type=event["event_type"],
                actor_id=event["actor_id"],
                remarks=event["remarks"],
                timestamp=event["timestamp"],
                prev_event_hash=prev_hash,
            )
            recalculated_hash = sha256(canonical_json(payload))
            conn.execute(
                "UPDATE ledger_hashes SET event_hash = ? WHERE event_id = ?",
                (recalculated_hash, event["event_id"]),
            )
            prev_hash = recalculated_hash
        conn.commit()

    client.post("/audit", data={"complaint_id": complaint_id, "action": "verify"})

    run = AUDIT_HISTORY[-1]
    assert run["summary"]["chain_status"] == "OK"
    assert any(event["chain_status"] == "LEGACY" for event in run["events"])
