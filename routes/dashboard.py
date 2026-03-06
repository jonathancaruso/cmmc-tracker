"""Dashboard blueprint: main dashboard and search pages."""

from flask import Blueprint, render_template, request, jsonify, session

from models import get_db, FAMILY_ABBR, FAMILY_COLORS
from utils import get_org_id

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route("/")
def dashboard():
    org_id = get_org_id()
    conn = get_db()
    families = conn.execute("""
        SELECT o.family,
               COUNT(*) as total,
               SUM(CASE WHEN p.captured = 1 THEN 1 ELSE 0 END) as captured,
               SUM(CASE WHEN p.status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
               SUM(CASE WHEN p.status = 'Evidence Collected' THEN 1 ELSE 0 END) as evidence_collected,
               SUM(CASE WHEN p.status = 'Reviewed' THEN 1 ELSE 0 END) as reviewed,
               COUNT(DISTINCT a.objective_id) as objectives_with_evidence,
               COALESCE(SUM(CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END), 0) as artifact_count
        FROM objectives o
        LEFT JOIN objective_progress p ON o.id = p.objective_id AND p.org_id = ?
        LEFT JOIN artifacts a ON o.id = a.objective_id AND a.org_id = ?
        GROUP BY o.family ORDER BY o.family
    """, (org_id, org_id)).fetchall()
    totals = conn.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN p.captured = 1 THEN 1 ELSE 0 END) as captured,
               SUM(CASE WHEN p.status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
               SUM(CASE WHEN p.status = 'Evidence Collected' THEN 1 ELSE 0 END) as evidence_collected,
               SUM(CASE WHEN p.status = 'Reviewed' THEN 1 ELSE 0 END) as reviewed,
               COUNT(DISTINCT a.objective_id) as objectives_with_evidence,
               COALESCE(SUM(CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END), 0) as artifact_count
        FROM objectives o
        LEFT JOIN objective_progress p ON o.id = p.objective_id AND p.org_id = ?
        LEFT JOIN artifacts a ON o.id = a.objective_id AND a.org_id = ?
    """, (org_id, org_id)).fetchone()
    domain_coverage = conn.execute("""
        SELECT d.id, d.name, d.color, COUNT(DISTINCT a.objective_id) as obj_count
        FROM domains d
        LEFT JOIN artifacts a ON d.id = a.domain_id AND a.org_id = ?
        WHERE d.org_id = ?
        GROUP BY d.id ORDER BY d.name
    """, (org_id, org_id)).fetchall()
    shared_artifacts = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT artifact_id FROM artifact_objectives ao
            JOIN artifacts a ON ao.artifact_id = a.id
            WHERE a.org_id = ?
            GROUP BY artifact_id HAVING COUNT(*) > 1
        )
    """, (org_id,)).fetchone()[0]
    # Get list of orgs for switcher
    orgs = conn.execute("SELECT id, name FROM organizations ORDER BY name").fetchall()
    conn.close()
    return render_template("dashboard.html",
                           families=families, totals=totals,
                           abbr=FAMILY_ABBR, colors=FAMILY_COLORS,
                           domain_coverage=domain_coverage,
                           shared_artifacts=shared_artifacts,
                           orgs=orgs)


@dashboard_bp.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    org_id = get_org_id()
    conn = get_db()
    results = conn.execute("""
        SELECT o.id, o.family, o.requirement_id, o.assessment_objective,
               COALESCE(p.captured, 0) as prog_captured,
               COALESCE(p.status, 'Not Started') as prog_status
        FROM objectives o
        LEFT JOIN objective_progress p ON o.id = p.objective_id AND p.org_id = ?
        WHERE o.id LIKE ? OR o.assessment_objective LIKE ?
              OR o.family LIKE ? OR o.requirement_id LIKE ?
              OR o.security_requirement LIKE ?
        ORDER BY o.sort_as LIMIT 50
    """, (org_id, f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    # Remap column names for API compatibility
    results = [{'id': r['id'], 'family': r['family'], 'requirement_id': r['requirement_id'],
                'assessment_objective': r['assessment_objective'],
                'captured': r['prog_captured'], 'status': r['prog_status']} for r in results]
    conn.close()
    return jsonify([dict(r) for r in results])


@dashboard_bp.route("/search")
def search_page():
    q = request.args.get("q", "").strip()
    org_id = get_org_id()
    results = []
    if q:
        conn = get_db()
        results = conn.execute("""
            SELECT o.id, o.family, o.requirement_id, o.sort_as,
                   o.security_requirement, o.assessment_objective,
                   o.examine, o.interview, o.test,
                   o.requirement_type, o.discussion,
                   COALESCE(p.captured, 0) as captured,
                   COALESCE(p.status, 'Not Started') as status,
                   COALESCE(p.artifact_notes, '') as artifact_notes,
                   p.captured_date,
                   GROUP_CONCAT(t.name, '; ') as assigned_to
            FROM objectives o
            LEFT JOIN objective_progress p ON o.id = p.objective_id AND p.org_id = ?
            LEFT JOIN artifact_assignments a ON o.id = a.objective_id AND a.org_id = ?
            LEFT JOIN team_members t ON a.member_id = t.id
            WHERE o.id LIKE ? OR o.assessment_objective LIKE ?
                  OR o.family LIKE ? OR o.requirement_id LIKE ?
                  OR o.security_requirement LIKE ?
            GROUP BY o.id
            ORDER BY o.sort_as
        """, (org_id, org_id, f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
        conn.close()
    return render_template("search.html", q=q, results=results, abbr=FAMILY_ABBR, colors=FAMILY_COLORS)
