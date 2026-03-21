# GrievTrack — Blockchain-ready grievance redressal with verifiable audit trail

Citizen grievance intake with chained hashes, tamper-evident audits, dashboard analytics, and a swap-in ledger backend that can target Hyperledger Fabric. Built for masters-level evaluation and demo defense.

## Key contributions
- Hash anchoring + chain verification for every complaint event
- Tamper detection across modify/delete/insert/reorder attempts
- Metrics: Event Integrity Score (EIS), Chain Verification Latency (CVL), Officer Accountability Index (OAI)
- Dashboard analytics with charts and audit summaries
- Fabric-stub ledger backend (swap-in design; `fabric_stub/anchored_log.jsonl`)
- Benchmark mode to compare CVL under synthetic load

## Quickstart
1) Create and activate a virtual environment (Python 3.10+ recommended).
2) Install dependencies:
```bash
pip install -r requirements.txt
```
3) Initialize the SQLite demo database (complaints, complaint_events, ledger_hashes):
```bash
python db.py
```
4) Run the app:
```bash
python app.py
```
5) Optional: switch ledger backend
```bash
export GRIEVTRACK_LEDGER_BACKEND=fabric_stub  # default is sqlite
```
- Codespaces note: forward port 5000 and use the public URL.
- Reproducibility: use **Reset** (type `RESET`) to clear complaints, events, ledger anchors, audit memory, and `fabric_stub/anchored_log.jsonl`. Benchmark via **Benchmark** to compare CVL under controlled N/M limits (caps: N ≤ 20, M ≤ 6).
- Docs quick links: [Demo script](docs/DEMO_SCRIPT.md), [Talk track](docs/THESIS_TALK_TRACK.md), [Architecture](docs/ARCHITECTURE.md), [Threat model](docs/THREAT_MODEL.md), [Metrics](docs/METRICS.md), [Screenshots checklist](docs/screenshots/README.md).

## Demo scenarios (teacher/panel script)
Use these three scripts live; emphasize the quoted lines to highlight design claims.

### Scenario 1: Happy Path End-to-End (Integrity 100%)
Steps: Submit → Update to ASSIGNED → IN_PROGRESS → CLOSED → view Timeline → run Audit Verify → open Dashboard.
Expected: EIS=100, chain status OK, OAI within SLA, dashboard shows counts/charts.
Panel-ready explanation (say this):
1. “Each event is canonicalized then hashed with the previous anchor; genesis uses `GENESIS`.”
2. “Hashes are anchored in SQLite (or Fabric stub) so off-chain edits are detectable.”
3. “Audit recomputes the chain and reports EIS; 100 means every off-chain event matches the ledger.”
4. “OAI checks if ASSIGNED→IN_PROGRESS/CLOSED met SLA; we’re within target.”
5. “Timeline shows immutable ordering; dashboard aggregates status and OAI.”
6. “This demonstrates the trusted baseline before any adversary action.”

### Scenario 2: Tamper Attack (Integrity Drop + Chain Broken)
Steps: Run Audit (expect EIS=100) → use Tamper helper to edit an event → rerun Audit.
Expected: event marked TAMPERED, chain broken flag true, EIS drops, forensic table shows mismatch.
Panel-ready explanation (say this):
1. “Assume an insider edits the off-chain DB directly.”
2. “Ledger still holds the anchored hash; recomputation now differs.”
3. “Prev-hash continuity check marks the chain BROKEN; this is chain-of-custody evidence.”
4. “EIS drops because matched events decreased; dashboard highlights the integrity issue.”
5. “This shows we detect modify/delete/insert/reorder, not just simple checksum errors.”

### Scenario 3: Performance/Evaluation (Benchmark)
Steps: Open Benchmark → set N ≤ 10 complaints, M ≤ 4 events each → run → view CVL trend chart.
Expected: chart of CVL vs total events, audit runtime printed.
Panel-ready explanation (say this):
1. “This is a scalability sanity check for thesis evaluation.”
2. “We synthesize N complaints with M events; each anchor is chained and then verified.”
3. “CVL measures ms to audit per complaint; lower is better.”
4. “We discuss how Fabric consensus would add latency but preserve ordering.”
5. “Use this to argue feasibility and to compare backends later.”

More verbose scripts live in `docs/DEMO_SCRIPT.md`.

