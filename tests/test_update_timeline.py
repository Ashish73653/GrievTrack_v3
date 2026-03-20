from db import get_db
from utils import canonical_event_payload, canonical_json, sha256


def _create_complaint(client):
    client.post(
        "/submit",
        data={
            "citizen_id": "citizen-1",
            "title": "Noise complaint",
            "description": "Loud generator running at night.",
            "category": "Community",
            "priority": "MEDIUM",
        },
    )
    with get_db() as conn:
        complaint = conn.execute(
            "SELECT complaint_id FROM complaints ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return complaint["complaint_id"]


def test_officer_update_adds_event_and_anchor(client):
    complaint_id = _create_complaint(client)

    with get_db() as conn:
        prev_event = conn.execute(
            "SELECT event_id FROM complaint_events WHERE complaint_id = ?",
            (complaint_id,),
        ).fetchone()
        prev_hash = conn.execute(
            "SELECT event_hash FROM ledger_hashes WHERE event_id = ?",
            (prev_event["event_id"],),
        ).fetchone()["event_hash"]

    response = client.post(
        "/update",
        data={
            "complaint_id": complaint_id,
            "officer_id": "officer-9",
            "status": "IN_PROGRESS",
            "remarks": "Initial triage started",
        },
    )

    assert response.status_code == 200
    assert b"Update recorded" in response.data

    with get_db() as conn:
        complaint = conn.execute(
            "SELECT current_status FROM complaints WHERE complaint_id = ?",
            (complaint_id,),
        ).fetchone()
        assert complaint["current_status"] == "IN_PROGRESS"

        latest_event = conn.execute(
            """
            SELECT * FROM complaint_events
            WHERE complaint_id = ?
            ORDER BY timestamp DESC, rowid DESC
            LIMIT 1
            """,
            (complaint_id,),
        ).fetchone()
        assert latest_event["event_type"] == "IN_PROGRESS"
        assert latest_event["actor_id"] == "officer-9"
        assert latest_event["remarks"] == "Initial triage started"

        ledger_row = conn.execute(
            "SELECT * FROM ledger_hashes WHERE event_id = ?",
            (latest_event["event_id"],),
        ).fetchone()

    payload = canonical_event_payload(
        complaint_id=complaint_id,
        event_id=latest_event["event_id"],
        event_type=latest_event["event_type"],
        actor_id=latest_event["actor_id"],
        remarks=latest_event["remarks"],
        timestamp=latest_event["timestamp"],
        prev_event_hash=prev_hash,
    )
    expected_hash = sha256(canonical_json(payload))

    assert ledger_row["event_hash"] == expected_hash


def test_timeline_lists_events_for_complaint(client):
    complaint_id = _create_complaint(client)

    client.post(
        "/update",
        data={
            "complaint_id": complaint_id,
            "officer_id": "officer-5",
            "status": "IN_PROGRESS",
            "remarks": "Assigned and investigating",
        },
    )
    client.post(
        "/update",
        data={
            "complaint_id": complaint_id,
            "officer_id": "officer-5",
            "status": "RESOLVED",
            "remarks": "Issue fixed",
        },
    )

    response = client.get(f"/timeline/?complaint_id={complaint_id}")
    assert response.status_code == 200
    assert complaint_id.encode("utf-8") in response.data
    assert b"SUBMIT" in response.data
    assert b"IN_PROGRESS" in response.data
    assert b"RESOLVED" in response.data
