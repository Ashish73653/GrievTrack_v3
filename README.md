# GrievTrack — Blockchain-ready grievance redressal with verifiable audit trail

Citizen grievance intake with chained hashes, tamper-evident audits, dashboard analytics, and a swap-in ledger backend that can target Hyperledger Fabric. Built for masters-level evaluation and demo defense.

## Key contributions
- Hash anchoring + chain verification for every complaint event
- Tamper detection across modify/delete/insert/reorder attempts
- Metrics: Event Integrity Score (EIS), Chain Verification Latency (CVL), Officer Accountability Index (OAI)
- Dashboard analytics with charts and audit summaries
- Fabric-stub ledger backend (swap-in design; `fabric_stub/anchored_log.jsonl`)
- Benchmark mode to compare CVL under synthetic load

## Teacher Demo Script (10–12 minutes)

Scenario A — Quick Start (Professional overview)
1) Navbar → Dashboard → Actions ▾ → **Seed demo data**.  
   - What you will see: toast/redirect confirmation, dashboard badge shows “Demo dataset loaded”, charts fill in with seeded values (≈10 complaints, EIS ~100%, CVL in low hundreds ms).  
   - What to explain: deterministic seed, idempotent; curated tamper + missing-ledger examples light up integrity and OAI charts instantly.  
2) Stay on **Dashboard**.  
   - What you will see: KPI cards (complaints, integrity events, OAI, audit performance, TRT), integrity pie, OAI histogram, CVL history.  
   - What to explain: “These are computed live from our 3-table model and anchored ledger hashes; the dashboard recomputes from DB + ledger on every load.”  

Scenario B — End-to-End workflow (Citizen → Officer → Traceability)
1) Navbar → **Submit** → click “Submit new grievance” (use sample values or Seeded IDs).  
   - What you will see: receipt panel with `complaint_id`, `event_hash`, and backend/`tx_id`.  
   - What to explain: “This is the anchored cryptographic receipt; prev_hash = GENESIS for the first event.”  
2) Navbar → **Update** → add `ASSIGNED`, then `IN_PROGRESS`, then `CLOSED`.  
   - What you will see: status confirmations; hashes chain to the previous ledger hash.  
   - What to explain: “Every update appends a new canonical JSON event and anchors the chained hash.”  
3) Navbar → **Timeline** → paste the `complaint_id` → **Load timeline**.  
   - What you will see: ordered event history with hashes and status badges.  
   - What to explain: “Traceability—every event is ordered, hashed, and anchored; gaps would show as missing anchors.”  

Scenario C — Audit + Attack proof (Integrity drop)
1) Navbar → **Audit** → paste the same `complaint_id` → **Verify**.  
   - What you will see: EIS near 100%, CVL near prior run, chain status OK/LEGACY.  
   - What to explain: “Audit recomputes canonical JSON hashes and compares them to ledger anchors.”  
2) Click **Simulate Tamper** (or Navbar → More ▾ → **Attacks**) and run one attack.  
   - What you will see: ledger/off-chain mismatch banners, table rows marked TAMPERED/MISSING.  
   - What to explain: “We intentionally break one link; anchored vs recomputed hashes now diverge.”  
3) Click **Verify** again.  
   - What you will see: EIS drops, chain status BROKEN, missing-ledger/off-chain badges.  
   - What to explain: “Mismatch appears immediately; integrity score quantifies damage. Download JSON report as evidence.”  

Scenario D — Research evaluation (optional, 2–3 min)
1) Navbar → More ▾ → **Benchmark** (use small values N ≤ 10, M ≤ 4).  
   - What you will see: CVL vs events chart for synthetic runs.  
   - What to explain: “We measure verification latency under increasing load; curves align with Dashboard research charts.”  
2) Reference Dashboard research tiles (Integrity breakdown, OAI histogram, CVL history).  
   - What you will see: seeded slices/bars; CVL history line.  
   - What to explain: “These are computed with the same formulas as Audit—EIS, CVL, OAI—anchored to ledger hashes.”  

## What to say in 30 seconds (elevator pitch)
- Problem: grievances and officer updates get lost or altered; auditors need verifiable trails.  
- Approach: canonical JSON payloads, chained SHA256, and a swap-in ledger backend anchor every event.  
- Metrics: EIS (integrity %), CVL (verification latency), OAI (officer accountability), TRT (resolution speed).  
- Demo proof: submit → update → audit → tamper; EIS stays ~100% until tamper, then drops and flags missing anchors; JSON report is downloadable evidence.  
- Roadmap: plug into Hyperledger Fabric (same APIs), add signed receipts/RBAC, keep the 3-table core stable.  

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

