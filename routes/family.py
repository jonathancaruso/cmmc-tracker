"""Family blueprint: family detail page, objective toggle/status/notes, bulk operations."""

from datetime import datetime

from flask import Blueprint, render_template, request, jsonify

from models import get_db, FAMILY_ABBR, FAMILY_COLORS, VALID_STATUSES
from utils import log_audit

family_bp = Blueprint('family', __name__)


@family_bp.route("/family/<path:family_name>")
def family_detail(family_name):
    conn = get_db()
    objectives = conn.execute("""
        SELECT * FROM objectives WHERE family = ? ORDER BY sort_as
    """, (family_name,)).fetchall()
    conn.close()

    requirements = {}
    for obj in objectives:
        req_id = obj["requirement_id"]
        if req_id not in requirements:
            requirements[req_id] = {
                "id": req_id,
                "security_requirement": obj["security_requirement"],
                "examine": obj["examine"],
                "interview": obj["interview"],
                "test": obj["test"],
                "objectives": [],
            }
        requirements[req_id]["objectives"].append(dict(obj))

    abbr = FAMILY_ABBR.get(family_name, "")
    return render_template("family.html", family=family_name, abbr=abbr,
                           requirements=requirements,
                           color=FAMILY_COLORS.get(abbr, "#6366f1"))


@family_bp.route("/api/toggle", methods=["POST"])
def toggle_objective():
    data = request.json
    obj_id = data.get("id")
    captured = data.get("captured", False)
    notes = data.get("artifact_notes", "")
    status = "Complete" if captured else "Not Started"
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d") if captured else None
    conn.execute("""
        UPDATE objectives SET captured = ?, artifact_notes = ?, captured_date = ?, status = ?
        WHERE id = ?
    """, (1 if captured else 0, notes, now, status, obj_id))
    log_audit('toggle', 'objective', obj_id,
              f"Set to {'Complete' if captured else 'Not Started'}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@family_bp.route("/api/status", methods=["POST"])
def update_status():
    data = request.json
    obj_id = data.get("id")
    status = data.get("status", "Not Started")
    if status not in VALID_STATUSES:
        return jsonify({"error": "Invalid status"}), 400
    conn = get_db()
    captured = 1 if status == "Complete" else 0
    now = datetime.now().strftime("%Y-%m-%d") if captured else None
    if captured:
        existing = conn.execute("SELECT captured_date FROM objectives WHERE id = ?", (obj_id,)).fetchone()
        if existing and existing["captured_date"]:
            now = existing["captured_date"]
    conn.execute("""
        UPDATE objectives SET status = ?, captured = ?, captured_date = COALESCE(?, captured_date)
        WHERE id = ?
    """, (status, captured, now, obj_id))
    log_audit('status_change', 'objective', obj_id, f"Set status to {status}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "status": status, "captured": captured})


@family_bp.route("/api/notes", methods=["POST"])
def update_notes():
    data = request.json
    conn = get_db()
    obj_id = data.get("id")
    conn.execute("UPDATE objectives SET artifact_notes = ? WHERE id = ?",
                 (data.get("notes", ""), obj_id))
    log_audit('notes_saved', 'objective', obj_id, 'Notes updated', conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@family_bp.route("/api/bulk", methods=["POST"])
def bulk_update():
    data = request.json
    req_id = data.get("requirement_id")
    captured = data.get("captured", True)
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d") if captured else None
    status = "Complete" if captured else "Not Started"
    conn.execute("""
        UPDATE objectives SET captured = ?, captured_date = ?, status = ?
        WHERE requirement_id = ?
    """, (1 if captured else 0, now, status, req_id))
    log_audit('bulk_toggle', 'objective', req_id,
              f"Bulk set requirement {req_id} to {status}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})
