"""Dashboard blueprint: main dashboard and search pages."""

from flask import Blueprint, render_template, request, jsonify

from models import get_db, FAMILY_ABBR, FAMILY_COLORS

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route("/")
def dashboard():
    conn = get_db()
    families = conn.execute("""
        SELECT o.family,
               COUNT(*) as total,
               SUM(CASE WHEN o.captured = 1 THEN 1 ELSE 0 END) as captured,
               SUM(CASE WHEN o.status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
               SUM(CASE WHEN o.status = 'Evidence Collected' THEN 1 ELSE 0 END) as evidence_collected,
               SUM(CASE WHEN o.status = 'Reviewed' THEN 1 ELSE 0 END) as reviewed,
               COUNT(DISTINCT a.objective_id) as objectives_with_evidence,
               COALESCE(SUM(CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END), 0) as artifact_count
        FROM objectives o
        LEFT JOIN artifacts a ON o.id = a.objective_id
        GROUP BY o.family ORDER BY o.family
    """).fetchall()
    totals = conn.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN o.captured = 1 THEN 1 ELSE 0 END) as captured,
               SUM(CASE WHEN o.status = 'In Progress' THEN 1 ELSE 0 END) as in_progress,
               SUM(CASE WHEN o.status = 'Evidence Collected' THEN 1 ELSE 0 END) as evidence_collected,
               SUM(CASE WHEN o.status = 'Reviewed' THEN 1 ELSE 0 END) as reviewed,
               COUNT(DISTINCT a.objective_id) as objectives_with_evidence,
               COALESCE(SUM(CASE WHEN a.id IS NOT NULL THEN 1 ELSE 0 END), 0) as artifact_count
        FROM objectives o
        LEFT JOIN artifacts a ON o.id = a.objective_id
    """).fetchone()
    domain_coverage = conn.execute("""
        SELECT d.id, d.name, d.color, COUNT(DISTINCT a.objective_id) as obj_count
        FROM domains d
        LEFT JOIN artifacts a ON d.id = a.domain_id
        GROUP BY d.id ORDER BY d.name
    """).fetchall()
    shared_artifacts = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT artifact_id FROM artifact_objectives
            GROUP BY artifact_id HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    conn.close()
    return render_template("dashboard.html",
                           families=families, totals=totals,
                           abbr=FAMILY_ABBR, colors=FAMILY_COLORS,
                           domain_coverage=domain_coverage,
                           shared_artifacts=shared_artifacts)


@dashboard_bp.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    conn = get_db()
    results = conn.execute("""
        SELECT id, family, requirement_id, assessment_objective, captured, status
        FROM objectives
        WHERE id LIKE ? OR assessment_objective LIKE ?
              OR family LIKE ? OR requirement_id LIKE ?
              OR security_requirement LIKE ?
        ORDER BY sort_as LIMIT 50
    """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    conn.close()
    return jsonify([dict(r) for r in results])


@dashboard_bp.route("/search")
def search_page():
    q = request.args.get("q", "").strip()
    results = []
    if q:
        conn = get_db()
        results = conn.execute("""
            SELECT o.*, GROUP_CONCAT(t.name, '; ') as assigned_to
            FROM objectives o
            LEFT JOIN artifact_assignments a ON o.id = a.objective_id
            LEFT JOIN team_members t ON a.member_id = t.id
            WHERE o.id LIKE ? OR o.assessment_objective LIKE ?
                  OR o.family LIKE ? OR o.requirement_id LIKE ?
                  OR o.security_requirement LIKE ?
            GROUP BY o.id
            ORDER BY o.sort_as
        """, (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
        conn.close()
    return render_template("search.html", q=q, results=results, abbr=FAMILY_ABBR, colors=FAMILY_COLORS)
