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

## UI walkthrough scenarios (what to click + what to say)
Script these three in order; they line up with the dashboard, audit, and research visuals.

### Scenario 1: Happy path demo (submit → update → timeline → audit → dashboard)
1. Click **Submit** → fill fields (or use “Use sample demo values”) → submit.
2. Click **Update** → paste complaint_id → set ASSIGNED → IN_PROGRESS → CLOSED.
3. Open **Timeline** with the same complaint_id to show chained events.
4. Run **Audit** → Verify to show EIS 100, chain status OK, ACI anchored, TRT value, and copy the complaint_id.
5. Go to **Dashboard** → point at Research Analytics cards (integrity breakdown, OAI histogram, TRT by priority, CVL history).
Explain: “Each event is canonicalized and chained to the previous hash (GENESIS for first), anchored in the ledger backend; Audit recomputes and proves immutability while dashboard rolls up integrity and accountability.”

### Scenario 2: Tamper detection demo (audit → simulate tamper → verify)
1. In **Audit**, enter complaint_id → click **Simulate tamper**.
2. Click **Verify** again.
3. Call out the Metric Engine: EIS drop, chain status BROKEN, tampered count, missing counts, and SLA violations (if any).
4. Scroll to the verification table: TAMPERED badge, recomputed hash vs ledger hash, copy hashes with the clipboard buttons.
5. Download JSON to show the new export payload including status counts, ACI, and chart data.
Explain: “Off-chain edits diverge from the anchored hash, so recomputation flags TAMPERED; prev-hash continuity breaks, and the report records the exact mismatch counts.”

### Scenario 3: Research graphs demo (/research simulation lab)
1. Click **Simulation Lab** (navbar) → pick Small/Medium → **Generate simulation**.
2. Narrate the two plots: CVL scalability on log scale (anchored vs pure cloud) and EIS vs tamper rate (anchored degrades slower).
3. Scroll to run history showing capped event arrays and modeled seconds; export JSON to demonstrate non-persistent research runs.
4. Return to **Dashboard** to relate Research Analytics (integrity breakdown, OAI histogram, TRT by priority, CVL history) back to live data.
Explain: “These are deterministic, capped simulations modeled from the current CVL baseline—paper-style visuals without mutating the DB schema.”

## What to explain to the panel
- Canonical hashing: payload → deterministic JSON → SHA256(prev_hash → chain), GENESIS for first link.
- Ledger anchoring: anchored via sqlite backend or Fabric stub JSONL; tx log lives in `fabric_stub/anchored_log.jsonl`.
- Chain verification: recompute hashes + prev_hash continuity to mimic blockchain immutability; chain_status shows OK/BROKEN/LEGACY.
- Metrics: EIS (integrity%), CVL (verify latency ms), OAI (accountability), ACI (anchoring completeness anchored/total × 100).
- Research simulations: CVL scalability and EIS vs tamper are modeled (not DB-heavy), bounded arrays for speed; dashboard research charts use live complaint/ledger scans.

## Screenshot checklist
- Dashboard: summary tiles + Research Analytics quad (integrity pie/bar, OAI histogram, TRT by priority, CVL history).
- Audit: Metric Engine strip, Audit Report Dashboard counts, verification table with copy-to-clipboard hashes.
- Research: Simulation Lab with CVL log plot, EIS vs tamper plot, and run history table.

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
