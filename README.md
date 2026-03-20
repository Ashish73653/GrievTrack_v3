# GrievTrack_v3

Minimal Flask scaffold for GrievTrack with anchored complaint events, integrity audits, and benchmarking.

## Setup
1. Create and activate a virtual environment (Python 3.10+ recommended).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Initialize the database:
   ```bash
   python db.py
   ```
4. (Optional) Choose ledger backend by setting `GRIEVTRACK_LEDGER_BACKEND`:
   - `sqlite` (default): hashes anchored locally into `ledger_hashes`.
   - `fabric_stub`: also writes an append-only log to `fabric_stub/anchored_log.jsonl` to mimic a blockchain submission.

## Run
```bash
python app.py
```
Open http://127.0.0.1:5000/ in your browser. The root path redirects to the dashboard.

## 2-minute demo flow
1. Submit a complaint via **Submit** (stores complaint + SUBMIT event, anchors hash, returns receipt).
2. Progress the case in **Update** (ASSIGNED/IN_PROGRESS/CLOSED events anchor hashes and update status).
3. Inspect ordering/hashes in **Timeline**.
4. Verify integrity in **Audit**; use Tamper to see chain break detection and audit history.
5. Generate synthetic load in **Benchmark** (caps: N ≤ 20 complaints, M ≤ 6 events each) to view CVL vs total events.
6. Use **Reset** (type `RESET`) to clear complaints, events, ledger hashes, audit memory, and Fabric stub logs.

## Metrics
- **EIS (Event Integrity Score)**: `matched / (ledger + off-chain events)` × 100. Drops on tamper, missing ledger entries, or chain breaks.
- **CVL (Chain Verification Latency)**: Milliseconds to verify a complaint’s chain against anchored hashes.
- **OAI (Officer Accountability Index)**: `(within_sla / assigned × 100) - 2 × delayed`; SLA window depends on priority (HIGH/URGENT: 24h, MEDIUM/NORMAL: 7d, LOW: 30d).

## Fabric stub and ledger backend
- `GRIEVTRACK_LEDGER_BACKEND=fabric_stub` appends every anchor to `fabric_stub/anchored_log.jsonl` while still recording hashes in SQLite for verification.
- Leave unset or set to `sqlite` to keep everything local to the database.

## Threat model coverage
Integrity verification detects:
- **Modify**: Hash mismatches mark events as `TAMPERED`.
- **Delete**: Missing off-chain or ledger entries flagged; chain status becomes `BROKEN`.
- **Insert/Reorder**: Prev-hash chain validation catches unexpected links and order changes.
