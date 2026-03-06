"""Pages blueprint: landing page, config page, member detail."""

from datetime import datetime

from flask import Blueprint, render_template

from models import get_db, FAMILY_ABBR, FAMILY_COLORS
from utils import admin_required, get_org_id

pages_bp = Blueprint('pages', __name__)


@pages_bp.route("/landing")
def landing():
    return render_template("landing.html")


@pages_bp.route("/config")
@admin_required
def config_page():
    org_id = get_org_id()
    conn = get_db()
    members = conn.execute("SELECT * FROM team_members WHERE org_id = ? ORDER BY name", (org_id,)).fetchall()
    counts = {}
    for m in members:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM artifact_assignments WHERE member_id = ?",
            (m["id"],)
        ).fetchone()
        counts[m["id"]] = row["c"]
    domains = conn.execute("SELECT * FROM domains WHERE org_id = ? ORDER BY name", (org_id,)).fetchall()
    conn.close()
    return render_template("config.html", members=members, counts=counts, domains=domains)


@pages_bp.route("/member/<int:member_id>")
def member_detail(member_id):
    conn = get_db()
    member = conn.execute("SELECT * FROM team_members WHERE id = ?", (member_id,)).fetchone()
    if not member:
        conn.close()
        return "Member not found", 404
    org_id = get_org_id()
    assignments = conn.execute("""
        SELECT a.id, a.objective_id, a.member_id, a.status as assign_status,
               a.due_date, a.assigned_at,
               o.family, o.assessment_objective,
               COALESCE(p.captured, 0) as captured, p.captured_date,
               COALESCE(p.artifact_notes, '') as artifact_notes
        FROM artifact_assignments a
        JOIN objectives o ON a.objective_id = o.id
        LEFT JOIN objective_progress p ON o.id = p.objective_id AND p.org_id = ?
        WHERE a.member_id = ? AND a.org_id = ?
        ORDER BY o.sort_as
    """, (org_id, member_id, org_id)).fetchall()
    total = len(assignments)
    completed = sum(1 for a in assignments if a["captured"])
    overdue = sum(1 for a in assignments if a["due_date"] and a["due_date"] < datetime.now().strftime("%Y-%m-%d") and not a["captured"])
    by_family = {}
    for a in assignments:
        fam = a["family"]
        if fam not in by_family:
            by_family[fam] = {"total": 0, "completed": 0, "items": []}
        by_family[fam]["total"] += 1
        if a["captured"]:
            by_family[fam]["completed"] += 1
        by_family[fam]["items"].append(dict(a))
    conn.close()
    return render_template("member.html", member=member, assignments=assignments,
                           total=total, completed=completed, overdue=overdue,
                           by_family=by_family, abbr=FAMILY_ABBR, colors=FAMILY_COLORS,
                           now=datetime.now().strftime("%Y-%m-%d"))
