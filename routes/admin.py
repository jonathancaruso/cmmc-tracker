"""Admin blueprint: user administration CRUD (create, edit, delete, password reset)."""

import sqlite3
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash

from models import get_db
from utils import validate_password, log_audit, admin_required

admin_bp = Blueprint('admin', __name__)


@admin_bp.route("/admin/users")
@admin_required
def admin_users():
    conn = get_db()
    users = conn.execute("SELECT id, username, role, first_name, last_name, created_at FROM users ORDER BY created_at").fetchall()
    conn.close()
    return render_template("admin_users.html", users=users)


@admin_bp.route("/api/admin/users", methods=["POST"])
@admin_required
def admin_create_user():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "user")
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    if role not in ('admin', 'user'):
        return jsonify({"error": "Invalid role"}), 400
    if not username:
        return jsonify({"error": "Username is required"}), 400
    if not first_name or not last_name:
        return jsonify({"error": "First and last name are required"}), 400
    errors = validate_password(password)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    display_name = f"{first_name} {last_name}"
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, first_name, last_name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (username, generate_password_hash(password), role, first_name, last_name, now)
        )
        conn.execute(
            "INSERT INTO team_members (name, role, email, created_at) VALUES (?, ?, ?, ?)",
            (display_name, role, '', now)
        )
        log_audit('created', 'user', username,
                  f"Created user {first_name} {last_name} ({username}) as {role}", conn=conn)
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Username already exists"}), 409
    conn.close()
    return jsonify({"ok": True})


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["PATCH"])
@admin_required
def admin_edit_user(user_id):
    data = request.json
    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    role = data.get("role", "").strip()
    if not first_name or not last_name:
        return jsonify({"error": "First and last name are required"}), 400
    if role not in ('admin', 'user'):
        return jsonify({"error": "Invalid role"}), 400
    conn = get_db()
    old_user = conn.execute("SELECT username, first_name, last_name, role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not old_user:
        conn.close()
        return jsonify({"error": "User not found"}), 404
    if user_id == session.get('user_id') and role != 'admin':
        conn.close()
        return jsonify({"error": "Cannot remove your own admin role"}), 400
    old_display = f"{old_user['first_name']} {old_user['last_name']}"
    new_display = f"{first_name} {last_name}"
    conn.execute("UPDATE users SET first_name = ?, last_name = ?, role = ? WHERE id = ?",
                 (first_name, last_name, role, user_id))
    if old_display != new_display:
        conn.execute("UPDATE team_members SET name = ? WHERE name = ?", (new_display, old_display))
    if old_user['role'] != role:
        conn.execute("UPDATE team_members SET role = ? WHERE name = ?", (role, new_display))
    conn.commit()
    changes = []
    if old_user['first_name'] != first_name or old_user['last_name'] != last_name:
        changes.append(f"Name: {old_display} -> {new_display}")
    if old_user['role'] != role:
        changes.append(f"Role: {old_user['role']} -> {role}")
    if changes:
        log_audit('edit_user', 'user', str(user_id), '; '.join(changes), conn=conn)
    conn.close()
    return jsonify({"ok": True})


@admin_bp.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@admin_required
def admin_delete_user(user_id):
    if user_id == session.get('user_id'):
        return jsonify({"error": "Cannot delete yourself"}), 400
    conn = get_db()
    user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    if user:
        conn.execute("DELETE FROM artifact_assignments WHERE member_id IN (SELECT id FROM team_members WHERE name = ?)", (user['username'],))
        conn.execute("DELETE FROM team_members WHERE name = ?", (user['username'],))
    log_audit('deleted', 'user', user_id,
              f"Deleted user {user['username']}" if user else f"Deleted user #{user_id}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@admin_bp.route("/api/admin/users/<int:user_id>/reset", methods=["POST"])
@admin_required
def admin_reset_password(user_id):
    data = request.json
    password = data.get("password", "")
    errors = validate_password(password)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400
    conn = get_db()
    user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                 (generate_password_hash(password), user_id))
    log_audit('password_reset', 'user', user_id,
              f"Password reset for {user['username']}" if user else f"Password reset for user #{user_id}",
              conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})
