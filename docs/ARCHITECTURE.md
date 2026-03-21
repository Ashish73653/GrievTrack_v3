# Architecture

## High-level flow
Citizen/Officer → Events DB → Canonical JSON → SHA256 → Ledger Backend (SQLite/Fabric Stub) → Auditor Verification → Dashboard

## Components
- **app.py**: Flask routes for submit, update, timeline, audit, benchmark, reset.
- **ledger_backend.py**: Ledger abstraction with SQLite backend and Fabric stub that also writes JSONL tx log (`fabric_stub/anchored_log.jsonl`).
- **db.py**: SQLite setup for three tables (complaints, complaint_events, ledger_hashes).
- **utils.py**: Canonical JSON helpers, IDs, hashing, timestamps.
- **templates/**: UI for submission, updates, timeline, audit, benchmark, dashboard.
- **fabric_stub/**: Pseudocode and sample payloads for future Fabric chaincode.

## Data structures
- Complaint: `complaint_id`, citizen fields, `priority`, `current_status`.
- Event: `event_id`, `complaint_id`, `event_type` (SUBMIT/ASSIGNED/IN_PROGRESS/CLOSED), `actor_id`, `remarks`, `timestamp`, `prev_event_hash`.
- Ledger anchor: `event_id`, `complaint_id`, `event_hash`, `timestamp`, optional `tx_id` (for stub).
- Audit result: per-event match status, chain status, EIS, CVL, OAI, audit timestamp.

## Canonicalization and hashing
1. Event payload normalized (sorted keys, consistent field order) via `canonical_event_payload` and `canonical_json`.
2. SHA256 digest computed over the canonical JSON.
3. `prev_event_hash` is `GENESIS` for the first event of a complaint; otherwise, the previous anchored hash.
4. Anchored hash stored in `ledger_hashes`; Fabric stub also writes to `fabric_stub/anchored_log.jsonl`.

## Verification loop
1. Fetch events for a complaint in order.
2. Recompute chain hash per event with expected `prev_event_hash`.
3. Compare to ledger anchor:
   - Match ⇒ `OK` (or `LEGACY` when previous-hash-less legacy hashes match).
   - Missing ⇒ `MISSING_LEDGER`, chain marked `BROKEN`.
   - Mismatch ⇒ `TAMPERED`, chain marked `BROKEN`.
4. Aggregate into EIS and record chain breakage.
5. Measure audit runtime per complaint to derive CVL.
6. Compute OAI based on ASSIGNED→IN_PROGRESS/CLOSED timing and SLA thresholds.

## Benchmark path
- Generates N complaints and M events each (caps enforced in code).
- Anchors every event, then audits chains to produce CVL vs total events chart.

## Swap-in ledger design
- `get_ledger_backend()` picks backend via `GRIEVTRACK_LEDGER_BACKEND`.
- To integrate Fabric, replace the stub with SDK calls that invoke chaincode functions `AnchorHash` and `GetHash`, preserving the canonical payload and prev-hash logic.
