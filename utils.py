import json
import hashlib
import secrets
from datetime import datetime, timezone


def now_iso() -> str:
    """Return current UTC time in ISO 8601 format without microseconds."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_complaint_id() -> str:
    """Generate complaint id: CMP-YYYY-XXXXXX where X is hex."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(3).upper()
    return f"CMP-{year}-{suffix}"


def new_event_id() -> str:
    """Generate event id: EVT-XXXXXXXX where X is hex."""
    token = secrets.token_hex(4).upper()
    return f"EVT-{token}"


def _normalize(value) -> str:
    """Convert None to empty string and everything else to str."""
    if value is None:
        return ""
    return str(value)


def canonical_event_payload(
    complaint_id,
    event_id,
    event_type,
    actor_id,
    remarks,
    timestamp,
    prev_event_hash=None,
):
    """Return normalized event payload for hashing."""
    return {
        "complaint_id": _normalize(complaint_id),
        "event_id": _normalize(event_id),
        "event_type": _normalize(event_type),
        "actor_id": _normalize(actor_id),
        "remarks": _normalize(remarks),
        "timestamp": _normalize(timestamp),
        "prev_event_hash": _normalize(prev_event_hash),
    }


def canonical_json(payload) -> str:
    """Return deterministic JSON representation."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256(text: str) -> str:
    """Return hex digest of text using SHA-256 (length 64)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
