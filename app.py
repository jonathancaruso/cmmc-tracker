#!/usr/bin/env python3
"""CMMC Artifact Tracker -- Flask app factory, configuration, and middleware."""

import os
import secrets
import sys

from flask import Flask, render_template, request, jsonify, redirect, url_for, session, abort

from models import get_db, init_db


def create_app():
    app = Flask(__name__)

    # --- Secret key ---
    _secret = os.environ.get("FLASK_SECRET")
    if not _secret:
        _secret = secrets.token_hex(32)
        print("WARNING: FLASK_SECRET not set. Using random key -- sessions will not survive restarts. "
              "Set FLASK_SECRET env var for production.", file=sys.stderr)
    app.secret_key = _secret

    # --- Session / cookie security ---
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = os.environ.get("FLASK_ENV") == "production"
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB upload limit

    # --- Register blueprints ---
    from auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.family import family_bp
    from routes.artifacts import artifacts_bp
    from routes.assignments import assignments_bp
    from routes.team import team_bp
    from routes.poam import poam_bp
    from routes.comments import comments_bp
    from routes.reports import reports_bp
    from routes.admin import admin_bp
    from routes.pages import pages_bp
    from routes.backup import backup_bp
    from routes.ssp import ssp_bp
    from routes.notifications import notifications_bp
    from routes.organizations import orgs_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(family_bp)
    app.register_blueprint(artifacts_bp)
    app.register_blueprint(assignments_bp)
    app.register_blueprint(team_bp)
    app.register_blueprint(poam_bp)
    app.register_blueprint(comments_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(ssp_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(orgs_bp)

    # --- Auth middleware ---
    @app.before_request
    def check_auth():
        if request.endpoint in ('static', None):
            return
        PUBLIC_ENDPOINTS = {'auth.login', 'auth.setup', 'pages.landing'}
        conn = get_db()
        user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        if user_count == 0:
            if request.endpoint != 'auth.setup':
                return redirect(url_for('auth.setup'))
            return
        if request.endpoint in PUBLIC_ENDPOINTS:
            if 'user_id' in session:
                return redirect(url_for('dashboard.dashboard'))
            return
        if 'user_id' not in session:
            if request.path.startswith('/api/') or request.path.startswith('/uploads/'):
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for('auth.login'))

    # --- CSRF protection ---
    @app.before_request
    def csrf_protect():
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return
        if request.endpoint in ('static', None):
            return
        if request.endpoint == 'auth.logout':
            return
        if request.endpoint in ('auth.login', 'auth.setup'):
            token = request.form.get('csrf_token', '')
            if not token or token != session.get('csrf_token'):
                if request.endpoint == 'auth.login':
                    return render_template("login.html", error="Session expired. Please try again.")
                abort(403)
            return
        token = request.headers.get('X-CSRF-Token', '') or request.form.get('csrf_token', '')
        if not token or token != session.get('csrf_token'):
            return jsonify({"error": "CSRF token missing or invalid"}), 403

    # --- CSRF token generation ---
    def generate_csrf_token():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(32)
        return session['csrf_token']

    @app.context_processor
    def inject_csrf():
        return {'csrf_token': generate_csrf_token}

    # --- Inject current user into templates ---
    @app.context_processor
    def inject_user():
        ctx = {'current_user': None, 'current_org': None, 'all_orgs': []}
        if 'user_id' in session:
            conn = get_db()
            user = conn.execute("SELECT id, username, role, first_name, last_name, org_id FROM users WHERE id = ?",
                                (session['user_id'],)).fetchone()
            if user:
                ctx['current_user'] = dict(user)
                org_id = session.get('org_id', user['org_id'] or 1)
                org = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
                ctx['current_org'] = dict(org) if org else {'id': 1, 'name': 'Default Organization'}
                if user['role'] == 'admin':
                    ctx['all_orgs'] = [dict(o) for o in conn.execute("SELECT id, name FROM organizations ORDER BY name").fetchall()]
            conn.close()
        return ctx

    # --- Security headers ---
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none';"
        )
        if os.environ.get("FLASK_ENV") == "production":
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # --- Error handlers ---
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Not found"}), 404
        return "Page not found", 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large. Maximum size is 100 MB."}), 413

    @app.errorhandler(500)
    def internal_error(e):
        if request.path.startswith('/api/'):
            return jsonify({"error": "Internal server error"}), 500
        return "Internal server error", 500

    return app


if __name__ == "__main__":
    app = create_app()
    init_db()
    # Seed example artifacts if not already done
    from seed_examples import seed_examples
    from seed_examples_supplement import seed_supplement
    conn_check = get_db()
    try:
        sample = conn_check.execute("SELECT example_artifacts FROM objectives LIMIT 1").fetchone()
        if sample and not sample["example_artifacts"]:
            conn_check.close()
            seed_examples()
            seed_supplement()
        else:
            conn_check.close()
    except Exception:
        conn_check.close()
        try:
            conn_check2 = get_db()
            conn_check2.execute("ALTER TABLE objectives ADD COLUMN example_artifacts TEXT DEFAULT ''")
            conn_check2.commit()
            conn_check2.close()
            seed_examples()
            seed_supplement()
        except Exception:
            pass

    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=3300, debug=debug)
