import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, redirect, render_template, request, url_for, Response

from db import get_db
from ledger_backend import get_ledger_backend
from utils import (
    canonical_event_payload,
    canonical_json,
    new_complaint_id,
    new_event_id,
    now_iso,
    sha256,
)


app = Flask(__name__)
AUDIT_HISTORY: List[Dict] = []
MAX_BENCHMARK_COMPLAINTS = 20
MAX_BENCHMARK_EVENTS = 6


def _fabric_log_path() -> Path:
    return Path(__file__).resolve().parent / "fabric_stub" / "anchored_log.jsonl"


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _sla_hours_for_priority(priority: str) -> int:
    normalized = (priority or "").upper()
    if normalized in {"HIGH", "URGENT"}:
        return 24
    if normalized in {"MEDIUM", "NORMAL"}:
        return 24 * 7
    if normalized in {"LOW", "NON-URGENT"}:
        return 24 * 30
    return 24 * 7


def _compute_oai(complaint: Dict, events: List) -> Dict:
    assigned_at = None
    in_progress_at = None
    closed_at = None

    for event in events:
        if event["event_type"] == "ASSIGNED" and not assigned_at:
            assigned_at = event["timestamp"]
        if event["event_type"] == "IN_PROGRESS" and not in_progress_at:
            in_progress_at = event["timestamp"]
        if event["event_type"] == "CLOSED" and not closed_at:
            closed_at = event["timestamp"]

    if not assigned_at:
        return {"status": "INSUFFICIENT_DATA", "details": "No ASSIGNED event"}

    transition_at = in_progress_at or closed_at
    if not transition_at:
        return {"status": "INSUFFICIENT_DATA", "details": "Awaiting IN_PROGRESS or CLOSED"}

    assigned_dt = _parse_iso(assigned_at)
    transition_dt = _parse_iso(transition_at)
    if not assigned_dt or not transition_dt:
        return {"status": "INSUFFICIENT_DATA", "details": "Unparseable timestamps"}

    duration = transition_dt - assigned_dt
    sla_hours = _sla_hours_for_priority(complaint.get("priority", ""))
    within_sla = duration <= timedelta(hours=sla_hours)
    return {
        "status": "WITHIN_SLA" if within_sla else "DELAYED",
        "assigned_at": assigned_at,
        "transition_at": transition_at,
        "duration_hours": round(duration.total_seconds() / 3600, 2),
        "sla_hours": sla_hours,
    }


def _compute_trt(events: List[Dict]) -> Optional[float]:
    submit_ts = None
    closed_ts = None
    for event in events:
        if event["event_type"] == "SUBMIT" and not submit_ts:
            submit_ts = _parse_iso(event["timestamp"])
        if event["event_type"] in {"CLOSED", "RESOLVED"} and not closed_ts:
            closed_ts = _parse_iso(event["timestamp"])
        if submit_ts and closed_ts:
            break

    if not submit_ts or not closed_ts:
        return None
    if closed_ts < submit_ts:
        return None
    delta = closed_ts - submit_ts
    return round(delta.total_seconds() / 3600, 2)


def _compute_aci(events: List[Dict], ledger_map: Dict[str, str]) -> Dict:
    total = len(events)
    anchored = sum(1 for event in events if event["event_id"] in ledger_map)
    score = round((anchored / total) * 100, 2) if total else 0.0
    return {"score": score, "anchored": anchored, "total": total}


def _latest_ledger_hash(cursor, complaint_id: str) -> Optional[str]:
    row = cursor.execute(
        """
        SELECT event_hash
        FROM ledger_hashes
        WHERE complaint_id = ?
        ORDER BY timestamp DESC, ledger_id DESC
        LIMIT 1
        """,
        (complaint_id,),
    ).fetchone()
    return row["event_hash"] if row else None


