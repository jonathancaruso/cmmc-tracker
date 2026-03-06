"""Team blueprint: team members CRUD and domains CRUD."""

import sqlite3
from datetime import datetime

from flask import Blueprint, request, jsonify

from models import get_db
from utils import log_audit, admin_required, get_org_id

team_bp = Blueprint('team', __name__)


@team_bp.route("/api/team", methods=["GET"])
def list_team():
    org_id = get_org_id()
    conn = get_db()
    members = conn.execute("SELECT * FROM team_members WHERE org_id = ? ORDER BY name", (org_id,)).fetchall()
    conn.close()
    return jsonify([dict(m) for m in members])


@team_bp.route("/api/team", methods=["POST"])
@admin_required
def add_team_member():
    data = request.json
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    org_id = get_org_id()
    conn = get_db()
    conn.execute(
        "INSERT INTO team_members (name, role, email, created_at, org_id) VALUES (?, ?, ?, ?, ?)",
        (name, data.get("role", ""), data.get("email", ""),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"), org_id)
    )
    log_audit('created', 'team', name, f"Created team member {name}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@team_bp.route("/api/team/<int:member_id>", methods=["DELETE"])
@admin_required
def delete_team_member(member_id):
    conn = get_db()
    member = conn.execute("SELECT name FROM team_members WHERE id = ?", (member_id,)).fetchone()
    conn.execute("DELETE FROM artifact_assignments WHERE member_id = ?", (member_id,))
    conn.execute("DELETE FROM team_members WHERE id = ?", (member_id,))
    log_audit('deleted', 'team', member_id,
              f"Deleted team member {member['name']}" if member else f"Deleted team member #{member_id}",
              conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@team_bp.route("/api/team/<int:member_id>", methods=["PATCH"])
@admin_required
def update_team_member(member_id):
    data = request.json
    conn = get_db()
    conn.execute(
        "UPDATE team_members SET name = ?, role = ?, email = ? WHERE id = ?",
        (data.get("name", ""), data.get("role", ""), data.get("email", ""), member_id)
    )
    log_audit('edited', 'team', member_id, f"Updated team member {data.get('name', '')}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@team_bp.route("/api/domains", methods=["GET"])
def list_domains():
    org_id = get_org_id()
    conn = get_db()
    rows = conn.execute("SELECT * FROM domains WHERE org_id = ? ORDER BY name", (org_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@team_bp.route("/api/domains", methods=["POST"])
@admin_required
def add_domain():
    data = request.json
    name = data.get("name", "").strip()
    color = data.get("color", "#6366f1").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    org_id = get_org_id()
    conn = get_db()
    try:
        conn.execute("INSERT INTO domains (name, color, org_id) VALUES (?, ?, ?)", (name, color, org_id))
        log_audit('created', 'domain', name, f"Created domain {name}", conn=conn)
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Domain already exists"}), 409
    conn.close()
    return jsonify({"ok": True})


@team_bp.route("/api/domains/<int:domain_id>", methods=["PATCH"])
@admin_required
def update_domain(domain_id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE domains SET name = ?, color = ? WHERE id = ?",
                 (data.get("name", "").strip(), data.get("color", "#6366f1").strip(), domain_id))
    log_audit('edited', 'domain', domain_id, f"Updated domain {data.get('name', '')}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@team_bp.route("/api/domains/<int:domain_id>", methods=["DELETE"])
@admin_required
def delete_domain(domain_id):
    conn = get_db()
    domain = conn.execute("SELECT name FROM domains WHERE id = ?", (domain_id,)).fetchone()
    conn.execute("UPDATE artifacts SET domain_id = NULL WHERE domain_id = ?", (domain_id,))
    conn.execute("DELETE FROM domains WHERE id = ?", (domain_id,))
    log_audit('deleted', 'domain', domain_id,
              f"Deleted domain {domain['name']}" if domain else f"Deleted domain #{domain_id}",
              conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})
