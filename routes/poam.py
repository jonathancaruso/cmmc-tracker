"""POA&M blueprint: Plan of Action & Milestones page, API, and CSV export."""

import csv
import io
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, Response

from models import get_db, FAMILY_ABBR, FAMILY_COLORS
from utils import log_audit

poam_bp = Blueprint('poam', __name__)


@poam_bp.route("/poam")
def poam_page():
    conn = get_db()
    rows = conn.execute("""
        SELECT o.id, o.family, o.requirement_id, o.assessment_objective, o.status,
               o.artifact_notes, o.security_requirement,
               p.weakness, p.remediation, p.resources, p.milestone_date, p.risk_level,
               GROUP_CONCAT(t.name, '; ') as assigned_to
        FROM objectives o
        LEFT JOIN poam p ON o.id = p.objective_id
        LEFT JOIN artifact_assignments a ON o.id = a.objective_id
        LEFT JOIN team_members t ON a.member_id = t.id
        WHERE o.captured = 0
        GROUP BY o.id
        ORDER BY o.sort_as
    """).fetchall()
    total_incomplete = len(rows)
    with_plan = sum(1 for r in rows if r['remediation'])
    by_risk = {'High': 0, 'Moderate': 0, 'Low': 0}
    for r in rows:
        risk = r['risk_level'] or 'Moderate'
        if risk in by_risk:
            by_risk[risk] += 1
    conn.close()
    return render_template("poam.html", items=rows, total=total_incomplete,
                           with_plan=with_plan, by_risk=by_risk,
                           abbr=FAMILY_ABBR, colors=FAMILY_COLORS)


@poam_bp.route("/api/poam", methods=["POST"])
def update_poam():
    data = request.json
    obj_id = data.get("objective_id")
    if not obj_id:
        return jsonify({"error": "objective_id required"}), 400
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    existing = conn.execute("SELECT id FROM poam WHERE objective_id = ?", (obj_id,)).fetchone()
    if existing:
        conn.execute("""
            UPDATE poam SET weakness=?, remediation=?, resources=?,
                   milestone_date=?, risk_level=?, updated_at=?
            WHERE objective_id=?
        """, (data.get("weakness", ""), data.get("remediation", ""),
              data.get("resources", ""), data.get("milestone_date") or None,
              data.get("risk_level", "Moderate"), now, obj_id))
    else:
        conn.execute("""
            INSERT INTO poam (objective_id, weakness, remediation, resources,
                              milestone_date, risk_level, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (obj_id, data.get("weakness", ""), data.get("remediation", ""),
              data.get("resources", ""), data.get("milestone_date") or None,
              data.get("risk_level", "Moderate"), now))
    log_audit('poam_saved', 'poam', obj_id,
              f"POA&M {'updated' if existing else 'created'} for {obj_id} (risk: {data.get('risk_level', 'Moderate')})",
              conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@poam_bp.route("/api/poam/export")
def export_poam_csv():
    conn = get_db()
    rows = conn.execute("""
        SELECT o.id, o.family, o.requirement_id, o.assessment_objective, o.status,
               o.security_requirement,
               COALESCE(p.weakness, '') as weakness,
               COALESCE(p.remediation, '') as remediation,
               COALESCE(p.resources, '') as resources,
               COALESCE(p.milestone_date, '') as milestone_date,
               COALESCE(p.risk_level, 'Moderate') as risk_level,
               GROUP_CONCAT(t.name, '; ') as assigned_to
        FROM objectives o
        LEFT JOIN poam p ON o.id = p.objective_id
        LEFT JOIN artifact_assignments a ON o.id = a.objective_id
        LEFT JOIN team_members t ON a.member_id = t.id
        WHERE o.captured = 0
        GROUP BY o.id
        ORDER BY o.sort_as
    """).fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["POA&M ID", "Requirement", "Objective ID", "Assessment Objective",
                     "Status", "Risk Level", "Weakness", "Remediation Plan",
                     "Resources Required", "Milestone Date", "Responsible Party"])
    for i, r in enumerate(rows, 1):
        writer.writerow([f"POAM-{i:04d}", r["requirement_id"], r["id"],
                         r["assessment_objective"], r["status"] or "Not Started",
                         r["risk_level"], r["weakness"], r["remediation"],
                         r["resources"], r["milestone_date"],
                         r["assigned_to"] or "Unassigned"])
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=poam-report.csv"})