def _verify_events_against_ledger(
    events: List[Dict], ledger_by_event: Dict[str, str], complaint_id: Optional[str] = None
) -> Dict:
    prev_anchor_hash: Optional[str] = None
    matched_count = 0
    chain_broken = False
    event_results = []
    order_anomalies = 0
    prev_ts: Optional[datetime] = None

    for event in events:
        event_dict = dict(event)
        cid = event_dict.get("complaint_id") or complaint_id or ""
        ledger_hash = ledger_by_event.get(event_dict["event_id"])
        expected_prev = prev_anchor_hash or "GENESIS"
        current_ts = _parse_iso(event_dict.get("timestamp"))
        out_of_order = bool(prev_ts and current_ts and current_ts < prev_ts)

        chain_payload = canonical_event_payload(
            complaint_id=cid,
            event_id=event_dict["event_id"],
            event_type=event_dict["event_type"],
            actor_id=event_dict["actor_id"],
            remarks=event_dict["remarks"],
            timestamp=event_dict["timestamp"],
            prev_event_hash=expected_prev,
        )
        chain_hash = sha256(canonical_json(chain_payload))

        legacy_payload = canonical_event_payload(
            complaint_id=cid,
            event_id=event_dict["event_id"],
            event_type=event_dict["event_type"],
            actor_id=event_dict["actor_id"],
            remarks=event_dict["remarks"],
            timestamp=event_dict["timestamp"],
            prev_event_hash="",
        )
        legacy_hash = sha256(canonical_json(legacy_payload))

        if ledger_hash is None:
            status = "MISSING_LEDGER"
            chain_status = "BROKEN"
            recomputed_hash = chain_hash
            chain_broken = True
        elif out_of_order:
            status = "ORDER_ANOMALY"
            chain_status = "BROKEN"
            recomputed_hash = chain_hash
            chain_broken = True
            order_anomalies += 1
        elif ledger_hash == chain_hash:
            status = "MATCH"
            chain_status = "OK"
            recomputed_hash = chain_hash
            matched_count += 1
        elif ledger_hash == legacy_hash:
            status = "MATCH"
            chain_status = "LEGACY"
            recomputed_hash = legacy_hash
            matched_count += 1
        else:
            status = "TAMPERED"
            chain_status = "BROKEN"
            recomputed_hash = chain_hash
            chain_broken = True

        if ledger_hash:
            prev_anchor_hash = ledger_hash
        prev_ts = current_ts or prev_ts

        event_results.append(
            {
                "event_id": event_dict["event_id"],
                "event_type": event_dict["event_type"],
                "actor_id": event_dict["actor_id"],
                "remarks": event_dict["remarks"],
                "timestamp": event_dict["timestamp"],
                "ledger_hash": ledger_hash or "",
                "recomputed_hash": recomputed_hash,
                "status": status,
                "chain_status": chain_status,
                "expected_prev_event_hash": expected_prev,
            }
        )

    return {
        "events": event_results,
        "matched": matched_count,
        "chain_broken": chain_broken,
        "order_anomalies": order_anomalies,
    }


