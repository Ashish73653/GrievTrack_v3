from flask import Flask, redirect, render_template, request, url_for

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


@app.route("/audit")
def audit():
    return render_template("audit.html")


@app.route("/benchmark")
def benchmark():
    return render_template("benchmark.html")


@app.route("/reset")
def reset():
    return render_template("reset.html")


if __name__ == "__main__":
    app.run(debug=True)
