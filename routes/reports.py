"""Reports blueprint: assessment report page, CSV export, and audit log."""

import csv
import io
import os
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, Response

from models import get_db, FAMILY_ABBR, FAMILY_COLORS
from utils import admin_required

reports_bp = Blueprint('reports', __name__)


@reports_bp.route("/api/export")
def export_csv():
    conn = get_db()
    rows = conn.execute("SELECT * FROM objectives ORDER BY sort_as").fetchall()
    assignments = {}
    for a in conn.execute("""
        SELECT a.objective_id, t.name FROM artifact_assignments a
        JOIN team_members t ON a.member_id = t.id
        ORDER BY t.name
    """).fetchall():
        assignments.setdefault(a["objective_id"], []).append(a["name"])
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Family", "Requirement", "Objective", "Status",
                     "Captured", "Notes", "Date Captured", "Assigned To"])
    for r in rows:
        assigned = "; ".join(assignments.get(r["id"], []))
        writer.writerow([r["id"], r["family"], r["requirement_id"],
                         r["assessment_objective"],
                         r["status"] or "Not Started",
                         "Yes" if r["captured"] else "No",
                         r["artifact_notes"], r["captured_date"] or "",
                         assigned])
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=cmmc-progress.csv"})


@reports_bp.route("/report")
def report():
    conn = get_db()
    totals = conn.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN o.captured = 1 THEN 1 ELSE 0 END) as captured,
               SUM(CASE WHEN o.status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
               SUM(CASE WHEN o.status = 'Evidence Collected' THEN 1 ELSE 0 END) as evidence_collected,
               SUM(CASE WHEN o.status = 'Reviewed' THEN 1 ELSE 0 END) as reviewed
        FROM objectives o
    """).fetchone()
    totals = dict(totals)

    families = conn.execute("""
        SELECT o.family,
               COUNT(*) as total,
               SUM(CASE WHEN o.captured = 1 THEN 1 ELSE 0 END) as captured,
               SUM(CASE WHEN o.status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
               SUM(CASE WHEN o.status = 'Evidence Collected' THEN 1 ELSE 0 END) as evidence_collected,
               SUM(CASE WHEN o.status = 'Reviewed' THEN 1 ELSE 0 END) as reviewed,
               COALESCE(SUM(CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END), 0) as artifact_count
        FROM objectives o
        LEFT JOIN artifacts a ON o.id = a.objective_id
        GROUP BY o.family ORDER BY o.family
    """).fetchall()
    families = [dict(f) for f in families]

    all_objectives = conn.execute("""
        SELECT * FROM objectives ORDER BY sort_as
    """).fetchall()

    all_artifacts = conn.execute("""
        SELECT ao.objective_id, a.id, a.original_name, a.obtained_method,
               d.name as domain_name
        FROM artifact_objectives ao
        JOIN artifacts a ON ao.artifact_id = a.id
        LEFT JOIN domains d ON a.domain_id = d.id
        ORDER BY a.uploaded_at DESC
    """).fetchall()

    all_assignments = conn.execute("""
        SELECT aa.objective_id, t.name, aa.status
        FROM artifact_assignments aa
        JOIN team_members t ON aa.member_id = t.id
    """).fetchall()
    conn.close()

    artifacts_by_obj = {}
    for art in all_artifacts:
        artifacts_by_obj.setdefault(art["objective_id"], []).append(dict(art))
    assignments_by_obj = {}
    for asn in all_assignments:
        assignments_by_obj.setdefault(asn["objective_id"], []).append(dict(asn))

    family_details = {}
    for obj in all_objectives:
        obj = dict(obj)
        fname = obj["family"]
        if fname not in family_details:
            family_details[fname] = {"total": 0, "captured": 0, "artifact_count": 0, "requirements": {}}
        fd = family_details[fname]
        fd["total"] += 1
        if obj.get("captured"):
            fd["captured"] += 1

        req_id = obj["requirement_id"]
        if req_id not in fd["requirements"]:
            fd["requirements"][req_id] = {
                "security_requirement": obj.get("security_requirement", ""),
                "discussion": obj.get("discussion", ""),
                "objectives": []
            }

        obj["artifacts"] = artifacts_by_obj.get(obj["id"], [])
        obj["assignments"] = assignments_by_obj.get(obj["id"], [])
        fd["artifact_count"] += len(obj["artifacts"])
        fd["requirements"][req_id]["objectives"].append(obj)

    pct_complete = round(totals["captured"] / totals["total"] * 100, 1) if totals["total"] else 0
    org_name = os.environ.get("ORG_NAME", "Organization")
    generated_date = datetime.now().strftime("%B %d, %Y")

    return render_template("report.html",
                           totals=totals, families=families,
                           family_details=family_details,
                           pct_complete=pct_complete,
                           org_name=org_name,
                           generated_date=generated_date,
                           abbr=FAMILY_ABBR, colors=FAMILY_COLORS)


@reports_bp.route("/audit")
@admin_required
def audit_log_page():
    page = request.args.get("page", 1, type=int)
    per_page = 50
    filter_user = request.args.get("user", "")
    filter_action = request.args.get("action", "")
    filter_from = request.args.get("from", "")
    filter_to = request.args.get("to", "")

    conn = get_db()
    conditions = []
    params = []
    if filter_user:
        conditions.append("username = ?")
        params.append(filter_user)
    if filter_action:
        conditions.append("action = ?")
        params.append(filter_action)
    if filter_from:
        conditions.append("timestamp >= ?")
        params.append(filter_from + " 00:00:00")
    if filter_to:
        conditions.append("timestamp <= ?")
        params.append(filter_to + " 23:59:59")

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    total = conn.execute(f"SELECT COUNT(*) FROM audit_log {where}", params).fetchone()[0]
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, total_pages)
    offset = (page - 1) * per_page

    rows = conn.execute(
        f"SELECT * FROM audit_log {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    users = conn.execute("SELECT DISTINCT username FROM audit_log WHERE username IS NOT NULL ORDER BY username").fetchall()
    actions = conn.execute("SELECT DISTINCT action FROM audit_log ORDER BY action").fetchall()
    conn.close()

    return render_template("audit.html", logs=rows, page=page, total_pages=total_pages,
                           total=total, users=[u[0] for u in users],
                           actions=[a[0] for a in actions],
                           filter_user=filter_user, filter_action=filter_action,
                           filter_from=filter_from, filter_to=filter_to)