def _build_dashboard_data() -> Dict:
    with get_db() as conn:
        cursor = conn.cursor()
        complaints = cursor.execute("SELECT * FROM complaints").fetchall()
        events = cursor.execute(
            """
            SELECT complaint_id, event_id, event_type, actor_id, remarks, timestamp
            FROM complaint_events
            ORDER BY complaint_id ASC, rowid ASC
            """
        ).fetchall()
        ledger_rows = cursor.execute(
            """
            SELECT complaint_id, event_id, event_hash, timestamp
            FROM ledger_hashes
            """
        ).fetchall()

    events_by_complaint: Dict[str, List[Dict]] = defaultdict(list)
    for event in events:
        events_by_complaint[event["complaint_id"]].append(dict(event))

    ledger_by_complaint: Dict[str, Dict[str, str]] = defaultdict(dict)
    for row in ledger_rows:
        ledger_by_complaint[row["complaint_id"]][row["event_id"]] = row["event_hash"]

    total_complaints = len(complaints)
    closed_statuses = {"CLOSED", "RESOLVED"}
    closed_count = sum(
        1
        for complaint in complaints
        if (complaint["current_status"] or "").upper() in closed_statuses
    )
    open_count = total_complaints - closed_count

    tampered_events = 0
    matched_events = 0
    total_events = 0
    missing_offchain_total = 0
    delayed_complaints = 0
    response_hours_total = 0.0
    response_samples = 0
    trt_hours_total = 0.0
    trt_samples = 0
    priority_trt: Dict[str, Dict[str, float]] = defaultdict(lambda: {"total": 0.0, "count": 0})
    global_status_counts: Dict[str, int] = defaultdict(int)
    aci_scores: List[float] = []
    officer_stats: Dict[str, Dict] = {}

    for complaint in complaints:
        complaint_dict = dict(complaint)
        cid = complaint_dict["complaint_id"]
        complaint_events = events_by_complaint.get(cid, [])
        ledger_map = ledger_by_complaint.get(cid, {})

        event_ids = {event["event_id"] for event in complaint_events}
        missing_offchain = [eid for eid in ledger_map.keys() if eid not in event_ids]
        missing_offchain_total += len(missing_offchain)

        verification = _verify_events_against_ledger(
            complaint_events, ledger_map, complaint_id=cid
        )
        total_events += len(complaint_events)
        matched_events += verification["matched"]
        status_counts = defaultdict(int)
        for event in verification["events"]:
            status_counts[event["status"]] += 1
        tampered_events += status_counts.get("TAMPERED", 0)
        status_counts["MISSING_OFFCHAIN"] += len(missing_offchain)
        for status, count in status_counts.items():
            global_status_counts[status] += count

        oai = _compute_oai(complaint_dict, complaint_events)
        if oai.get("status") == "DELAYED":
            delayed_complaints += 1
        if oai.get("status") in {"WITHIN_SLA", "DELAYED"} and "duration_hours" in oai:
            response_hours_total += oai["duration_hours"]
            response_samples += 1

        aci = _compute_aci(complaint_events, ledger_map)
        aci_scores.append(aci["score"])

        trt_hours = _compute_trt(complaint_events)
        if trt_hours is not None:
            trt_hours_total += trt_hours
            trt_samples += 1
            priority_key = (complaint_dict.get("priority") or "UNSPECIFIED").upper()
            priority_stats = priority_trt[priority_key]
            priority_stats["total"] += trt_hours
            priority_stats["count"] += 1

        officer_id = None
        for event in complaint_events:
            if event["event_type"] == "ASSIGNED" and event["actor_id"]:
                officer_id = event["actor_id"]
                break
        if not officer_id:
            for event in complaint_events:
                if event["event_type"] != "SUBMIT" and event["actor_id"]:
                    officer_id = event["actor_id"]
                    break

        if officer_id:
            stats = officer_stats.setdefault(
                officer_id,
                {
                    "assigned_count": 0,
                    "within_sla_count": 0,
                    "delayed_count": 0,
                    "total_hours": 0.0,
                    "duration_samples": 0,
                },
            )
            stats["assigned_count"] += 1
            if oai.get("status") == "WITHIN_SLA":
                stats["within_sla_count"] += 1
            if oai.get("status") == "DELAYED":
                stats["delayed_count"] += 1
            if oai.get("status") in {"WITHIN_SLA", "DELAYED"} and "duration_hours" in oai:
                stats["total_hours"] += oai["duration_hours"]
                stats["duration_samples"] += 1

    integrity_events = total_events + missing_offchain_total
    global_eis = (
        round((matched_events / integrity_events) * 100, 2) if integrity_events else 0.0
    )

    officer_rows = []
    for officer_id, stats in sorted(officer_stats.items()):
        avg_hours = (
            round(stats["total_hours"] / stats["duration_samples"], 2)
            if stats["duration_samples"]
            else 0.0
        )
        oai_score = (
            round((stats["within_sla_count"] / stats["assigned_count"]) * 100, 2)
            - (2 * stats["delayed_count"])
            if stats["assigned_count"]
            else 0.0
        )
        officer_rows.append(
            {
                "officer_id": officer_id,
                "assigned_count": stats["assigned_count"],
                "within_sla_count": stats["within_sla_count"],
                "delayed_count": stats["delayed_count"],
                "avg_response_hours": avg_hours,
                "oai_score": round(oai_score, 2),
            }
        )

    cvl_values = [
        run.get("summary", {}).get("cvl_ms", 0) for run in AUDIT_HISTORY if run.get("summary")
    ]
    audit_summary = {
        "audits_run": len(AUDIT_HISTORY),
        "avg_cvl_ms": round(sum(cvl_values) / len(cvl_values), 2) if cvl_values else 0.0,
        "last_cvl_ms": cvl_values[-1] if cvl_values else 0.0,
    }

    chart_data = {
        "eis": {
            "labels": [f"Run {run['run_id']}" for run in AUDIT_HISTORY],
            "values": [run.get("summary", {}).get("eis_score", 0.0) for run in AUDIT_HISTORY],
        },
        "cvl": {
            "labels": [f"Run {run['run_id']}" for run in AUDIT_HISTORY],
            "values": [run.get("summary", {}).get("cvl_ms", 0.0) for run in AUDIT_HISTORY],
        },
        "sla_by_officer": {
            "labels": [row["officer_id"] for row in officer_rows],
            "within": [row["within_sla_count"] for row in officer_rows],
            "delayed": [row["delayed_count"] for row in officer_rows],
        },
    }

    avg_trt_overall = round(trt_hours_total / trt_samples, 2) if trt_samples else 0.0
    trt_priority_labels = []
    trt_priority_values = []
    for priority, stats in sorted(priority_trt.items()):
        if not stats["count"]:
            continue
        trt_priority_labels.append(priority)
        trt_priority_values.append(round(stats["total"] / stats["count"], 2))

    chart_data["trt_by_priority"] = {
        "labels": trt_priority_labels,
        "values": trt_priority_values,
    }

    integrity_breakdown = {
        "MATCH": global_status_counts.get("MATCH", 0),
        "TAMPERED": global_status_counts.get("TAMPERED", 0),
        "MISSING_LEDGER": global_status_counts.get("MISSING_LEDGER", 0),
        "MISSING_OFFCHAIN": global_status_counts.get("MISSING_OFFCHAIN", 0),
        "ORDER_ANOMALY": global_status_counts.get("ORDER_ANOMALY", 0),
    }
    chart_data["integrity_breakdown"] = {
        "labels": list(integrity_breakdown.keys()),
        "values": list(integrity_breakdown.values()),
    }

    global_aci_avg = round(sum(aci_scores) / len(aci_scores), 2) if aci_scores else 0.0

    return {
        "complaint_summary": {
            "total": total_complaints,
            "open": open_count,
            "closed": closed_count,
        },
        "integrity_summary": {
            "total_events": integrity_events,
            "tampered_events": tampered_events,
            "global_eis": global_eis,
            "missing_offchain": missing_offchain_total,
            "global_aci": global_aci_avg,
        },
        "officer_summary": {
            "total_officers": len(officer_stats),
            "delayed_count": delayed_complaints,
            "avg_response_hours": round(
                response_hours_total / response_samples, 2
            )
            if response_samples
            else 0.0,
        },
        "trt_summary": {
            "avg_hours": avg_trt_overall,
            "by_priority": dict(
                zip(
                    trt_priority_labels,
                    trt_priority_values,
                )
            ),
        },
        "integrity_breakdown": integrity_breakdown,
        "audit_summary": audit_summary,
        "officer_oai": officer_rows,
        "chart_data": chart_data,
    }


