from db import get_db
from utils import canonical_event_payload, canonical_json, sha256


def test_submit_creates_records_and_receipt(client):
    response = client.post(
        "/submit",
        data={
            "citizen_id": "citizen-123",
            "title": "Pothole on Main Street",
            "description": "Large pothole near the crosswalk.",
            "category": "Road",
            "priority": "HIGH",
        },
    )

    assert response.status_code == 200

    with get_db() as conn:
        complaint = conn.execute(
            "SELECT * FROM complaints ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        assert complaint is not None
        assert complaint["citizen_id"] == "citizen-123"
        assert complaint["title"] == "Pothole on Main Street"
        assert complaint["description"] == "Large pothole near the crosswalk."
        assert complaint["category"] == "Road"
        assert complaint["priority"] == "HIGH"
        assert complaint["current_status"] == "SUBMIT"

        event = conn.execute(
            "SELECT * FROM complaint_events WHERE complaint_id = ?",
            (complaint["complaint_id"],),
        ).fetchone()
        assert event is not None
        assert event["event_type"] == "SUBMIT"
        assert event["actor_id"] == "citizen-123"
        assert event["remarks"] == "Complaint submitted"

        payload = canonical_event_payload(
            complaint_id=complaint["complaint_id"],
            event_id=event["event_id"],
            event_type=event["event_type"],
            actor_id=event["actor_id"],
            remarks=event["remarks"],
            timestamp=event["timestamp"],
            prev_event_hash="",
        )
        expected_hash = sha256(canonical_json(payload))

        ledger_row = conn.execute(
            "SELECT * FROM ledger_hashes WHERE event_id = ?", (event["event_id"],)
        ).fetchone()
        assert ledger_row is not None
        assert ledger_row["event_hash"] == expected_hash
        assert ledger_row["timestamp"] == event["timestamp"]

    assert b"Submission Receipt" in response.data
    assert b"View timeline" in response.data
    assert event["event_id"].encode("utf-8") in response.data
    assert expected_hash.encode("utf-8") in response.data
