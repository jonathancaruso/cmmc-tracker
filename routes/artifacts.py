"""Artifacts blueprint: uploads, delete, domain tagging, obtained method, linking, library, hashing."""

import hashlib
import os
import sqlite3
from datetime import datetime

from flask import Blueprint, render_template, request, jsonify, abort, send_from_directory

from models import get_db, ALLOWED_EXTENSIONS, UPLOAD_DIR
from utils import log_audit, _extract_file_created, _generate_artifact_filename

artifacts_bp = Blueprint('artifacts', __name__)


@artifacts_bp.route("/api/artifacts/<objective_id>")
def list_artifacts(objective_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, d.name as domain_name, d.color as domain_color,
               CASE WHEN a.objective_id != ? THEN 1 ELSE 0 END as is_linked
        FROM artifact_objectives ao
        JOIN artifacts a ON ao.artifact_id = a.id
        LEFT JOIN domains d ON a.domain_id = d.id
        WHERE ao.objective_id = ? ORDER BY a.uploaded_at DESC
    """, (objective_id, objective_id)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        linked = conn.execute("""
            SELECT ao.objective_id, o.family FROM artifact_objectives ao
            JOIN objectives o ON ao.objective_id = o.id
            WHERE ao.artifact_id = ?
        """, (r['id'],)).fetchall()
        d['linked_objectives'] = [{'id': l['objective_id'], 'family': l['family']} for l in linked]
        result.append(d)
    conn.close()
    return jsonify(result)


@artifacts_bp.route("/api/upload", methods=["POST"])
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

    safe_id = objective_id.replace("[", "").replace("]", "").replace(" ", "").replace("\t", "")
    obj_dir = os.path.join(UPLOAD_DIR, safe_id)
    os.makedirs(obj_dir, exist_ok=True)

    conn = get_db()

    domain_name = ""
    if domain_id:
        d = conn.execute("SELECT name FROM domains WHERE id = ?", (domain_id,)).fetchone()
        if d:
            domain_name = d["name"]

    filename = _generate_artifact_filename(conn, objective_id, domain_name, ext)
    filepath = os.path.join(obj_dir, filename)

    if os.path.exists(filepath):
        timestamp = datetime.now().strftime("%H%M%S")
        filename = _generate_artifact_filename(conn, objective_id, domain_name, f"_{timestamp}{ext}")
        filepath = os.path.join(obj_dir, filename)

    file.save(filepath)
    file_size = os.path.getsize(filepath)

    file_created = _extract_file_created(filepath, ext)

    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor = conn.execute("""
        INSERT INTO artifacts (objective_id, filename, original_name, file_size, mime_type, uploaded_at, domain_id, file_created)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (objective_id, f"{safe_id}/{filename}", file.filename, file_size,
          file.content_type, now_ts, domain_id, file_created))
    conn.execute("INSERT OR IGNORE INTO artifact_objectives (artifact_id, objective_id) VALUES (?, ?)",
                  (cursor.lastrowid, objective_id))
    log_audit('uploaded', 'artifact', objective_id, f"Uploaded {filename}", conn=conn)
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "filename": filename})


