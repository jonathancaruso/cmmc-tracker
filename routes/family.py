"""Family blueprint: family detail page, objective toggle/status/notes, bulk operations."""

from datetime import datetime

from flask import Blueprint, render_template, request, jsonify

from models import get_db, FAMILY_ABBR, FAMILY_COLORS, VALID_STATUSES
from utils import log_audit, get_org_id

family_bp = Blueprint('family', __name__)


@family_bp.route("/family/<path:family_name>")
def family_detail(family_name):
    org_id = get_org_id()
    conn = get_db()
    objectives = conn.execute("""
        SELECT o.id, o.family, o.requirement_id, o.sort_as,
               o.security_requirement, o.assessment_objective,
               o.examine, o.interview, o.test,
               o.requirement_type, o.discussion, o.example_artifacts,
               COALESCE(p.captured, 0) as captured,
               COALESCE(p.status, 'Not Started') as status,
               COALESCE(p.artifact_notes, '') as artifact_notes,
               p.captured_date
        FROM objectives o
        LEFT JOIN objective_progress p ON o.id = p.objective_id AND p.org_id = ?
        WHERE o.family = ? ORDER BY o.sort_as
    """, (org_id, family_name)).fetchall()
    ssp_mappings = {}
    for s in conn.execute("SELECT requirement_id, ssp_section, ssp_description FROM ssp_mappings").fetchall():
        ssp_mappings[s["requirement_id"]] = {"ssp_section": s["ssp_section"] or "", "ssp_description": s["ssp_description"] or ""}
    conn.close()

    requirements = {}
    for obj in objectives:
        req_id = obj["requirement_id"]
        if req_id not in requirements:
            ssp = ssp_mappings.get(req_id, {})
            requirements[req_id] = {
                "id": req_id,
                "security_requirement": obj["security_requirement"],
                "examine": obj["examine"],
                "interview": obj["interview"],
                "test": obj["test"],
                "ssp_section": ssp.get("ssp_section", ""),
                "ssp_description": ssp.get("ssp_description", ""),
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
    org_id = get_org_id()
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d") if captured else None
    conn.execute("""
        INSERT INTO objective_progress (org_id, objective_id, captured, artifact_notes, captured_date, status)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(org_id, objective_id) DO UPDATE SET
            captured = excluded.captured, artifact_notes = excluded.artifact_notes,
            captured_date = excluded.captured_date, status = excluded.status
    """, (org_id, obj_id, 1 if captured else 0, notes, now, status))
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
    org_id = get_org_id()
    conn = get_db()
    captured = 1 if status == "Complete" else 0
    now = datetime.now().strftime("%Y-%m-%d") if captured else None
    if captured:
        existing = conn.execute("SELECT captured_date FROM objective_progress WHERE org_id = ? AND objective_id = ?",
                                (org_id, obj_id)).fetchone()
        if existing and existing["captured_date"]:
            now = existing["captured_date"]
    conn.execute("""
        INSERT INTO objective_progress (org_id, objective_id, status, captured, captured_date)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(org_id, objective_id) DO UPDATE SET
            status = excluded.status, captured = excluded.captured,
            captured_date = COALESCE(excluded.captured_date, objective_progress.captured_date)
    """, (org_id, obj_id, status, captured, now))
    log_audit('status_change', 'objective', obj_id, f"Set status to {status}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "status": status, "captured": captured})


@family_bp.route("/api/notes", methods=["POST"])
def update_notes():
    data = request.json
    obj_id = data.get("id")
    org_id = get_org_id()
    conn = get_db()
    conn.execute("""
        INSERT INTO objective_progress (org_id, objective_id, artifact_notes)
        VALUES (?, ?, ?)
        ON CONFLICT(org_id, objective_id) DO UPDATE SET artifact_notes = excluded.artifact_notes
    """, (org_id, obj_id, data.get("notes", "")))
    log_audit('notes_saved', 'objective', obj_id, 'Notes updated', conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@family_bp.route("/api/bulk", methods=["POST"])
def bulk_update():
    data = request.json
    req_id = data.get("requirement_id")
    captured = data.get("captured", True)
    org_id = get_org_id()
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d") if captured else None
    status = "Complete" if captured else "Not Started"
    objectives = conn.execute("SELECT id FROM objectives WHERE requirement_id = ?", (req_id,)).fetchall()
    for obj in objectives:
        conn.execute("""
            INSERT INTO objective_progress (org_id, objective_id, captured, captured_date, status)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(org_id, objective_id) DO UPDATE SET
                captured = excluded.captured, captured_date = excluded.captured_date, status = excluded.status
        """, (org_id, obj['id'], 1 if captured else 0, now, status))
    log_audit('bulk_toggle', 'objective', req_id,
              f"Bulk set requirement {req_id} to {status}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})
