"""Authentication blueprint: login, logout, initial setup, user management, password validation."""

import sqlite3
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

from models import get_db
from utils import validate_password, log_audit, _check_rate_limit

auth_bp = Blueprint('auth', __name__)


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    conn = get_db()
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    if user_count > 0:
        return redirect(url_for('auth.login'))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        confirm = request.form.get("confirm_password", "")
        errors = []
        if not username:
            errors.append("Username is required")
        if not first_name or not last_name:
            errors.append("First and last name are required")
        if password != confirm:
            errors.append("Passwords do not match")
        errors.extend(validate_password(password))
        if errors:
            return render_template("setup.html", errors=errors, username=username,
                                   first_name=first_name, last_name=last_name)
        conn = get_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        display_name = f"{first_name} {last_name}"
        conn.execute(
            "INSERT INTO users (username, password_hash, role, first_name, last_name, created_at, org_id) VALUES (?, ?, ?, ?, ?, ?, 1)",
            (username, generate_password_hash(password), 'admin', first_name, last_name, now)
        )
        conn.execute(
            "INSERT INTO team_members (name, role, email, created_at) VALUES (?, ?, ?, ?)",
            (display_name, 'admin', '', now)
        )
        conn.commit()
        conn2 = get_db()
        user_row = conn2.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        conn2.execute(
            "INSERT INTO audit_log (user_id, username, action, target_type, target_id, details, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_row['id'], username, 'created', 'user', str(user_row['id']),
             f"Initial admin user {first_name} {last_name} ({username}) created via setup",
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn2.commit()
        conn2.close()
        conn.close()
        return redirect(url_for('auth.login'))
    return render_template("setup.html", errors=[], username="")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        client_ip = request.remote_addr
        if not _check_rate_limit(client_ip):
            return render_template("login.html", error="Too many login attempts. Please wait 5 minutes.")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['org_id'] = user['org_id'] or 1
            # Load org name
            conn2 = get_db()
            org = conn2.execute("SELECT name FROM organizations WHERE id = ?", (session['org_id'],)).fetchone()
            session['org_name'] = org['name'] if org else 'Default Organization'
            conn2.close()
            return redirect(url_for('dashboard.dashboard'))
        return render_template("login.html", error="Invalid username or password")
    return render_template("login.html", error=None)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
