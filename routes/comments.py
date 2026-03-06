"""Comments blueprint: CRUD for objective comments/activity log and comment counts."""

from datetime import datetime

from flask import Blueprint, request, jsonify, session

from models import get_db
from utils import log_audit, get_org_id

comments_bp = Blueprint('comments', __name__)


@comments_bp.route("/api/comments/<objective_id>")
def list_comments(objective_id):
    org_id = get_org_id()
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM objective_comments WHERE objective_id = ? AND org_id = ?
        ORDER BY created_at DESC
    """, (objective_id, org_id)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@comments_bp.route("/api/comments", methods=["POST"])
def add_comment():
    data = request.json
    obj_id = data.get("objective_id")
    comment = data.get("comment", "").strip()
    if not obj_id or not comment:
        return jsonify({"error": "objective_id and comment required"}), 400
    username = session.get("username", "system")
    user_id = session.get("user_id")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    org_id = get_org_id()
    conn = get_db()
    cur = conn.execute("""
        INSERT INTO objective_comments (objective_id, user_id, username, comment, created_at, org_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (obj_id, user_id, username, comment, now, org_id))
    comment_id = cur.lastrowid
    log_audit('comment_added', 'objective', obj_id, comment[:100], conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "id": comment_id, "username": username, "created_at": now})


@comments_bp.route("/api/comments/<int:comment_id>", methods=["DELETE"])
def delete_comment(comment_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM objective_comments WHERE id = ?", (comment_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    if session.get("role") != "admin" and session.get("user_id") != row["user_id"]:
        conn.close()
        return jsonify({"error": "Not authorized"}), 403
    conn.execute("DELETE FROM objective_comments WHERE id = ?", (comment_id,))
    log_audit('comment_deleted', 'objective', row['objective_id'], f'Comment #{comment_id}', conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@comments_bp.route("/api/comments/count")
def comment_counts():
    """Get comment counts for multiple objectives (used by family page)."""
    obj_ids = request.args.get("ids", "")
    if not obj_ids:
        return jsonify({})
    ids = [x.strip() for x in obj_ids.split(",") if x.strip()]
    org_id = get_org_id()
    conn = get_db()
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(f"""
        SELECT objective_id, COUNT(*) as cnt
        FROM objective_comments
        WHERE objective_id IN ({placeholders}) AND org_id = ?
        GROUP BY objective_id
    """, ids + [org_id]).fetchall()
    conn.close()
    return jsonify({r["objective_id"]: r["cnt"] for r in rows})
