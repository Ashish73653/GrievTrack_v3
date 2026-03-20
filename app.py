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


@app.route("/update")
def update():
    return render_template("update.html")


@app.route("/timeline/")
def timeline():
    return render_template("timeline.html")


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