## Research mapping (thesis alignment)
- Objective: **Tamper-evident grievance trail** → Features: canonical JSON hashing, ledger anchoring, `Audit` page, forensic table. Pages: Submit, Update, Timeline, Audit.
- Objective: **Officer accountability** → Features: OAI metric, SLA-aware status transitions. Pages: Update, Dashboard.
- Objective: **Performance under load** → Features: Benchmark harness, CVL metric chart. Pages: Benchmark, Dashboard.
- Objective: **Blockchain swap-in readiness** → Features: `fabric_stub` backend, ledger abstraction in `ledger_backend.py`, JSONL tx log. Files: `ledger_backend.py`, `fabric_stub/anchored_log.jsonl`, `fabric_stub/chaincode_pseudocode.txt`.

Formulas:
- `EIS = matched_events / (ledger_events + offchain_events) * 100`
- `CVL = audit_runtime_ms_per_complaint`
- `OAI = (within_sla / assigned * 100) - 2 * delayed`
SLA thresholds: HIGH/URGENT ≤ 24h, MEDIUM/NORMAL ≤ 7d, LOW ≤ 30d.

## Threat model coverage
- Modify → recomputed SHA256 ≠ anchored hash ⇒ status TAMPERED, chain BROKEN.
- Delete → ledger/off-chain mismatch or missing anchor ⇒ chain BROKEN, EIS drops.
- Insert/Reorder → prev-hash continuity check flags unexpected links.

## Attack Demonstrations (Auditor Lab)
| Attack | Expected detection signals |
| --- | --- |
| MODIFY_LATEST_REMARKS | Event status = TAMPERED, chain status BROKEN |
| DELETE_LATEST_EVENT (off-chain) | Missing off-chain entry → MISSING_OFFCHAIN status, chain BROKEN |
| DELETE_LEDGER_ANCHOR | Missing ledger anchor → MISSING_LEDGER status, chain BROKEN |
| INSERT_FAKE_EVENT | Unanchored event → MISSING_LEDGER status, EIS drops |
| REORDER_ATTACK | Timestamp order check → ORDER_ANOMALY status, chain BROKEN |

## Architecture
```
Citizen/Officer
    ↓
Events DB (complaints, complaint_events)
    ↓ canonical JSON
SHA256(prev_event_hash → chain)
    ↓
Ledger Backend (SQLite | Fabric Stub JSONL)
    ↓
Auditor Verification (EIS/CVL/OAI)
    ↓
Dashboard + Analytics
```

- Components: Flask app (`app.py`), SQLite DB (`complaints`, `complaint_events`, `ledger_hashes`), ledger abstraction (`ledger_backend.py`) with Fabric stub artifacts (`fabric_stub/anchored_log.jsonl`, `fabric_stub/chaincode_pseudocode.txt`), templates under `templates/`.
- Data: canonical event payload includes `complaint_id`, `event_id`, `event_type`, `actor_id`, `remarks`, `timestamp`, `prev_event_hash`.
- Auditor recomputes hashes, compares to ledger, emits EIS/CVL/OAI and chain status.
See `docs/ARCHITECTURE.md` for details.

## Hyperledger roadmap
- Current stub: `GRIEVTRACK_LEDGER_BACKEND=fabric_stub` writes append-only JSONL tx log (`fabric_stub/anchored_log.jsonl`) while still persisting to SQLite.
- For real Fabric: implement chaincode functions `AnchorHash` and `GetHash`, wire client invocations inside `ledger_backend.py` (Fabric client), and route anchors via Fabric SDK.
- Additional steps: enroll org peers, define endorsement policy, and persist tx IDs for audit reproducibility.
- Reference pseudocode: `fabric_stub/chaincode_pseudocode.txt` sketches the Fabric chaincode shape.

## Limitations
- 3-table constraint: audit history is in-memory per session (not persisted).
- Prototype auth only; full RBAC/JWT and signed audit reports are future work.
- Fabric is stubbed; no consensus or MSP enrollment in this prototype.

## Future work
- Integrate with Hyperledger Fabric test network and chaincode (`AnchorHash`, `GetHash`).
- Add RBAC/JWT, officer signing, and auditable receipts.
- Encrypt sensitive fields off-chain with key rotation.
- Simulate multi-org endorsement policies and ordering service latency.
- Notification system (email/SMS) for status changes and SLA warnings.
- Docker Compose + CI pipeline for reproducible deployments.
- Data retention and GDPR-like deletion/anonymization policies.

## License + citation
MIT License (see `LICENSE`).

Citation for thesis usage:
```bibtex
@software{grievtrack2026,
  title={GrievTrack: Blockchain-ready grievance redressal with verifiable audit trail},
  author={Project Team},
  year={2026},
  url={https://github.com/Ashish73653/GrievTrack_v3}
}
```
