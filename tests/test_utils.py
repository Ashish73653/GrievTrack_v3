import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils import canonical_event_payload, canonical_json, sha256


def test_sha256_length():
    digest = sha256("example")
    assert len(digest) == 64


def test_canonical_json_deterministic():
    payload_a = {"b": 2, "a": 1}
    payload_b = {"a": 1, "b": 2}

    json_a = canonical_json(payload_a)
    json_b = canonical_json(payload_b)

    assert json_a == json_b


def test_prev_event_hash_changes_hash():
    base_payload = canonical_event_payload(
        complaint_id="CMP-2024-ABCDEF",
        event_id="EVT-12345678",
        event_type="CREATE",
        actor_id="user-1",
        remarks="initial",
        timestamp="2024-01-01T00:00:00+00:00",
        prev_event_hash="",
    )
    chained_payload = canonical_event_payload(
        complaint_id="CMP-2024-ABCDEF",
        event_id="EVT-12345678",
        event_type="CREATE",
        actor_id="user-1",
        remarks="initial",
        timestamp="2024-01-01T00:00:00+00:00",
        prev_event_hash="abc123",
    )

    base_hash = sha256(canonical_json(base_payload))
    chained_hash = sha256(canonical_json(chained_payload))

    assert base_hash != chained_hash
