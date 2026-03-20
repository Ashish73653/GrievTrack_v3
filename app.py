import json
import time
from datetime import datetime, timedelta
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
            ORDER BY timestamp ASC, rowid ASC
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

    prev_hash = ""
    matched_count = 0
    event_results = []
    for event in events:
        ledger_hash = ledger_by_event.get(event["event_id"])
        payload = canonical_event_payload(
            complaint_id=complaint_id,
            event_id=event["event_id"],
            event_type=event["event_type"],
            actor_id=event["actor_id"],
            remarks=event["remarks"],
            timestamp=event["timestamp"],
            prev_event_hash=prev_hash,
        )
        recomputed_hash = sha256(canonical_json(payload))

        if ledger_hash:
            prev_hash = ledger_hash

        if ledger_hash is None:
            status = "MISSING_LEDGER"
        elif ledger_hash == recomputed_hash:
            status = "MATCH"
            matched_count += 1
        else:
            status = "TAMPERED"

        event_results.append(
            {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "actor_id": event["actor_id"],
                "remarks": event["remarks"],
                "timestamp": event["timestamp"],
                "ledger_hash": ledger_hash or "",
                "recomputed_hash": recomputed_hash,
                "status": status,
            }
        )

    cvl_ms = int((time.perf_counter() - start_time) * 1000)
    total_events = len(events) + len(missing_offchain)
    eis_score = round((matched_count / total_events) * 100, 2) if total_events else 0.0

    complaint = dict(complaint_row)
    oai = _compute_oai(complaint, events)

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
            "action": action,
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
    return render_template("dashboard.html")


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
            conn.commit()

        payload = canonical_event_payload(
            complaint_id=complaint_id,
            event_id=event_id,
            event_type="SUBMIT",
            actor_id=citizen_id,
            remarks=remarks,
            timestamp=event_timestamp,
            prev_event_hash="",
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
            prev_hash = ""
            with get_db() as conn:
                cursor = conn.cursor()
                complaint = cursor.execute(
                    "SELECT * FROM complaints WHERE complaint_id = ?",
                    (complaint_id,),
                ).fetchone()
                if not complaint:
                    error = "Complaint not found."
                else:
                    previous_event = cursor.execute(
                        """
                        SELECT ce.event_id, lh.event_hash
                        FROM complaint_events ce
                        LEFT JOIN ledger_hashes lh ON lh.event_id = ce.event_id
                        WHERE ce.complaint_id = ?
                        ORDER BY ce.timestamp DESC, ce.rowid DESC
                        LIMIT 1
                        """,
                        (complaint_id,),
                    ).fetchone()
                    prev_hash = (
                        previous_event["event_hash"]
                        if previous_event and previous_event["event_hash"]
                        else ""
                    )
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


@app.route("/audit", methods=["GET", "POST"])
def audit():
    complaint_id = ""
    audit_result = None
    error = None
    tamper_note = None

    if request.method == "POST":
        complaint_id = request.form.get("complaint_id", "").strip()
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

    latest_run_id = AUDIT_HISTORY[-1]["run_id"] if AUDIT_HISTORY else None
    return render_template(
        "audit.html",
        complaint_id=complaint_id,
        audit_result=audit_result,
        audit_history=AUDIT_HISTORY,
        error=error,
        tamper_note=tamper_note,
        latest_run_id=latest_run_id,
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
    return render_template("benchmark.html")


@app.route("/reset")
def reset():
    return render_template("reset.html")


if __name__ == "__main__":
    app.run(debug=True)