def _clear_system_state() -> Dict:
    with get_db() as conn:
        cursor = conn.cursor()
        pre_counts = {
            "complaints": cursor.execute("SELECT COUNT(*) FROM complaints").fetchone()[0],
            "events": cursor.execute("SELECT COUNT(*) FROM complaint_events").fetchone()[0],
            "ledger": cursor.execute("SELECT COUNT(*) FROM ledger_hashes").fetchone()[0],
        }
        cursor.execute("DELETE FROM complaint_events")
        cursor.execute("DELETE FROM complaints")
        cursor.execute("DELETE FROM ledger_hashes")
        conn.commit()

    AUDIT_HISTORY.clear()
    log_path = _fabric_log_path()
    log_cleared = False
    if log_path.exists():
        log_path.unlink()
        log_cleared = True

    return {"pre_counts": pre_counts, "log_cleared": log_cleared}


def _record_event(
    complaint_id: str,
    event_type: str,
    actor_id: str,
    remarks: str,
    timestamp: Optional[str] = None,
) -> str:
    ts = timestamp or now_iso()
    with get_db() as conn:
        cursor = conn.cursor()
        event_id = new_event_id()
        cursor.execute(
            """
            INSERT INTO complaint_events (
                event_id, complaint_id, event_type, actor_id, remarks, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, complaint_id, event_type, actor_id, remarks, ts),
        )
        cursor.execute(
            "UPDATE complaints SET current_status = ? WHERE complaint_id = ?",
            (event_type, complaint_id),
        )
        conn.commit()

    with get_db() as conn:
        prev_hash = _latest_ledger_hash(conn.cursor(), complaint_id) or "GENESIS"
    payload = canonical_event_payload(
        complaint_id=complaint_id,
        event_id=event_id,
        event_type=event_type,
        actor_id=actor_id,
        remarks=remarks,
        timestamp=ts,
        prev_event_hash=prev_hash,
    )
    event_hash = sha256(canonical_json(payload))
    get_ledger_backend().anchor_hash(
        event_id=event_id,
        complaint_id=complaint_id,
        event_hash=event_hash,
        timestamp=ts,
    )
    return event_id


def _run_benchmark(complaint_count: int, events_per_complaint: int) -> Dict:
    count = max(1, min(complaint_count, MAX_BENCHMARK_COMPLAINTS))
    per_complaint = max(1, min(events_per_complaint, MAX_BENCHMARK_EVENTS))
    status_plan = ["ASSIGNED", "IN_PROGRESS", "FOLLOW_UP", "CLOSED", "FOLLOW_UP", "CLOSED"]
    audits: List[Dict] = []
    priorities = ["HIGH", "MEDIUM", "LOW"]

    for idx in range(count):
        complaint_id = new_complaint_id()
        created_at = now_iso()
        citizen_id = f"citizen-{idx+1:02d}"
        remarks = "Synthetic complaint submitted for benchmark"
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO complaints (
                    complaint_id, title, description, category, priority, citizen_id,
                    current_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    complaint_id,
                    f"Benchmark case {idx+1}",
                    "Synthetic complaint for benchmark run.",
                    "Benchmark",
                    priorities[idx % len(priorities)],
                    citizen_id,
                    "SUBMIT",
                    created_at,
                ),
            )
            submit_event_id = new_event_id()
            submit_ts = now_iso()
            cursor.execute(
                """
                INSERT INTO complaint_events (
                    event_id, complaint_id, event_type, actor_id, remarks, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    submit_event_id,
                    complaint_id,
                    "SUBMIT",
                    citizen_id,
                    remarks,
                    submit_ts,
                ),
            )
            conn.commit()

        payload = canonical_event_payload(
            complaint_id=complaint_id,
            event_id=submit_event_id,
            event_type="SUBMIT",
            actor_id=citizen_id,
            remarks=remarks,
            timestamp=submit_ts,
            prev_event_hash="GENESIS",
        )
        submit_hash = sha256(canonical_json(payload))
        get_ledger_backend().anchor_hash(
            event_id=submit_event_id,
            complaint_id=complaint_id,
            event_hash=submit_hash,
            timestamp=submit_ts,
        )

        for step, status in enumerate(status_plan[:per_complaint]):
            actor = f"officer-{idx+1:02d}"
            remark = f"Benchmark {status.lower()} step {step + 1}"
            event_id = _record_event(complaint_id, status, actor, remark)

        audits.append(_verify_complaint(complaint_id, "benchmark"))

    cvls = [run["summary"]["cvl_ms"] for run in audits if run.get("summary")]
    totals = [run["summary"]["total"] for run in audits if run.get("summary")]
    chart_points = [
        {"label": run["complaint_id"], "events": run["summary"]["total"], "cvl": run["summary"]["cvl_ms"]}
        for run in audits
    ]

    return {
        "requested": {"complaints": complaint_count, "events_per_complaint": events_per_complaint},
        "used": {"complaints": count, "events_per_complaint": per_complaint},
        "audits": audits,
        "total_events": sum(totals),
        "avg_cvl_ms": round(sum(cvls) / len(cvls), 2) if cvls else 0.0,
        "max_cvl_ms": max(cvls) if cvls else 0,
        "chart": chart_points,
    }


