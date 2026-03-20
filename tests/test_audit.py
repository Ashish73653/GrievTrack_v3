import json

from app import AUDIT_HISTORY
from db import get_db


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
