#!/usr/bin/env python3
"""CMMC Artifact Tracker — Flask + SQLite"""

import os
import re
import sqlite3
import csv
import io
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response, redirect, url_for, session
from openpyxl import load_workbook
import functools
import secrets
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET") or secrets.token_hex(32)
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "cmmc.db"))
XLSX_PATH = os.path.join(os.path.dirname(__file__), "nist-800-171a.xlsx")
XLSX_171_PATH = os.path.join(os.path.dirname(__file__), "nist-800-171.xlsx")
UPLOAD_DIR = os.environ.get("UPLOAD_PATH", os.path.join(os.path.dirname(__file__), "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.pdf', '.doc', '.docx',
                      '.xls', '.xlsx', '.txt', '.csv', '.pptx', '.zip', '.md'}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    # Create all tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS objectives (
            id TEXT PRIMARY KEY,
            family TEXT NOT NULL,
            requirement_id TEXT NOT NULL,
            sort_as TEXT,
            security_requirement TEXT,
            assessment_objective TEXT,
            examine TEXT,
            interview TEXT,
            test TEXT,
            captured INTEGER DEFAULT 0,
            artifact_notes TEXT DEFAULT '',
            captured_date TEXT,
            requirement_type TEXT DEFAULT '',
            discussion TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objective_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_size INTEGER,
            mime_type TEXT,
            uploaded_at TEXT NOT NULL,
            file_created TEXT,
            FOREIGN KEY (objective_id) REFERENCES objectives(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT DEFAULT '',
            email TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL DEFAULT '#6366f1'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS artifact_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objective_id TEXT NOT NULL,
            member_id INTEGER NOT NULL,
            status TEXT DEFAULT 'assigned',
            due_date TEXT,
            assigned_at TEXT NOT NULL,
            FOREIGN KEY (objective_id) REFERENCES objectives(id),
            FOREIGN KEY (member_id) REFERENCES team_members(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS poam (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            objective_id TEXT NOT NULL UNIQUE,
            weakness TEXT DEFAULT '',
            remediation TEXT DEFAULT '',
            resources TEXT DEFAULT '',
            milestone_date TEXT,
            risk_level TEXT DEFAULT 'Moderate',
            updated_at TEXT NOT NULL,
            FOREIGN KEY (objective_id) REFERENCES objectives(id)
        )
    """)
    conn.commit()

    # Migrate existing DBs: add columns if they don't exist
    for col in ["requirement_type", "discussion"]:
        try:
            conn.execute(f"SELECT {col} FROM objectives LIMIT 1")
        except Exception:
            try:
                conn.execute(f"ALTER TABLE objectives ADD COLUMN {col} TEXT DEFAULT ''")
            except Exception:
                pass

    # Add status column
    try:
        conn.execute("SELECT status FROM objectives LIMIT 1")
    except Exception:
        try:
            conn.execute("ALTER TABLE objectives ADD COLUMN status TEXT DEFAULT 'Not Started'")
            # Backfill: set captured objectives to 'Complete'
            conn.execute("UPDATE objectives SET status = 'Complete' WHERE captured = 1")
        except Exception:
            pass
    # Migrate: add domain_id to artifacts
    try:
        conn.execute("SELECT domain_id FROM artifacts LIMIT 1")
    except Exception:
        try:
            conn.execute("ALTER TABLE artifacts ADD COLUMN domain_id INTEGER REFERENCES domains(id)")
        except Exception:
            pass

    # Migrate: add file_created to artifacts
    try:
        conn.execute("SELECT file_created FROM artifacts LIMIT 1")
    except Exception:
        try:
            conn.execute("ALTER TABLE artifacts ADD COLUMN file_created TEXT")
        except Exception:
            pass

    # Migrate: add obtained_method to artifacts
    try:
        conn.execute("SELECT obtained_method FROM artifacts LIMIT 1")
    except Exception:
        try:
            conn.execute("ALTER TABLE artifacts ADD COLUMN obtained_method TEXT DEFAULT ''")
        except Exception:
            pass

    # No default domains — user adds their AD domains via config page

    conn.commit()

    # Check if objectives already seeded
    count = conn.execute("SELECT COUNT(*) FROM objectives").fetchone()[0]
    if count > 0:
        # Seed discussion if missing
        if os.path.exists(XLSX_171_PATH):
            sample = conn.execute("SELECT discussion FROM objectives WHERE requirement_id = '3.1.1' LIMIT 1").fetchone()
            if sample and not sample["discussion"]:
                wb2 = load_workbook(XLSX_171_PATH, read_only=True)
                ws2 = wb2["SP 800-171"]
                for row in ws2.iter_rows(min_row=2, values_only=True):
                    req_id = str(row[2] or "").strip()
                    req_type = str(row[1] or "").strip()
                    discussion = str(row[5] or "").strip()
                    if req_id:
                        conn.execute(
                            "UPDATE objectives SET requirement_type = ?, discussion = ? WHERE requirement_id = ?",
                            (req_type, discussion, req_id)
                        )
                conn.commit()
                wb2.close()
        conn.close()
        return

    # Parse xlsx — two passes: collect all rows, then insert
    wb = load_workbook(XLSX_PATH, read_only=True)
    ws = wb["SP800-171A"]
    current_family = ""
    current_req_id = ""
    current_sec_req = ""
    current_examine = ""
    current_interview = ""
    current_test = ""

    # Track which requirements have bracket sub-items
    all_rows = list(ws.iter_rows(min_row=2, values_only=True))
    reqs_with_brackets = set()
    for row in all_rows:
        ident = str(row[1] or "").strip()
        if "[" in ident:
            reqs_with_brackets.add(ident.split("[")[0])

    for row in all_rows:
        family = row[0] or current_family
        identifier = str(row[1] or "").strip()
        sort_as = str(row[2] or "").strip()
        sec_req = row[3]
        obj_text = row[4]
        examine = row[5]
        interview = row[6]
        test = row[7]

        if not identifier:
            continue

        current_family = family

        if "[" not in identifier:
            # Parent requirement row — save context for sub-items
            current_req_id = identifier
            current_sec_req = sec_req or ""
            current_examine = examine or ""
            current_interview = interview or ""
            current_test = test or ""
            current_sort_as = sort_as
            current_obj_text = obj_text or ""
            # If this requirement has no bracket sub-items, insert it as a single objective
            if identifier not in reqs_with_brackets and current_obj_text:
                # Strip "Determine if:" or "Determine If: " prefix
                obj_clean = current_obj_text
                for prefix in ("Determine if: ", "Determine If: ", "Determine if:", "Determine If:"):
                    if obj_clean.startswith(prefix):
                        obj_clean = obj_clean[len(prefix):].strip()
                        break
                conn.execute("""
                    INSERT OR IGNORE INTO objectives
                    (id, family, requirement_id, sort_as, security_requirement,
                     assessment_objective, examine, interview, test)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    identifier, current_family, identifier, sort_as,
                    current_sec_req, obj_clean,
                    current_examine, current_interview, current_test
                ))
        else:
            # Assessment objective row (bracketed sub-item)
            conn.execute("""
                INSERT OR IGNORE INTO objectives 
                (id, family, requirement_id, sort_as, security_requirement, 
                 assessment_objective, examine, interview, test)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                identifier, current_family, current_req_id, sort_as,
                current_sec_req, obj_text or "",
                current_examine, current_interview, current_test
            ))

    conn.commit()
    wb.close()
    print(f"Database seeded from {XLSX_PATH}")

    # Now seed discussion and requirement_type from SP 800-171
    if os.path.exists(XLSX_171_PATH):
        wb2 = load_workbook(XLSX_171_PATH, read_only=True)
        ws2 = wb2["SP 800-171"]
        for row in ws2.iter_rows(min_row=2, values_only=True):
            req_id = str(row[2] or "").strip()
            req_type = str(row[1] or "").strip()
            sec_req = str(row[4] or "").strip()
            discussion = str(row[5] or "").strip()
            if req_id:
                conn.execute(
                    "UPDATE objectives SET requirement_type = ?, discussion = ? WHERE requirement_id = ?",
                    (req_type, discussion, req_id)
                )
                # Backfill missing security_requirement text
                if sec_req:
                    import re
                    sec_req_clean = re.sub(r'\[\d+\]\.?', '', sec_req).strip()
                    conn.execute(
                        "UPDATE objectives SET security_requirement = ? WHERE requirement_id = ? AND (security_requirement IS NULL OR security_requirement = '')",
                        (sec_req_clean, req_id)
                    )
        conn.commit()
        wb2.close()
        print(f"Discussion and requirement types seeded from {XLSX_171_PATH}")

    conn.close()


def validate_password(password):
    errors = []
    if len(password) < 16:
        errors.append("Password must be at least 16 characters")
    if not re.search(r'[A-Z]', password):
        errors.append("Must contain an uppercase letter")
    if not re.search(r'[a-z]', password):
        errors.append("Must contain a lowercase letter")
    if not re.search(r'[0-9]', password):
        errors.append("Must contain a number")
    if not re.search(r'[^A-Za-z0-9]', password):
        errors.append("Must contain a special character")
    return errors


def admin_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))
        conn = get_db()
        user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if not user or user['role'] != 'admin':
            if request.path.startswith('/api/'):
                return jsonify({"error": "Admin access required"}), 403
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


@app.before_request
def check_auth():
    if request.endpoint in ('static', None):
        return
    PUBLIC_ENDPOINTS = {'login', 'setup'}
    conn = get_db()
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    if user_count == 0:
        if request.endpoint != 'setup':
            return redirect(url_for('setup'))
        return
    if request.endpoint in PUBLIC_ENDPOINTS:
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return
    if 'user_id' not in session:
        if request.path.startswith('/api/') or request.path.startswith('/uploads/'):
            return jsonify({"error": "Authentication required"}), 401
        return redirect(url_for('login'))


@app.context_processor
def inject_user():
    if 'user_id' in session:
        conn = get_db()
        user = conn.execute("SELECT id, username, role FROM users WHERE id = ?",
                            (session['user_id'],)).fetchone()
        conn.close()
        if user:
            return {'current_user': dict(user)}
    return {'current_user': None}


FAMILY_ABBR = {
    "Access Control": "AC",
    "Awareness and Training": "AT",
    "Audit and Accountability": "AU",
    "Configuration Management": "CM",
    "Identification and Authentication": "IA",
    "Incident Response": "IR",
    "Maintenance": "MA",
    "Media Protection": "MP",
    "Personnel Security": "PS",
    "Physical Protection": "PE",
    "Risk Assessment": "RA",
    "Security Assessment": "CA",
    "System and Communications Protection": "SC",
    "System and Information Integrity": "SI",
}

FAMILY_COLORS = {
    "AC": "#3b82f6", "AT": "#8b5cf6", "AU": "#ec4899", "CM": "#f59e0b",
    "IA": "#10b981", "IR": "#ef4444", "MA": "#6366f1", "MP": "#14b8a6",
    "PS": "#f97316", "PE": "#84cc16", "RA": "#06b6d4", "CA": "#a855f7",
    "SC": "#0ea5e9", "SI": "#e11d48",
}


@app.route("/")
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
    conn.close()
    return render_template("dashboard.html",
                           families=families, totals=totals,
                           abbr=FAMILY_ABBR, colors=FAMILY_COLORS,
                           domain_coverage=domain_coverage)


@app.route("/family/<path:family_name>")
def family_detail(family_name):
    conn = get_db()
    objectives = conn.execute("""
        SELECT * FROM objectives WHERE family = ? ORDER BY sort_as
    """, (family_name,)).fetchall()
    conn.close()

    # Group by requirement
    requirements = {}
    for obj in objectives:
        req_id = obj["requirement_id"]
        if req_id not in requirements:
            requirements[req_id] = {
                "id": req_id,
                "security_requirement": obj["security_requirement"],
                "examine": obj["examine"],
                "interview": obj["interview"],
                "test": obj["test"],
                "objectives": [],
            }
        requirements[req_id]["objectives"].append(dict(obj))

    abbr = FAMILY_ABBR.get(family_name, "")
    return render_template("family.html", family=family_name, abbr=abbr,
                           requirements=requirements,
                           color=FAMILY_COLORS.get(abbr, "#6366f1"))


@app.route("/api/toggle", methods=["POST"])
def toggle_objective():
    data = request.json
    obj_id = data.get("id")
    captured = data.get("captured", False)
    notes = data.get("artifact_notes", "")
    status = "Complete" if captured else "Not Started"
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d") if captured else None
    conn.execute("""
        UPDATE objectives SET captured = ?, artifact_notes = ?, captured_date = ?, status = ?
        WHERE id = ?
    """, (1 if captured else 0, notes, now, status, obj_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


VALID_STATUSES = ["Not Started", "In Progress", "Evidence Collected", "Reviewed", "Complete"]


@app.route("/api/status", methods=["POST"])
def update_status():
    data = request.json
    obj_id = data.get("id")
    status = data.get("status", "Not Started")
    if status not in VALID_STATUSES:
        return jsonify({"error": "Invalid status"}), 400
    conn = get_db()
    captured = 1 if status == "Complete" else 0
    now = datetime.now().strftime("%Y-%m-%d") if captured else None
    # Only set captured_date if transitioning to Complete
    if captured:
        existing = conn.execute("SELECT captured_date FROM objectives WHERE id = ?", (obj_id,)).fetchone()
        if existing and existing["captured_date"]:
            now = existing["captured_date"]  # Keep original date
    conn.execute("""
        UPDATE objectives SET status = ?, captured = ?, captured_date = COALESCE(?, captured_date)
        WHERE id = ?
    """, (status, captured, now, obj_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "status": status, "captured": captured})


@app.route("/api/notes", methods=["POST"])
def update_notes():
    data = request.json
    conn = get_db()
    conn.execute("UPDATE objectives SET artifact_notes = ? WHERE id = ?",
                 (data.get("notes", ""), data.get("id")))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/bulk", methods=["POST"])
def bulk_update():
    data = request.json
    req_id = data.get("requirement_id")
    captured = data.get("captured", True)
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d") if captured else None
    status = "Complete" if captured else "Not Started"
    conn.execute("""
        UPDATE objectives SET captured = ?, captured_date = ?, status = ?
        WHERE requirement_id = ?
    """, (1 if captured else 0, now, status, req_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/export")
def export_csv():
    conn = get_db()
    rows = conn.execute("SELECT * FROM objectives ORDER BY sort_as").fetchall()
    # Get all assignments with member names
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


### POA&M (Plan of Action & Milestones) ###

@app.route("/poam")
def poam_page():
    conn = get_db()
    # Get all incomplete objectives with optional POA&M data
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
    # Summary stats
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


@app.route("/api/poam", methods=["POST"])
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
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/poam/export")
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


@app.route("/api/search")
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


@app.route("/search")
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


@app.route("/member/<int:member_id>")
def member_detail(member_id):
    conn = get_db()
    member = conn.execute("SELECT * FROM team_members WHERE id = ?", (member_id,)).fetchone()
    if not member:
        conn.close()
        return "Member not found", 404
    assignments = conn.execute("""
        SELECT a.*, o.family, o.assessment_objective, o.captured, o.captured_date, o.artifact_notes
        FROM artifact_assignments a
        JOIN objectives o ON a.objective_id = o.id
        WHERE a.member_id = ?
        ORDER BY o.sort_as
    """, (member_id,)).fetchall()
    # Stats
    total = len(assignments)
    completed = sum(1 for a in assignments if a["captured"])
    overdue = sum(1 for a in assignments if a["due_date"] and a["due_date"] < datetime.now().strftime("%Y-%m-%d") and not a["captured"])
    # Group by family
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


### Config / Team Management ###

@app.route("/config")
@admin_required
def config_page():
    conn = get_db()
    members = conn.execute("SELECT * FROM team_members ORDER BY name").fetchall()
    # Get assignment counts per member
    counts = {}
    for m in members:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM artifact_assignments WHERE member_id = ?",
            (m["id"],)
        ).fetchone()
        counts[m["id"]] = row["c"]
    domains = conn.execute("SELECT * FROM domains ORDER BY name").fetchall()
    conn.close()
    return render_template("config.html", members=members, counts=counts, domains=domains)


@app.route("/api/team", methods=["GET"])
def list_team():
    conn = get_db()
    members = conn.execute("SELECT * FROM team_members ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(m) for m in members])


@app.route("/api/team", methods=["POST"])
@admin_required
def add_team_member():
    data = request.json
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    conn = get_db()
    conn.execute(
        "INSERT INTO team_members (name, role, email, created_at) VALUES (?, ?, ?, ?)",
        (name, data.get("role", ""), data.get("email", ""),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/team/<int:member_id>", methods=["DELETE"])
@admin_required
def delete_team_member(member_id):
    conn = get_db()
    conn.execute("DELETE FROM artifact_assignments WHERE member_id = ?", (member_id,))
    conn.execute("DELETE FROM team_members WHERE id = ?", (member_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/team/<int:member_id>", methods=["PATCH"])
@admin_required
def update_team_member(member_id):
    data = request.json
    conn = get_db()
    conn.execute(
        "UPDATE team_members SET name = ?, role = ?, email = ? WHERE id = ?",
        (data.get("name", ""), data.get("role", ""), data.get("email", ""), member_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


### Domains ###

@app.route("/api/domains", methods=["GET"])
def list_domains():
    conn = get_db()
    rows = conn.execute("SELECT * FROM domains ORDER BY name").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/domains", methods=["POST"])
@admin_required
def add_domain():
    data = request.json
    name = data.get("name", "").strip()
    color = data.get("color", "#6366f1").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    conn = get_db()
    try:
        conn.execute("INSERT INTO domains (name, color) VALUES (?, ?)", (name, color))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Domain already exists"}), 409
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/domains/<int:domain_id>", methods=["PATCH"])
@admin_required
def update_domain(domain_id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE domains SET name = ?, color = ? WHERE id = ?",
                 (data.get("name", "").strip(), data.get("color", "#6366f1").strip(), domain_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/domains/<int:domain_id>", methods=["DELETE"])
@admin_required
def delete_domain(domain_id):
    conn = get_db()
    conn.execute("UPDATE artifacts SET domain_id = NULL WHERE domain_id = ?", (domain_id,))
    conn.execute("DELETE FROM domains WHERE id = ?", (domain_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


### Assignments ###

@app.route("/api/assignments/<objective_id>")
def list_assignments(objective_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, t.name as member_name, t.role as member_role
        FROM artifact_assignments a
        JOIN team_members t ON a.member_id = t.id
        WHERE a.objective_id = ?
        ORDER BY a.assigned_at DESC
    """, (objective_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/assignments", methods=["POST"])
def add_assignment():
    data = request.json
    objective_id = data.get("objective_id")
    member_id = data.get("member_id")
    if not objective_id or not member_id:
        return jsonify({"error": "objective_id and member_id required"}), 400
    conn = get_db()
    # Prevent duplicate assignments
    existing = conn.execute(
        "SELECT id FROM artifact_assignments WHERE objective_id = ? AND member_id = ?",
        (objective_id, member_id)
    ).fetchone()
    if existing:
        conn.close()
        return jsonify({"error": "Already assigned"}), 409
    conn.execute("""
        INSERT INTO artifact_assignments (objective_id, member_id, status, due_date, assigned_at)
        VALUES (?, ?, ?, ?, ?)
    """, (objective_id, member_id, data.get("status", "assigned"),
          data.get("due_date"), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/assignments/<int:assignment_id>", methods=["DELETE"])
def delete_assignment(assignment_id):
    conn = get_db()
    conn.execute("DELETE FROM artifact_assignments WHERE id = ?", (assignment_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/assignments/<int:assignment_id>/due", methods=["PATCH"])
def update_assignment_due(assignment_id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE artifact_assignments SET due_date = ? WHERE id = ?",
                 (data.get("due_date") or None, assignment_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/assignments/<int:assignment_id>/status", methods=["PATCH"])
def update_assignment_status(assignment_id):
    data = request.json
    conn = get_db()
    conn.execute("UPDATE artifact_assignments SET status = ? WHERE id = ?",
                 (data.get("status", "assigned"), assignment_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/assignments/bulk", methods=["POST"])
def bulk_assign():
    data = request.json
    requirement_id = data.get("requirement_id")
    member_id = data.get("member_id")
    if not requirement_id or not member_id:
        return jsonify({"error": "requirement_id and member_id required"}), 400
    conn = get_db()
    objectives = conn.execute(
        "SELECT id FROM objectives WHERE requirement_id = ?", (requirement_id,)
    ).fetchall()
    added = 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for obj in objectives:
        existing = conn.execute(
            "SELECT id FROM artifact_assignments WHERE objective_id = ? AND member_id = ?",
            (obj["id"], member_id)
        ).fetchone()
        if not existing:
            conn.execute("""
                INSERT INTO artifact_assignments (objective_id, member_id, status, assigned_at)
                VALUES (?, ?, 'assigned', ?)
            """, (obj["id"], member_id, now))
            added += 1
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "added": added, "total": len(objectives)})


### Artifacts ###

@app.route("/api/artifacts/<objective_id>")
def list_artifacts(objective_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, d.name as domain_name, d.color as domain_color
        FROM artifacts a
        LEFT JOIN domains d ON a.domain_id = d.id
        WHERE a.objective_id = ? ORDER BY a.uploaded_at DESC
    """, (objective_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


def _extract_file_created(filepath, ext):
    """Extract creation/modification date from file metadata."""
    try:
        # Images (EXIF)
        if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
            from PIL import Image
            from PIL.ExifTags import Base as ExifBase
            img = Image.open(filepath)
            exif = img.getexif()
            if exif:
                # Try DateTimeOriginal, then DateTimeDigitized, then DateTime
                for tag in (ExifBase.DateTimeOriginal, ExifBase.DateTimeDigitized, ExifBase.DateTime):
                    val = exif.get(tag)
                    if val:
                        # EXIF format: "2026:03:05 10:30:00"
                        return val.replace(":", "-", 2)
            img.close()

        # PDFs
        elif ext == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(filepath)
            info = reader.metadata
            if info:
                for field in (info.creation_date, info.modification_date):
                    if field:
                        return field.strftime("%Y-%m-%d %H:%M:%S")

        # Word docs (.docx)
        elif ext == '.docx':
            from docx import Document
            doc = Document(filepath)
            props = doc.core_properties
            if props.created:
                return props.created.strftime("%Y-%m-%d %H:%M:%S")
            if props.modified:
                return props.modified.strftime("%Y-%m-%d %H:%M:%S")

        # Excel (.xlsx)
        elif ext == '.xlsx':
            from openpyxl import load_workbook
            wb = load_workbook(filepath, read_only=True)
            props = wb.properties
            if props.created:
                return props.created.strftime("%Y-%m-%d %H:%M:%S")
            if props.modified:
                return props.modified.strftime("%Y-%m-%d %H:%M:%S")
            wb.close()

        # PowerPoint (.pptx) - uses same OPC format as docx
        elif ext == '.pptx':
            import zipfile
            from xml.etree import ElementTree
            with zipfile.ZipFile(filepath) as z:
                if 'docProps/core.xml' in z.namelist():
                    tree = ElementTree.parse(z.open('docProps/core.xml'))
                    ns = {'dcterms': 'http://purl.org/dc/terms/'}
                    created = tree.find('.//dcterms:created', ns)
                    if created is not None and created.text:
                        return created.text[:19].replace("T", " ")

    except Exception:
        pass
    return None


def _generate_artifact_filename(conn, objective_id, domain_name, ext):
    """Generate auto-renamed filename: AC-3.01.01.a-Domain{ext}"""
    # Clean objective_id: 3.1.1[a] -> 3.01.01.a
    clean_id = objective_id.replace("[", ".").replace("]", "").replace(" ", "").replace("\t", "")
    # Get family abbreviation prefix from the objective
    obj_row = conn.execute("SELECT family FROM objectives WHERE id = ?", (objective_id,)).fetchone()
    abbr = FAMILY_ABBR.get(obj_row["family"], "") if obj_row else ""
    prefix = f"{abbr}-{clean_id}" if abbr else clean_id

    # Domain part
    domain_part = ""
    if domain_name:
        domain_part = "-" + domain_name.replace(" ", "-")

    return f"{prefix}{domain_part}{ext}"


@app.route("/api/upload", methods=["POST"])
def upload_artifact():
    objective_id = request.form.get("objective_id")
    if not objective_id:
        return jsonify({"error": "Missing objective_id"}), 400

    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file provided"}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"File type {ext} not allowed"}), 400

    domain_id = request.form.get("domain_id") or None
    if domain_id:
        domain_id = int(domain_id)

    # Create per-objective subdirectory
    safe_id = objective_id.replace("[", "").replace("]", "").replace(" ", "").replace("\t", "")
    obj_dir = os.path.join(UPLOAD_DIR, safe_id)
    os.makedirs(obj_dir, exist_ok=True)

    conn = get_db()

    # Look up domain name for filename
    domain_name = ""
    if domain_id:
        d = conn.execute("SELECT name FROM domains WHERE id = ?", (domain_id,)).fetchone()
        if d:
            domain_name = d["name"]

    # Auto-rename
    filename = _generate_artifact_filename(conn, objective_id, domain_name, ext)
    filepath = os.path.join(obj_dir, filename)

    # Avoid collision
    if os.path.exists(filepath):
        timestamp = datetime.now().strftime("%H%M%S")
        filename = _generate_artifact_filename(conn, objective_id, domain_name, f"_{timestamp}{ext}")
        filepath = os.path.join(obj_dir, filename)

    file.save(filepath)
    file_size = os.path.getsize(filepath)

    # Extract creation date from file metadata
    file_created = _extract_file_created(filepath, ext)

    conn.execute("""
        INSERT INTO artifacts (objective_id, filename, original_name, file_size, mime_type, uploaded_at, domain_id, file_created)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (objective_id, f"{safe_id}/{filename}", file.filename, file_size,
          file.content_type, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), domain_id, file_created))
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "filename": filename})


@app.route("/api/artifacts/delete/<int:artifact_id>", methods=["POST"])
def delete_artifact(artifact_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    # Delete file
    filepath = os.path.join(UPLOAD_DIR, row["filename"])
    if os.path.exists(filepath):
        os.remove(filepath)

    conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/artifacts/<int:artifact_id>/domain", methods=["PATCH"])
def update_artifact_domain(artifact_id):
    data = request.json
    domain_id = data.get("domain_id") or None
    if domain_id:
        domain_id = int(domain_id)

    conn = get_db()
    row = conn.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    old_filepath = os.path.join(UPLOAD_DIR, row["filename"])
    ext = os.path.splitext(row["filename"])[1]

    # Look up domain name
    domain_name = ""
    if domain_id:
        d = conn.execute("SELECT name FROM domains WHERE id = ?", (domain_id,)).fetchone()
        if d:
            domain_name = d["name"]

    # Generate new filename
    new_basename = _generate_artifact_filename(conn, row["objective_id"], domain_name, ext)
    safe_id = row["objective_id"].replace("[", "").replace("]", "").replace(" ", "").replace("\t", "")
    new_filename = f"{safe_id}/{new_basename}"
    new_filepath = os.path.join(UPLOAD_DIR, new_filename)

    # Rename physical file
    if os.path.exists(old_filepath):
        os.makedirs(os.path.dirname(new_filepath), exist_ok=True)
        os.rename(old_filepath, new_filepath)

    # Update DB
    conn.execute("UPDATE artifacts SET domain_id = ?, filename = ? WHERE id = ?",
                 (domain_id, new_filename, artifact_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "filename": new_filename})


@app.route("/api/artifacts/<int:artifact_id>/obtained", methods=["PATCH"])
def update_artifact_obtained(artifact_id):
    data = request.json
    method = data.get("obtained_method", "")
    conn = get_db()
    conn.execute("UPDATE artifacts SET obtained_method = ? WHERE id = ?", (method, artifact_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    from flask import send_from_directory
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/api/hash-artifacts", methods=["POST"])
def hash_artifacts():
    """Generate CMMC-compliant SHA-256 hashes for all uploaded artifacts."""
    import hashlib
    results = []
    for root, dirs, files in os.walk(UPLOAD_DIR):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            sha256 = hashlib.sha256()
            with open(fpath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            rel_path = os.path.relpath(fpath, UPLOAD_DIR)
            results.append({
                "algorithm": "SHA256",
                "hash": sha256.hexdigest().upper(),
                "path": rel_path
            })

    # Write CMMCAssessmentArtifacts.log
    log_lines = [f"{'Algorithm':<12} {'Hash':<64} Path"]
    log_lines.append(f"{'-'*12} {'-'*64} {'-'*4}")
    for r in results:
        log_lines.append(f"{r['algorithm']:<12} {r['hash']:<64} {r['path']}")
    log_content = "\n".join(log_lines)

    artifacts_log = os.path.join(UPLOAD_DIR, "CMMCAssessmentArtifacts.log")
    with open(artifacts_log, "w", encoding="ascii") as f:
        f.write(log_content)

    # Hash the log file itself
    sha256 = hashlib.sha256()
    with open(artifacts_log, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    log_hash = sha256.hexdigest().upper()

    hash_log = os.path.join(UPLOAD_DIR, "CMMCAssessmentLogHash.log")
    with open(hash_log, "w", encoding="ascii") as f:
        f.write(f"{'Algorithm':<12} {'Hash':<64} Path\n")
        f.write(f"{'-'*12} {'-'*64} {'-'*4}\n")
        f.write(f"{'SHA256':<12} {log_hash:<64} CMMCAssessmentArtifacts.log\n")

    return jsonify({
        "ok": True,
        "artifacts_hashed": len(results),
        "log_hash": log_hash,
        "artifacts_log": "uploads/CMMCAssessmentArtifacts.log",
        "hash_log": "uploads/CMMCAssessmentLogHash.log"
    })


### Authentication ###

@app.route("/setup", methods=["GET", "POST"])
def setup():
    conn = get_db()
    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    if user_count > 0:
        return redirect(url_for('login'))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        errors = []
        if not username:
            errors.append("Username is required")
        if password != confirm:
            errors.append("Passwords do not match")
        errors.extend(validate_password(password))
        if errors:
            return render_template("setup.html", errors=errors, username=username)
        conn = get_db()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, generate_password_hash(password), 'admin', now)
        )
        # Auto-create team member for assignment dropdown
        conn.execute(
            "INSERT INTO team_members (name, role, email, created_at) VALUES (?, ?, ?, ?)",
            (username, 'admin', '', now)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('login'))
    return render_template("setup.html", errors=[], username="")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        return render_template("login.html", error="Invalid username or password")
    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route("/admin/users")
@admin_required
def admin_users():
    conn = get_db()
    users = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY created_at").fetchall()
    conn.close()
    return render_template("admin_users.html", users=users)


@app.route("/api/admin/users", methods=["POST"])
@admin_required
def admin_create_user():
    data = request.json
    username = data.get("username", "").strip()
    password = data.get("password", "")
    role = data.get("role", "user")
    if role not in ('admin', 'user'):
        return jsonify({"error": "Invalid role"}), 400
    if not username:
        return jsonify({"error": "Username is required"}), 400
    errors = validate_password(password)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400
    conn = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, generate_password_hash(password), role, now)
        )
        # Auto-create team member for assignment dropdown
        conn.execute(
            "INSERT INTO team_members (name, role, email, created_at) VALUES (?, ?, ?, ?)",
            (username, role, '', now)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Username already exists"}), 409
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@admin_required
def admin_delete_user(user_id):
    if user_id == session.get('user_id'):
        return jsonify({"error": "Cannot delete yourself"}), 400
    conn = get_db()
    user = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    # Also remove from team members
    if user:
        conn.execute("DELETE FROM artifact_assignments WHERE member_id IN (SELECT id FROM team_members WHERE name = ?)", (user['username'],))
        conn.execute("DELETE FROM team_members WHERE name = ?", (user['username'],))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/admin/users/<int:user_id>/reset", methods=["POST"])
@admin_required
def admin_reset_password(user_id):
    data = request.json
    password = data.get("password", "")
    errors = validate_password(password)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400
    conn = get_db()
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?",
                 (generate_password_hash(password), user_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


if __name__ == "__main__":
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

    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=8888, debug=debug)