def _simulate_tamper(complaint_id: str) -> Optional[str]:
    with get_db() as conn:
        cursor = conn.cursor()
        latest_event = cursor.execute(
            """
            SELECT event_id, remarks
            FROM complaint_events
            WHERE complaint_id = ?
            ORDER BY timestamp DESC, rowid DESC
            LIMIT 1
            """,
            (complaint_id,),
        ).fetchone()
        if not latest_event:
            return None

        tampered_remarks = f"{latest_event['remarks']} [tampered @ {now_iso()}]"
        cursor.execute(
            "UPDATE complaint_events SET remarks = ? WHERE event_id = ?",
            (tampered_remarks, latest_event["event_id"]),
        )
        conn.commit()
        return tampered_remarks


def _delete_latest_event(complaint_id: str) -> Optional[Dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        latest_event = cursor.execute(
            """
            SELECT event_id, event_type, actor_id, remarks, timestamp
            FROM complaint_events
            WHERE complaint_id = ?
            ORDER BY timestamp DESC, rowid DESC
            LIMIT 1
            """,
            (complaint_id,),
        ).fetchone()
        if not latest_event:
            return None
        cursor.execute("DELETE FROM complaint_events WHERE event_id = ?", (latest_event["event_id"],))
        next_event = cursor.execute(
            """
            SELECT event_type
            FROM complaint_events
            WHERE complaint_id = ?
            ORDER BY timestamp DESC, rowid DESC
            LIMIT 1
            """,
            (complaint_id,),
        ).fetchone()
        new_status = next_event["event_type"] if next_event else "UNKNOWN"
        cursor.execute(
            "UPDATE complaints SET current_status = ? WHERE complaint_id = ?",
            (new_status, complaint_id),
        )
        conn.commit()
        return dict(latest_event)


def _delete_latest_ledger_anchor(complaint_id: str) -> Optional[Dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        latest_anchor = cursor.execute(
            """
            SELECT ledger_id, event_id, event_hash, timestamp
            FROM ledger_hashes
            WHERE complaint_id = ?
            ORDER BY timestamp DESC, ledger_id DESC
            LIMIT 1
            """,
            (complaint_id,),
        ).fetchone()
        if not latest_anchor:
            return None
        cursor.execute("DELETE FROM ledger_hashes WHERE ledger_id = ?", (latest_anchor["ledger_id"],))
        conn.commit()
        return dict(latest_anchor)


def _insert_fake_event(complaint_id: str) -> Optional[Dict]:
    with get_db() as conn:
        cursor = conn.cursor()
        complaint = cursor.execute(
            "SELECT * FROM complaints WHERE complaint_id = ?", (complaint_id,)
        ).fetchone()
        if not complaint:
            return None

    fake_event_id = new_event_id()
    fake_ts = now_iso()
    fake_type = "FAKE_EVENT"
    fake_actor = "adversary"
    fake_remarks = "Unanchored insertion by adversary"

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO complaint_events (
                event_id, complaint_id, event_type, actor_id, remarks, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (fake_event_id, complaint_id, fake_type, fake_actor, fake_remarks, fake_ts),
        )
        cursor.execute(
            "UPDATE complaints SET current_status = ? WHERE complaint_id = ?",
            (fake_type, complaint_id),
        )
        conn.commit()

    return {
        "event_id": fake_event_id,
        "event_type": fake_type,
        "actor_id": fake_actor,
        "remarks": fake_remarks,
        "timestamp": fake_ts,
    }


def _reorder_latest_events(complaint_id: str) -> Optional[List[Dict]]:
    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT event_id, timestamp
            FROM complaint_events
            WHERE complaint_id = ?
            ORDER BY timestamp DESC, rowid DESC
            LIMIT 2
            """,
            (complaint_id,),
        ).fetchall()
        if len(rows) < 2:
            return None
        first, second = rows[0], rows[1]
        cursor.execute(
            "UPDATE complaint_events SET timestamp = ? WHERE event_id = ?",
            (second["timestamp"], first["event_id"]),
        )
        cursor.execute(
            "UPDATE complaint_events SET timestamp = ? WHERE event_id = ?",
            (first["timestamp"], second["event_id"]),
        )
        conn.commit()
        return [dict(first), dict(second)]


def _verify_complaint(complaint_id: str, action: str) -> Dict:
    with get_db() as conn:
        cursor = conn.cursor()
        complaint_row = cursor.execute(
            "SELECT * FROM complaints WHERE complaint_id = ?", (complaint_id,)
        ).fetchone()
        if not complaint_row:
            return {"error": "Complaint not found."}

        events = cursor.execute(
            """
            SELECT event_id, event_type, actor_id, remarks, timestamp
            FROM complaint_events
            WHERE complaint_id = ?
            ORDER BY rowid ASC
            """,
            (complaint_id,),
        ).fetchall()

        ledger_rows = cursor.execute(
            """
            SELECT event_id, event_hash, timestamp
            FROM ledger_hashes
            WHERE complaint_id = ?
            """,
            (complaint_id,),
        ).fetchall()

    start_time = time.perf_counter()
    ledger_by_event: Dict[str, str] = {
        row["event_id"]: row["event_hash"] for row in ledger_rows
    }
    event_ids = {event["event_id"] for event in events}
    missing_offchain = [
        {
            "event_id": row["event_id"],
            "event_hash": row["event_hash"],
            "timestamp": row["timestamp"],
        }
        for row in ledger_rows
        if row["event_id"] not in event_ids
    ]

    verification = _verify_events_against_ledger(
        [dict(event) for event in events], ledger_by_event, complaint_id=complaint_id
    )
    event_results = verification["events"]
    matched_count = verification["matched"]
    chain_broken = verification["chain_broken"]
    order_anomalies = verification.get("order_anomalies", 0)
    status_counts = defaultdict(int)
    for event in event_results:
        status_counts[event["status"]] += 1
    status_counts["MISSING_OFFCHAIN"] += len(missing_offchain)

    cvl_ms = int((time.perf_counter() - start_time) * 1000)
    total_events = len(events) + len(missing_offchain)
    eis_score = round((matched_count / total_events) * 100, 2) if total_events else 0.0
    chain_status = "BROKEN" if (chain_broken or missing_offchain or order_anomalies) else "OK"

    complaint = dict(complaint_row)
    oai = _compute_oai(complaint, events)
    aci = _compute_aci([dict(e) for e in events], ledger_by_event)
    trt_hours = _compute_trt([dict(e) for e in events])

    run_data = {
        "run_id": len(AUDIT_HISTORY) + 1,
        "complaint_id": complaint_id,
        "complaint": complaint,
        "events": event_results,
        "missing_offchain": missing_offchain,
        "summary": {
            "matched": matched_count,
            "total": total_events,
            "eis_score": eis_score,
            "cvl_ms": cvl_ms,
            "oai": oai,
            "chain_status": chain_status,
            "action": action,
            "status_counts": dict(status_counts),
            "order_anomalies": order_anomalies,
            "aci": aci,
            "trt_hours": trt_hours,
        },
        "timestamp": now_iso(),
    }
    AUDIT_HISTORY.append(run_data)
    return run_data


@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    dashboard_data = _build_dashboard_data()
    return render_template("dashboard.html", **dashboard_data)


@app.route("/submit", methods=["GET", "POST"])
def submit():
    receipt = None

    if request.method == "POST":
        citizen_id = request.form.get("citizen_id", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        priority = request.form.get("priority", "").strip()

        complaint_id = new_complaint_id()
        created_at = now_iso()
        event_id = new_event_id()
        event_timestamp = now_iso()
        remarks = "Complaint submitted"
        prev_event_hash = "GENESIS"

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO complaints (
                    complaint_id, title, description, category, priority, citizen_id,
                    current_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    complaint_id,
                    title,
                    description,
                    category,
                    priority,
                    citizen_id,
                    "SUBMIT",
                    created_at,
                ),
            )
            cursor.execute(
                """
                INSERT INTO complaint_events (
                    event_id, complaint_id, event_type, actor_id, remarks, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    complaint_id,
                    "SUBMIT",
                    citizen_id,
                    remarks,
                    event_timestamp,
                ),
            )
            prev_event_hash = _latest_ledger_hash(cursor, complaint_id) or "GENESIS"
            conn.commit()

        payload = canonical_event_payload(
            complaint_id=complaint_id,
            event_id=event_id,
            event_type="SUBMIT",
            actor_id=citizen_id,
            remarks=remarks,
            timestamp=event_timestamp,
            prev_event_hash=prev_event_hash,
        )
        event_hash = sha256(canonical_json(payload))
        anchor_meta = get_ledger_backend().anchor_hash(
            event_id=event_id,
            complaint_id=complaint_id,
            event_hash=event_hash,
            timestamp=event_timestamp,
        )

        receipt = {
            "complaint_id": complaint_id,
            "event_id": event_id,
            "event_hash": event_hash,
            "backend": anchor_meta.get("backend", ""),
            "tx_id": anchor_meta.get("tx_id", ""),
        }

    return render_template("submit.html", receipt=receipt)


@app.route("/update", methods=["GET", "POST"])
def update():
    error = None
    update_receipt = None

    if request.method == "POST":
        complaint_id = request.form.get("complaint_id", "").strip()
        officer_id = request.form.get("officer_id", "").strip()
        status = request.form.get("status", "").strip().upper()
        remarks = request.form.get("remarks", "").strip()
        final_remarks = remarks or (f"Status set to {status}" if status else "")

        if not complaint_id or not officer_id or not status:
            error = "Complaint ID, officer ID, and status are required."
        else:
            event_id = None
            timestamp = None
            prev_hash = "GENESIS"
            with get_db() as conn:
                cursor = conn.cursor()
                complaint = cursor.execute(
                    "SELECT * FROM complaints WHERE complaint_id = ?",
                    (complaint_id,),
                ).fetchone()
                if not complaint:
                    error = "Complaint not found."
                else:
                    prev_hash = _latest_ledger_hash(cursor, complaint_id) or "GENESIS"
                    event_id = new_event_id()
                    timestamp = now_iso()
                    cursor.execute(
                        """
                        INSERT INTO complaint_events (
                            event_id, complaint_id, event_type, actor_id, remarks, timestamp
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            complaint_id,
                            status,
                            officer_id,
                            final_remarks,
                            timestamp,
                        ),
                    )
                    cursor.execute(
                        "UPDATE complaints SET current_status = ? WHERE complaint_id = ?",
                        (status, complaint_id),
                    )
                    conn.commit()

            if not error and event_id and timestamp:
                payload = canonical_event_payload(
                    complaint_id=complaint_id,
                    event_id=event_id,
                    event_type=status,
                    actor_id=officer_id,
                    remarks=final_remarks,
                    timestamp=timestamp,
                    prev_event_hash=prev_hash,
                )
                event_hash = sha256(canonical_json(payload))
                anchor_meta = get_ledger_backend().anchor_hash(
                    event_id=event_id,
                    complaint_id=complaint_id,
                    event_hash=event_hash,
                    timestamp=timestamp,
                )
                update_receipt = {
                    "complaint_id": complaint_id,
                    "event_id": event_id,
                    "event_hash": event_hash,
                    "status": status,
                    "backend": anchor_meta.get("backend", ""),
                    "tx_id": anchor_meta.get("tx_id", ""),
                }

    return render_template("update.html", error=error, receipt=update_receipt)


@app.route("/timeline/")
def timeline():
    complaint_id = request.args.get("complaint_id", "").strip()
    complaint = None
    events = []
    error = None

    if complaint_id:
        with get_db() as conn:
            cursor = conn.cursor()
            complaint = cursor.execute(
                "SELECT * FROM complaints WHERE complaint_id = ?",
                (complaint_id,),
            ).fetchone()
            if complaint:
                events = cursor.execute(
                    """
                    SELECT ce.event_id, ce.event_type, ce.actor_id, ce.remarks, ce.timestamp, lh.event_hash
                    FROM complaint_events ce
                    LEFT JOIN ledger_hashes lh ON lh.event_id = ce.event_id
                    WHERE ce.complaint_id = ?
                    ORDER BY ce.timestamp ASC, ce.rowid ASC
                    """,
                    (complaint_id,),
                ).fetchall()
            else:
                error = "Complaint not found."

    return render_template(
        "timeline.html",
        complaint_id=complaint_id,
        complaint=complaint,
        events=events,
        error=error,
    )


@app.route("/attacks", methods=["GET", "POST"])
def attacks():
    complaint_id = request.args.get("complaint_id", "").strip()
    if request.method == "POST":
        complaint_id = request.form.get("complaint_id", "").strip() or complaint_id
    attack_result = None
    error = None

    with get_db() as conn:
        cursor = conn.cursor()
        complaint_options = cursor.execute(
            """
            SELECT complaint_id, title, current_status, created_at
            FROM complaints
            ORDER BY created_at DESC, rowid DESC
            LIMIT 20
            """
        ).fetchall()

    if request.method == "POST":
        attack = request.form.get("attack", "").strip()
        if not complaint_id:
            error = "Complaint ID is required to run an attack."
        else:
            if attack == "MODIFY_LATEST_REMARKS":
                tampered = _simulate_tamper(complaint_id)
                if tampered is None:
                    error = "No events available to tamper."
                else:
                    attack_result = {"attack": attack, "details": tampered}
            elif attack == "DELETE_LATEST_EVENT":
                deleted = _delete_latest_event(complaint_id)
                if not deleted:
                    error = "No events found to delete."
                else:
                    attack_result = {"attack": attack, "details": deleted}
            elif attack == "DELETE_LEDGER_ANCHOR":
                anchor = _delete_latest_ledger_anchor(complaint_id)
                if not anchor:
                    error = "No ledger anchor found to delete."
                else:
                    attack_result = {"attack": attack, "details": anchor}
            elif attack == "INSERT_FAKE_EVENT":
                fake_event = _insert_fake_event(complaint_id)
                if not fake_event:
                    error = "Complaint not found for fake insertion."
                else:
                    attack_result = {"attack": attack, "details": fake_event}
            elif attack == "REORDER_ATTACK":
                swapped = _reorder_latest_events(complaint_id)
                if not swapped:
                    error = "Need at least two events to reorder."
                else:
                    attack_result = {"attack": attack, "details": swapped}
            else:
                error = "Select a valid attack type."

    return render_template(
        "attacks.html",
        complaint_id=complaint_id,
        complaint_options=complaint_options,
        attack_result=attack_result,
        error=error,
    )


@app.route("/audit", methods=["GET", "POST"])
def audit():
    complaint_id = request.args.get("complaint_id", "").strip()
    audit_result = None
    error = None
    tamper_note = None
    status_hints = {}

    if request.method == "POST":
        complaint_id = request.form.get("complaint_id", "").strip() or complaint_id
        action = request.form.get("action", "verify")

        if not complaint_id:
            error = "Complaint ID is required."
        else:
            if action == "tamper":
                tampered = _simulate_tamper(complaint_id)
                if tampered is None:
                    error = "Cannot tamper: complaint has no events."
                else:
                    tamper_note = "Tamper simulation applied to latest event remarks."
            if not error:
                audit_result = _verify_complaint(complaint_id, action)
                if audit_result.get("error"):
                    error = audit_result["error"]
                    audit_result = None
                else:
                    counts = audit_result["summary"].get("status_counts", {})
                    status_hints = {
                        "missing_ledger": counts.get("MISSING_LEDGER", 0),
                        "missing_offchain": counts.get("MISSING_OFFCHAIN", 0),
                        "order_anomaly": counts.get("ORDER_ANOMALY", 0),
                    }

    latest_run_id = AUDIT_HISTORY[-1]["run_id"] if AUDIT_HISTORY else None
    return render_template(
        "audit.html",
        complaint_id=complaint_id,
        audit_result=audit_result,
        audit_history=AUDIT_HISTORY,
        error=error,
        tamper_note=tamper_note,
        latest_run_id=latest_run_id,
        status_hints=status_hints,
    )


@app.route("/audit/report")
def audit_report():
    run_id = request.args.get("run_id", type=int)
    if run_id is None and AUDIT_HISTORY:
        run_id = AUDIT_HISTORY[-1]["run_id"]

    run = next((entry for entry in AUDIT_HISTORY if entry["run_id"] == run_id), None)
    if not run:
        return {"error": "Audit run not found."}, 404

    filename = f"audit-{run['complaint_id']}-{run['run_id']}.json"
    payload = json.dumps(run, indent=2)
    response = Response(payload, mimetype="application/json")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


@app.route("/benchmark")
def benchmark():
    return redirect(url_for("benchmark_run"))


@app.route("/benchmark/run", methods=["GET", "POST"])
def benchmark_run():
    result = None
    errors = []
    if request.method == "POST":
        requested_complaints = request.form.get("complaints", type=int) or 0
        requested_events = request.form.get("events_per_complaint", type=int) or 0

        complaints = max(1, min(requested_complaints, MAX_BENCHMARK_COMPLAINTS))
        events_per = max(1, min(requested_events, MAX_BENCHMARK_EVENTS))
        result = _run_benchmark(complaints, events_per)
        result["capped"] = {
            "complaints": requested_complaints > MAX_BENCHMARK_COMPLAINTS,
            "events": requested_events > MAX_BENCHMARK_EVENTS,
        }
        result["form_values"] = {
            "complaints": requested_complaints or complaints,
            "events_per_complaint": requested_events or events_per,
        }

    return render_template(
        "benchmark.html",
        max_complaints=MAX_BENCHMARK_COMPLAINTS,
        max_events=MAX_BENCHMARK_EVENTS,
        result=result,
        errors=errors,
    )


@app.route("/reset", methods=["GET", "POST"])
def reset():
    cleared = None
    error = None
    if request.method == "POST":
        confirmation = request.form.get("confirmation", "").strip().upper()
        if confirmation != "RESET":
            error = "Type RESET to confirm."
        else:
            cleared = _clear_system_state()

    return render_template("reset.html", cleared=cleared, error=error)


if __name__ == "__main__":
    app.run(debug=True)
