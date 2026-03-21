# GrievTrack Demo Script (Panel-Ready)

Use this script for a 10–12 minute live demo. Keep browser tabs open for Submit, Update, Timeline, Audit, Benchmark, and Dashboard.

## Scenario 1: Happy Path End-to-End (Integrity 100%)
**Goal:** Show trusted baseline with perfect integrity and SLA-respecting handling.

1. Open **Submit** and file a complaint (e.g., priority HIGH). Note the receipt and complaint ID.
2. Go to **Update** and move the complaint through **ASSIGNED → IN_PROGRESS → CLOSED**, adding short remarks.
3. Open **Timeline** for the complaint. Point out the ordered events and their anchored hashes.
4. Run **Audit** for the complaint. Expect `EIS=100`, `chain_status=OK`, no tamper flags.
5. Visit **Dashboard** to show counts, recent audits, OAI status, and charts.

What to say (script):
- “Each event is canonicalized and hashed with the previous anchor (`prev_event_hash`), starting with `GENESIS`.”
- “Anchors land in SQLite (or Fabric stub), giving us a tamper-evident trail.”
- “Audit recomputes every hash; 100 EIS means complete agreement between off-chain events and ledger anchors.”
- “OAI confirms we met the SLA for the ASSIGNED→IN_PROGRESS/CLOSED transition.”
- “Dashboard aggregates status, OAI, and audit results for supervisors.”

## Scenario 2: Tamper Attack (Integrity Drop + Chain Broken)
**Goal:** Show forensic evidence when the off-chain database is altered.

1. Run **Audit** first; show `EIS=100` to establish baseline.
2. Use the **Tamper** helper (or directly edit via provided form) to modify an event remark or status.
3. Rerun **Audit** for the same complaint.
4. Observe `TAMPERED` on the altered event, `chain_status=BROKEN`, EIS reduced, and mismatched hashes in the forensic table.

What to say (script):
- “Assume an insider edits the off-chain row; the ledger anchor remains unchanged.”
- “Recomputed SHA256 now differs from the anchored hash, so we mark it TAMPERED.”
- “Prev-hash continuity check shows the chain is broken—evidence for chain-of-custody.”
- “EIS drops because matched events decreased; dashboard highlights the integrity regression.”
- “This covers modify/delete/insert/reorder, not just single-row changes.”

## Scenario 3: Performance/Evaluation (Benchmark)
**Goal:** Show evaluation mode and CVL metric under load.

1. Open **Benchmark**.
2. Choose `N` complaints ≤ 10 and `M` events each ≤ 4; run the benchmark.
3. Point to the printed audit runtime and the CVL chart (CVL vs total events).
4. Optionally repeat with different N/M to show trend stability.

What to say (script):
- “Benchmark synthesizes events, anchors them, then audits the chains.”
- “CVL is the milliseconds to verify a complaint chain; we track how it scales with load.”
- “Fabric consensus would add latency, but the chain verification logic stays identical.”
- “Use this to report feasibility and as a baseline before plugging in Fabric.”