@artifacts_bp.route("/api/artifacts/delete/<int:artifact_id>", methods=["POST"])
def delete_artifact(artifact_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404

    filepath = os.path.join(UPLOAD_DIR, row["filename"])
    if os.path.exists(filepath):
        os.remove(filepath)

    conn.execute("DELETE FROM artifact_objectives WHERE artifact_id = ?", (artifact_id,))
    conn.execute("DELETE FROM artifacts WHERE id = ?", (artifact_id,))
    log_audit('deleted', 'artifact', artifact_id,
              f"Deleted {row['original_name']} from {row['objective_id']}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@artifacts_bp.route("/api/artifacts/<int:artifact_id>/domain", methods=["PATCH"])
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

    domain_name = ""
    if domain_id:
        d = conn.execute("SELECT name FROM domains WHERE id = ?", (domain_id,)).fetchone()
        if d:
            domain_name = d["name"]

    new_basename = _generate_artifact_filename(conn, row["objective_id"], domain_name, ext)
    safe_id = row["objective_id"].replace("[", "").replace("]", "").replace(" ", "").replace("\t", "")
    new_filename = f"{safe_id}/{new_basename}"
    new_filepath = os.path.join(UPLOAD_DIR, new_filename)

    if os.path.exists(old_filepath):
        os.makedirs(os.path.dirname(new_filepath), exist_ok=True)
        os.rename(old_filepath, new_filepath)

    conn.execute("UPDATE artifacts SET domain_id = ?, filename = ? WHERE id = ?",
                 (domain_id, new_filename, artifact_id))
    log_audit('domain_changed', 'artifact', artifact_id,
              f"Domain set to {domain_name or 'none'} for {row['objective_id']}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "filename": new_filename})


@artifacts_bp.route("/api/artifacts/<int:artifact_id>/obtained", methods=["PATCH"])
def update_artifact_obtained(artifact_id):
    data = request.json
    method = data.get("obtained_method", "")
    conn = get_db()
    conn.execute("UPDATE artifacts SET obtained_method = ? WHERE id = ?", (method, artifact_id))
    log_audit('obtained_updated', 'artifact', artifact_id,
              f"Obtained method set to '{method}'" if method else "Obtained method cleared", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@artifacts_bp.route("/api/artifacts/<int:artifact_id>/link", methods=["POST"])
def link_artifact(artifact_id):
    data = request.json
    objective_id = data.get("objective_id", "").strip()
    if not objective_id:
        return jsonify({"error": "Missing objective_id"}), 400
    conn = get_db()
    artifact = conn.execute("SELECT id FROM artifacts WHERE id = ?", (artifact_id,)).fetchone()
    if not artifact:
        conn.close()
        return jsonify({"error": "Artifact not found"}), 404
    objective = conn.execute("SELECT id FROM objectives WHERE id = ?", (objective_id,)).fetchone()
    if not objective:
        conn.close()
        return jsonify({"error": "Objective not found"}), 404
    try:
        conn.execute("INSERT INTO artifact_objectives (artifact_id, objective_id) VALUES (?, ?)",
                      (artifact_id, objective_id))
        log_audit('linked', 'artifact', artifact_id,
                  f"Linked artifact #{artifact_id} to {objective_id}", conn=conn)
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Already linked"}), 409
    conn.close()
    return jsonify({"ok": True})


@artifacts_bp.route("/api/artifacts/<int:artifact_id>/link/<path:objective_id>", methods=["DELETE"])
def unlink_artifact(artifact_id, objective_id):
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM artifact_objectives WHERE artifact_id = ?",
                          (artifact_id,)).fetchone()[0]
    if count <= 1:
        conn.close()
        return jsonify({"error": "Cannot unlink the last objective. Delete the artifact instead."}), 400
    conn.execute("DELETE FROM artifact_objectives WHERE artifact_id = ? AND objective_id = ?",
                  (artifact_id, objective_id))
    log_audit('unlinked', 'artifact', artifact_id,
              f"Unlinked artifact #{artifact_id} from {objective_id}", conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@artifacts_bp.route("/api/artifacts/library")
def artifacts_library_api():
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, d.name as domain_name, d.color as domain_color
        FROM artifacts a
        LEFT JOIN domains d ON a.domain_id = d.id
        ORDER BY a.uploaded_at DESC
    """).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        linked = conn.execute("""
            SELECT ao.objective_id, o.family FROM artifact_objectives ao
            JOIN objectives o ON ao.objective_id = o.id
            WHERE ao.artifact_id = ?
        """, (r['id'],)).fetchall()
        d['linked_objectives'] = [{'id': l['objective_id'], 'family': l['family']} for l in linked]
        result.append(d)
    conn.close()
    return jsonify(result)


@artifacts_bp.route("/artifacts")
def artifacts_library_page():
    return render_template("artifacts.html")


@artifacts_bp.route("/uploads/<path:filename>")
def serve_upload(filename):
    real_upload = os.path.realpath(UPLOAD_DIR)
    real_file = os.path.realpath(os.path.join(UPLOAD_DIR, filename))
    if not real_file.startswith(real_upload + os.sep) and real_file != real_upload:
        abort(404)
    return send_from_directory(UPLOAD_DIR, filename)


@artifacts_bp.route("/api/hash-artifacts", methods=["POST"])
def hash_artifacts():
    """Generate CMMC-compliant SHA-256 hashes for all uploaded artifacts."""
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

    log_lines = [f"{'Algorithm':<12} {'Hash':<64} Path"]
    log_lines.append(f"{'-'*12} {'-'*64} {'-'*4}")
    for r in results:
        log_lines.append(f"{r['algorithm']:<12} {r['hash']:<64} {r['path']}")
    log_content = "\n".join(log_lines)

    artifacts_log = os.path.join(UPLOAD_DIR, "CMMCAssessmentArtifacts.log")
    with open(artifacts_log, "w", encoding="ascii") as f:
        f.write(log_content)

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

    log_audit('hash_generated', 'artifact', None,
              f"Generated SHA-256 hashes for {len(results)} artifacts")

    return jsonify({
        "ok": True,
        "artifacts_hashed": len(results),
        "log_hash": log_hash,
        "artifacts_log": "uploads/CMMCAssessmentArtifacts.log",
        "hash_log": "uploads/CMMCAssessmentLogHash.log"
    })
