"""Backup blueprint: ZIP export/import of cmmc.db + uploads/ folder."""

import io
import os
import shutil
import zipfile
from datetime import datetime

from flask import Blueprint, request, jsonify, send_file

from models import get_db, DB_PATH, UPLOAD_DIR
from utils import admin_required, log_audit

backup_bp = Blueprint('backup', __name__)


@backup_bp.route("/api/backup/export")
@admin_required
def export_backup():
    """Download a ZIP containing cmmc.db and the uploads/ folder."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add database
        if os.path.exists(DB_PATH):
            zf.write(DB_PATH, "cmmc.db")

        # Add uploads directory
        if os.path.isdir(UPLOAD_DIR):
            for root, _dirs, files in os.walk(UPLOAD_DIR):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    arcname = os.path.join("uploads", os.path.relpath(fpath, UPLOAD_DIR))
                    zf.write(fpath, arcname)

    buf.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_audit('backup_export', 'system', None, 'Exported full backup ZIP')
    return send_file(buf, mimetype='application/zip', as_attachment=True,
                     download_name=f"cmmc-backup-{timestamp}.zip")


@backup_bp.route("/api/backup/import", methods=["POST"])
@admin_required
def import_backup():
    """Accept a ZIP upload and restore cmmc.db + uploads/."""
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file provided"}), 400

    if not file.filename.lower().endswith('.zip'):
        return jsonify({"error": "File must be a .zip archive"}), 400

    try:
        zf = zipfile.ZipFile(file.stream)
    except zipfile.BadZipFile:
        return jsonify({"error": "Invalid ZIP file"}), 400

    names = zf.namelist()
    if "cmmc.db" not in names:
        zf.close()
        return jsonify({"error": "ZIP must contain cmmc.db at the root level"}), 400

    # Validate no path traversal
    for name in names:
        if name.startswith('/') or '..' in name:
            zf.close()
            return jsonify({"error": f"Invalid path in ZIP: {name}"}), 400

    # Restore database
    db_data = zf.read("cmmc.db")
    with open(DB_PATH, 'wb') as f:
        f.write(db_data)

    # Restore uploads
    upload_entries = [n for n in names if n.startswith("uploads/") and not n.endswith('/')]
    if upload_entries:
        # Clear existing uploads
        if os.path.isdir(UPLOAD_DIR):
            shutil.rmtree(UPLOAD_DIR)
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        for entry in upload_entries:
            rel = entry[len("uploads/"):]
            dest = os.path.join(UPLOAD_DIR, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, 'wb') as f:
                f.write(zf.read(entry))

    zf.close()
    log_audit('backup_import', 'system', None,
              f"Imported backup ZIP ({len(upload_entries)} files restored)")
    return jsonify({"ok": True, "files_restored": len(upload_entries)})
