# Thesis Talk Track (Slide-by-Slide)

Use this outline for a 12–15 minute defense or committee presentation.

1) **Problem & Motivation**
- Citizens need tamper-evident grievance handling; current systems allow silent edits.
- Thesis hypothesis: chained hashing + ledger anchoring improves trust and accountability.

2) **Contributions**
- GrievTrack app with canonicalized event hashing and ledger anchoring.
- Tamper detection for modify/delete/insert/reorder.
- Metrics: EIS, CVL, OAI; dashboard and benchmark harness.
- Fabric-ready backend abstraction.

3) **System Overview**
- Show ASCII pipeline from README.
- Emphasize canonical JSON, SHA256, ledger abstraction, and auditor loop.

4) **Data Model & Flows**
- Three tables: complaints, complaint_events, ledger_hashes.
- Event payload fields: complaint_id, event_id, event_type, actor_id, remarks, timestamp, prev_event_hash.
- Submission → hashing → anchoring → verification → dashboard loop.

5) **Metrics**
- EIS formula and interpretation (drops on tamper/missing/chain break).
- CVL definition (ms per complaint to verify chain).
- OAI definition, SLA thresholds (HIGH/URGENT 24h, MEDIUM/NORMAL 7d, LOW 30d).

6) **Threat Model**
- Modify: hash mismatch ⇒ TAMPERED.
- Delete: missing anchor/off-chain ⇒ chain broken.
- Insert/Reorder: prev-hash continuity check fails.
- Mention forensic table in Audit.

7) **Demo Map**
- Scenario 1: Happy path baseline (EIS=100, OAI within SLA).
- Scenario 2: Tamper attack shows chain break evidence.
- Scenario 3: Benchmark shows CVL trend.

8) **Results & Observations**
- Integrity preserved in baseline, EIS drop on tamper.
- CVL scales linearly for N≤10, M≤4 (demo bounds).
- Dashboard aids supervisor awareness.

9) **Hyperledger Fabric Roadmap**
- Current stub: JSONL tx log, same hashing path.
- Future: chaincode (`AnchorHash`, `GetHash`), endorsement policy, client invoke.

10) **Limitations**
- In-memory audit history; prototype auth only.
- Fabric consensus not included.

11) **Future Work**
- RBAC/JWT + signed receipts, off-chain encryption.
- Multi-org simulation, Docker Compose + CI, data retention policies.

12) **Call to Action**
- Invite code review, reproducibility checks, and Fabric test-network collaboration.
