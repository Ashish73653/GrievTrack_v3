# Metrics

## Event Integrity Score (EIS)
- **Definition:** `matched_events / (ledger_events + offchain_events) * 100`.
- **Interpretation:** 100 means every off-chain event matches a ledger anchor and chain continuity holds. Drops on missing anchors, tamper, or chain breaks.
- **Example:** If 5 events exist off-chain and 5 anchors exist, but 1 hash mismatch occurs, `EIS = 9 / 10 * 100 = 90`.

## Chain Verification Latency (CVL)
- **Definition:** Milliseconds to verify a single complaint’s event chain (audit runtime per complaint).
- **Interpretation:** Lower is better; used to compare backends or load scenarios.
- **Example:** Benchmark with N=5, M=3 reports total audit time 45 ms ⇒ `CVL ≈ 45 / 5 = 9 ms per complaint`.

## Officer Accountability Index (OAI)
- **Definition:** `(within_sla / assigned * 100) - 2 * delayed`, where `within_sla` counts ASSIGNED→IN_PROGRESS/CLOSED transitions inside SLA thresholds.
- **SLA thresholds:** HIGH/URGENT ≤ 24h; MEDIUM/NORMAL ≤ 7d; LOW ≤ 30d.
- **Example:** 4 complaints assigned, 3 within SLA, 1 delayed ⇒ `OAI = (3/4*100) - 2*1 = 75 - 2 = 73`.

## How to report in a thesis
- Include EIS before/after tamper to show integrity drop (e.g., 100 → 60).
- Plot CVL vs total events from the Benchmark page to show scalability.
- Present OAI over time to demonstrate accountability improvements after process changes.
