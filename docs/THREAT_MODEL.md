# Threat Model

## Assets
- Integrity of complaint events and their ordering.
- Audit evidence (EIS, chain status, forensic hash table).
- Ledger anchors (SQLite or Fabric stub JSONL).

## Adversaries
- Insider with direct DB access attempting covert edits.
- Network observer attempting to replay or reorder events (mitigated by server-side hashing).

## Attack vectors and detection
- **Modify existing event**: Off-chain row edited. Detection: recomputed SHA256 ≠ anchored hash ⇒ event marked `TAMPERED`, chain `BROKEN`.
- **Delete event or ledger row**: Missing anchor or off-chain row. Detection: audit sees absent counterpart; chain marked `BROKEN`, EIS drops.
- **Insert/Reorder events**: Unexpected `prev_event_hash`. Detection: continuity check fails; chain `BROKEN`, forensic table highlights unexpected links.
- **Backend swap risk**: Unsupported ledger backend. Mitigation: `get_ledger_backend` validates allowed choices; default is SQLite.
- **SLA evasion**: Officer delays updates. Detection: OAI flags `DELAYED` when ASSIGNED→IN_PROGRESS/CLOSED exceeds thresholds.

## Mitigations and coverage
- Canonical JSON + prev-hash chaining prevents silent reordering.
- Anchoring hashes in ledger decouples evidence from mutable app DB.
- Audit page recomputes hashes and records history (session memory) for repeatability.
- Dashboard surfaces integrity status and recent audits for oversight.

## Gaps and assumptions
- Audit history is stored in memory for the running process (not yet persisted).
- Authentication/authorization is minimal; RBAC/JWT is future work.
- Fabric consensus and MSP enrollment are not included in the stub.
