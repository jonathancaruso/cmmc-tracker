"""Assignments blueprint: CRUD for objective assignments and bulk assign."""

from datetime import datetime

from flask import Blueprint, request, jsonify

from models import get_db
from utils import log_audit

assignments_bp = Blueprint('assignments', __name__)


@assignments_bp.route("/api/assignments/<objective_id>")
def list_assignments(objective_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, t.name as member_name, t.role as member_role
        FROM artifact_assignments a
        JOIN team_members t ON a.member_id = t.id
        WHERE a.objective_id = ?
        ORDER BY a.assigned_at DESC
    """, (objective_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@assignments_bp.route("/api/assignments", methods=["POST"])
def add_assignment():
    data = request.json
    objective_id = data.get("objective_id")
    member_id = data.get("member_id")
    if not objective_id or not member_id:
        return jsonify({"error": "objective_id and member_id required"}), 400
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM artifact_assignments WHERE objective_id = ? AND member_id = ?",
        (objective_id, member_id)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "Already assigned"}), 409
    conn.execute("""
        INSERT INTO artifact_assignments (objective_id, member_id, status, due_date, assigned_at)
        VALUES (?, ?, ?, ?, ?)
    """, (objective_id, member_id, data.get("status", "assigned"),
          data.get("due_date"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    member = conn.execute("SELECT name FROM team_members WHERE id = ?", (member_id,)).fetchone()
    member_name = member['name'] if member else f"#{member_id}"
    log_audit('created', 'assignment', objective_id,
              f"Assigned {objective_id} to {member_name}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@assignments_bp.route("/api/assignments/<int:assignment_id>", methods=["DELETE"])
def delete_assignment(assignment_id):
    conn = get_db()
    asgn = conn.execute("""
        SELECT a.objective_id, t.name FROM artifact_assignments a
        JOIN team_members t ON a.member_id = t.id WHERE a.id = ?
    """, (assignment_id,)).fetchone()
    conn.execute("DELETE FROM artifact_assignments WHERE id = ?", (assignment_id,))
    detail = f"Removed assignment {asgn['objective_id']} from {asgn['name']}" if asgn else f"Deleted assignment #{assignment_id}"
    log_audit('deleted', 'assignment', assignment_id, detail, conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@assignments_bp.route("/api/assignments/<int:assignment_id>/due", methods=["PATCH"])
def update_assignment_due(assignment_id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE artifact_assignments SET due_date = ? WHERE id = ?",
                 (data.get("due_date") or None, assignment_id))
    log_audit('due_date_changed', 'assignment', assignment_id,
              f"Due date set to {data.get('due_date') or 'none'}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@assignments_bp.route("/api/assignments/<int:assignment_id>/status", methods=["PATCH"])
def update_assignment_status(assignment_id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE artifact_assignments SET status = ? WHERE id = ?",
                 (data.get("status", "assigned"), assignment_id))
    log_audit('status_change', 'assignment', assignment_id,
              f"Assignment status set to {data.get('status', 'assigned')}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@assignments_bp.route("/api/assignments/bulk", methods=["POST"])
def bulk_assign():
    data = request.json
    requirement_id = data.get("requirement_id")
    member_id = data.get("member_id")
    if not requirement_id or not member_id:
        return jsonify({"error": "requirement_id and member_id required"}), 400
    conn = get_db()
    objectives = conn.execute(
        "SELECT id FROM objectives WHERE requirement_id = ?", (requirement_id,)
    ).fetchall()
    added = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for obj in objectives:
        existing = conn.execute(
            "SELECT id FROM artifact_assignments WHERE objective_id = ? AND member_id = ?",
            (obj["id"], member_id)
        ).fetchone()
        if not existing:
            conn.execute("""
                INSERT INTO artifact_assignments (objective_id, member_id, status, assigned_at)
                VALUES (?, ?, 'assigned', ?)
            """, (obj["id"], member_id, now))
            added += 1
    member = conn.execute("SELECT name FROM team_members WHERE id = ?", (member_id,)).fetchone()
    member_name = member['name'] if member else f"#{member_id}"
    log_audit('bulk_assign', 'assignment', requirement_id,
              f"Bulk assigned {requirement_id} to {member_name} ({added} new of {len(objectives)} objectives)",
              conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "added": added, "total": len(objectives)})
