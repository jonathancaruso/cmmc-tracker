"""Notifications blueprint: overdue assignment alerts and optional email."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, session
import os

from models import get_db, FAMILY_ABBR, FAMILY_COLORS
from utils import admin_required, log_audit

notifications_bp = Blueprint('notifications', __name__)


def get_overdue_assignments(conn, days_ahead=0):
    """Get assignments that are overdue or due within days_ahead days."""
    cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")

    rows = conn.execute("""
        SELECT a.id as assignment_id, a.objective_id, a.due_date, a.status as assign_status,
               o.family, o.assessment_objective, o.status as obj_status, o.captured,
               t.id as member_id, t.name as member_name, t.email as member_email
        FROM artifact_assignments a
        JOIN objectives o ON a.objective_id = o.id
        JOIN team_members t ON a.member_id = t.id
        WHERE a.due_date IS NOT NULL
          AND a.due_date <= ?
          AND o.captured = 0
        ORDER BY a.due_date ASC
    """, (cutoff,)).fetchall()

    overdue = []
    upcoming = []
    for r in rows:
        item = dict(r)
        item['is_overdue'] = r['due_date'] < today
        item['days_until'] = (datetime.strptime(r['due_date'], '%Y-%m-%d') - datetime.now()).days
        if item['is_overdue']:
            overdue.append(item)
        else:
            upcoming.append(item)

    return overdue, upcoming


@notifications_bp.route("/notifications")
def notifications_page():
    conn = get_db()
    overdue, upcoming = get_overdue_assignments(conn, days_ahead=7)

    # Group by member
    by_member = {}
    for item in overdue + upcoming:
        mid = item['member_id']
        if mid not in by_member:
            by_member[mid] = {'name': item['member_name'], 'email': item['member_email'],
                              'overdue': [], 'upcoming': []}
        if item['is_overdue']:
            by_member[mid]['overdue'].append(item)
        else:
            by_member[mid]['upcoming'].append(item)

    # SMTP config status
    smtp_configured = bool(os.environ.get('SMTP_HOST'))

    conn.close()
    return render_template("notifications.html",
                           overdue=overdue, upcoming=upcoming,
                           by_member=by_member,
                           smtp_configured=smtp_configured,
                           abbr=FAMILY_ABBR, colors=FAMILY_COLORS)


@notifications_bp.route("/api/notifications/summary")
def notification_summary():
    """Quick count for nav badge."""
    conn = get_db()
    overdue, upcoming = get_overdue_assignments(conn, days_ahead=3)
    conn.close()
    return jsonify({
        "overdue_count": len(overdue),
        "upcoming_count": len(upcoming),
        "total": len(overdue) + len(upcoming)
    })


@notifications_bp.route("/api/notifications/send-email", methods=["POST"])
@admin_required
def send_overdue_emails():
    """Send email notifications for overdue assignments. Requires SMTP env vars."""
    smtp_host = os.environ.get('SMTP_HOST')
    smtp_port = int(os.environ.get('SMTP_PORT', '587'))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    smtp_from = os.environ.get('SMTP_FROM', smtp_user)

    if not smtp_host:
        return jsonify({"error": "SMTP not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS env vars."}), 400

    conn = get_db()
    overdue, upcoming = get_overdue_assignments(conn, days_ahead=3)

    # Group by member email
    by_email = {}
    for item in overdue + upcoming:
        email = item.get('member_email', '').strip()
        if not email:
            continue
        if email not in by_email:
            by_email[email] = {'name': item['member_name'], 'items': []}
        by_email[email]['items'].append(item)

    sent = 0
    errors = []
    for email, data in by_email.items():
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"CMMC Tracker: {len(data['items'])} assignments need attention"
            msg['From'] = smtp_from
            msg['To'] = email

            lines = [f"Hi {data['name']},\n",
                     "The following CMMC assessment assignments need your attention:\n"]

            overdue_items = [i for i in data['items'] if i['is_overdue']]
            upcoming_items = [i for i in data['items'] if not i['is_overdue']]

            if overdue_items:
                lines.append(f"\n--- OVERDUE ({len(overdue_items)}) ---")
                for item in overdue_items:
                    lines.append(f"  [{item['objective_id']}] {item['assessment_objective'][:80]}")
                    lines.append(f"    Due: {item['due_date']} ({abs(item['days_until'])} days overdue)")

            if upcoming_items:
                lines.append(f"\n--- DUE SOON ({len(upcoming_items)}) ---")
                for item in upcoming_items:
                    lines.append(f"  [{item['objective_id']}] {item['assessment_objective'][:80]}")
                    lines.append(f"    Due: {item['due_date']} ({item['days_until']} days)")

            lines.append("\n\nPlease log in to the CMMC Artifact Tracker to update your progress.")
            body = "\n".join(lines)
            msg.attach(MIMEText(body, 'plain'))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                if smtp_user:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            sent += 1
        except Exception as e:
            errors.append(f"{email}: {str(e)}")

    log_audit('notifications_sent', 'system', None,
              f"Sent {sent} emails, {len(errors)} errors", conn=conn)
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "sent": sent, "errors": errors,
                    "skipped_no_email": sum(1 for i in overdue + upcoming if not i.get('member_email', '').strip())})
