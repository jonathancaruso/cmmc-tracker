"""Organizations blueprint: multi-tenant org management, switching, and CRUD."""

import re
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for

from models import get_db, seed_org_progress
from utils import log_audit, admin_required, get_org_id

orgs_bp = Blueprint('orgs', __name__)


def _slugify(name):
    """Convert org name to URL-safe slug."""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug or 'org'


@orgs_bp.route("/organizations")
@admin_required
def orgs_page():
    conn = get_db()
    orgs = conn.execute("""
        SELECT o.*, COUNT(u.id) as user_count
        FROM organizations o
        LEFT JOIN users u ON u.org_id = o.id
        GROUP BY o.id
        ORDER BY o.name
    """).fetchall()
    conn.close()
    return render_template("organizations.html", orgs=orgs)


@orgs_bp.route("/api/organizations", methods=["POST"])
@admin_required
def create_org():
    data = request.json
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Organization name is required"}), 400
    slug = _slugify(name)
    conn = get_db()
    # Ensure unique slug
    existing = conn.execute("SELECT id FROM organizations WHERE slug = ?", (slug,)).fetchone()
    if existing:
        slug = f"{slug}-{int(datetime.now().timestamp())}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.execute(
        "INSERT INTO organizations (name, slug, created_at) VALUES (?, ?, ?)",
        (name, slug, now)
    )
    org_id = cursor.lastrowid
    conn.commit()
    conn.close()
    # Seed objective_progress for new org
    count = seed_org_progress(org_id)
    log_audit('created', 'organization', str(org_id),
              f"Created organization '{name}' (slug: {slug}, {count} objectives seeded)")
    return jsonify({"ok": True, "id": org_id, "slug": slug})


@orgs_bp.route("/api/organizations/<int:org_id>", methods=["PATCH"])
@admin_required
def update_org(org_id):
    data = request.json
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Organization name is required"}), 400
    conn = get_db()
    org = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
    if not org:
        conn.close()
        return jsonify({"error": "Organization not found"}), 404
    conn.execute("UPDATE organizations SET name = ? WHERE id = ?", (name, org_id))
    log_audit('edited', 'organization', str(org_id), f"Renamed to '{name}'", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@orgs_bp.route("/api/organizations/<int:org_id>", methods=["DELETE"])
@admin_required
def delete_org(org_id):
    if org_id == 1:
        return jsonify({"error": "Cannot delete the default organization"}), 400
    conn = get_db()
    org = conn.execute("SELECT name FROM organizations WHERE id = ?", (org_id,)).fetchone()
    if not org:
        conn.close()
        return jsonify({"error": "Organization not found"}), 404
    # Check for users still in this org
    user_count = conn.execute("SELECT COUNT(*) FROM users WHERE org_id = ?", (org_id,)).fetchone()[0]
    if user_count > 0:
        conn.close()
        return jsonify({"error": f"Cannot delete: {user_count} users still belong to this organization"}), 400
    # Delete org-scoped data
    for table in ['objective_progress', 'artifact_assignments', 'objective_comments',
                  'poam', 'ssp_mappings', 'team_members', 'domains', 'audit_log']:
        conn.execute(f"DELETE FROM {table} WHERE org_id = ?", (org_id,))
    # Delete artifacts (and their files)
    artifacts = conn.execute("SELECT filename FROM artifacts WHERE org_id = ?", (org_id,)).fetchall()
    import os
    from models import UPLOAD_DIR
    for art in artifacts:
        filepath = os.path.join(UPLOAD_DIR, art['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
    conn.execute("DELETE FROM artifact_objectives WHERE artifact_id IN (SELECT id FROM artifacts WHERE org_id = ?)",
                 (org_id,))
    conn.execute("DELETE FROM artifacts WHERE org_id = ?", (org_id,))
    conn.execute("DELETE FROM organizations WHERE id = ?", (org_id,))
    log_audit('deleted', 'organization', str(org_id), f"Deleted organization '{org['name']}'", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@orgs_bp.route("/api/organizations/switch", methods=["POST"])
def switch_org():
    """Switch active organization for current user session."""
    data = request.json
    org_id = data.get("org_id")
    if not org_id:
        return jsonify({"error": "org_id required"}), 400
    conn = get_db()
    org = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
    if not org:
        conn.close()
        return jsonify({"error": "Organization not found"}), 404
    # Only admins can switch to any org; regular users stay in their own
    user_org = conn.execute("SELECT org_id FROM users WHERE id = ?", (session.get('user_id'),)).fetchone()
    if session.get('role') != 'admin' and user_org and user_org['org_id'] != org_id:
        conn.close()
        return jsonify({"error": "Not authorized to switch to this organization"}), 403
    conn.close()
    session['org_id'] = org_id
    session['org_name'] = org['name']
    log_audit('org_switch', 'organization', str(org_id), f"Switched to '{org['name']}'")
    return jsonify({"ok": True, "name": org['name']})