## Recommended demo workflow (10 minutes)
1) **Seed demo data (Seed page)** — loads curated complaints with SLA variety, one tamper, and a missing-ledger follow-up so every chart lights up.  
2) **Dashboard overview** — call out summary tiles plus chart captions (integrity breakdown, OAI histogram, TRT by priority, EIS/CVL trends).  
3) **Pick a complaint** — from the dashboard/timeline, copy a complaint_id (deterministic SEED-CMP IDs available).  
4) **Audit verify** — paste the ID, run Verify; read EIS/CVL/OAI/ACI and chain status.  
5) **Tamper/Attacks demo** — click Simulate tamper or open Attacks; optionally delete/insert to mimic missing ledger/off-chain anchors.  
6) **Re-run audit** — show EIS drop, BROKEN chain, and status breakdown table; download JSON to prove it.  
7) **Benchmark (small run)** — run within caps (e.g., N=5, M=3); interpret CVL vs events slope using the caption and relate to research charts.

## Demo scenarios
### Scenario 1: Happy path (EIS = 100, chain OK, SLA within)
- Submit a new complaint (or use Seeded), update through ASSIGNED → IN_PROGRESS → CLOSED, then Audit it.  
- Point out EIS 100, chain status OK/LEGACY, ACI anchored, and TRT within SLA; dashboard charts stay green.  
- Talk track: deterministic payloads chained from GENESIS keep hashes stable and make receipts verifiable.

### Scenario 2: Tamper/attack (EIS drops, chain broken, missing flagged)
- In Audit, choose a complaint → Simulate tamper → Verify again.  
- Call out TAMPERED rows, missing ledger/off-chain badges, BROKEN chain, EIS drop, and SLA/OAI impact.  
- Download JSON export and copy hashes to show exact divergence; relate to Status Legend colors.

### Scenario 3: Scalability (benchmark + simulated research graphs)
- Run Benchmark with a small N/M to plot CVL vs total events (capped); look for slope/ outliers.  
- Open Simulation Lab and generate Small/Medium to explain modeled CVL log-scale and EIS vs tamper curves.  
- Tie back to Dashboard research tiles to show why the paper-style charts align with live metrics.

## What to explain to the panel (talk track)
- **Canonical payload + deterministic hashing:** canonical JSON → SHA256(prev_hash → chain), GENESIS for first link.  
- **Anchoring backend + fabric_stub log:** sqlite backend by default, swap-in Fabric via `GRIEVTRACK_LEDGER_BACKEND`; anchored transactions mirrored at `fabric_stub/anchored_log.jsonl`.  
- **Chain validation + deletion/insertion detection:** recompute hashes, check prev_hash continuity, and flag missing ledger/off-chain to detect modify/delete/insert/reorder attempts.  
- **Metrics definitions:** EIS (integrity%), CVL (verify latency ms), OAI (accountability), ACI (anchoring completeness anchored/total × 100), TRT (submit → closed hours).  
- **Why charts match research:** dashboard tiles use live ledger/event scans; Simulation Lab uses modeled curves anchored on the same metric formulas for defense talking points.

## Common questions & answers
- **Why not real Fabric?** Modular backend keeps Fabric optional; the stub mimics ledger anchoring and writes to JSONL. Roadmap: plug Fabric client + chaincode (`AnchorHash`, `GetHash`) without changing the app surface.  
- **Why no audit history table?** Design is constrained to 3 tables; audit runs live in session memory and exportable JSON. Use Reset to clear, Benchmark/Simulation Lab for reproducible reruns.

## Getting good graphs quickly
- Use **Seed demo data** (`/seed`) to append a curated dataset: 10 complaints across Infrastructure/Sanitation/Water/Safety/Electricity, officers OFF001–OFF005, realistic SLA timings (within + delayed), plus a tampered event and one missing-ledger follow-up so integrity charts are not flat.
- The dashboard shows a prompt when empty—click **Seed demo data** to light up charts and tables immediately. Demo badge appears while seeded data is present (citizen IDs prefixed `demo-`).
- Reset wipes everything: complaints, complaint_events, ledger_hashes, in-memory histories (audit/research/benchmark), and the Fabric stub log at `fabric_stub/anchored_log.jsonl`.
- Seed is idempotent: pressing the Seed button repeatedly will not duplicate rows (deterministic IDs `SEED-CMP-001...`).
- The seed page surfaces an “already present” banner with counts on a second run; use **Go to dashboard** from there.
- Reset clears the seeded rows, ledger anchors, anchored log, and in-memory audit/research/benchmark runs in one click.
- Seed payload keeps the tampered and missing-ledger examples so audit charts are never empty.
- Audit JSON export stays aligned with the on-screen table; hashes are copyable for inspectors.

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
