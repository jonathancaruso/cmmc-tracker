"""SSP Mapping blueprint: map requirements to System Security Plan sections."""

from flask import Blueprint, render_template, request, jsonify

from models import get_db, FAMILY_ABBR, FAMILY_COLORS
from utils import log_audit, get_org_id

ssp_bp = Blueprint('ssp', __name__)


@ssp_bp.route("/ssp")
def ssp_page():
    org_id = get_org_id()
    conn = get_db()
    rows = conn.execute("""
        SELECT DISTINCT o.requirement_id, o.family, o.security_requirement,
               s.id as ssp_id, s.ssp_section, s.ssp_description
        FROM objectives o
        LEFT JOIN ssp_mappings s ON o.requirement_id = s.requirement_id AND s.org_id = ?
        GROUP BY o.requirement_id
        ORDER BY o.sort_as
    """, (org_id,)).fetchall()
    conn.close()

    families = {}
    for r in rows:
        fam = r["family"]
        if fam not in families:
            families[fam] = {"abbr": FAMILY_ABBR.get(fam, ""), "color": FAMILY_COLORS.get(FAMILY_ABBR.get(fam, ""), "#6366f1"), "requirements": []}
        families[fam]["requirements"].append(dict(r))

    return render_template("ssp.html", families=families, abbr=FAMILY_ABBR, colors=FAMILY_COLORS)


@ssp_bp.route("/api/ssp/<path:requirement_id>", methods=["PUT"])
def update_ssp(requirement_id):
    data = request.json
    ssp_section = (data.get("ssp_section") or "").strip()
    ssp_description = (data.get("ssp_description") or "").strip()

    conn = get_db()
    # Verify requirement exists
    obj = conn.execute("SELECT id FROM objectives WHERE requirement_id = ? LIMIT 1",
                       (requirement_id,)).fetchone()
    if not obj:
        conn.close()
        return jsonify({"error": "Requirement not found"}), 404

    org_id = get_org_id()
    existing = conn.execute("SELECT id FROM ssp_mappings WHERE requirement_id = ? AND org_id = ?",
                            (requirement_id, org_id)).fetchone()
    if existing:
        conn.execute("""
            UPDATE ssp_mappings SET ssp_section = ?, ssp_description = ?
            WHERE requirement_id = ? AND org_id = ?
        """, (ssp_section, ssp_description, requirement_id, org_id))
    else:
        conn.execute("""
            INSERT INTO ssp_mappings (requirement_id, ssp_section, ssp_description, org_id)
            VALUES (?, ?, ?, ?)
        """, (requirement_id, ssp_section, ssp_description, org_id))

    log_audit('ssp_updated', 'ssp', requirement_id,
              f"SSP section set to '{ssp_section}'" if ssp_section else "SSP section cleared",
              conn=conn)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@ssp_bp.route("/api/ssp")
def list_ssp():
    """Return all SSP mappings as JSON (used by family detail pages)."""
    org_id = get_org_id()
    conn = get_db()
    rows = conn.execute("SELECT * FROM ssp_mappings WHERE org_id = ? ORDER BY requirement_id", (org_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
