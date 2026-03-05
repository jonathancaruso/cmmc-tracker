# Security Hardening — CMMC Artifact Tracker

This document describes the security measures implemented in the CMMC Artifact Tracker.

## Authentication & Session Management

- **Password hashing**: Werkzeug's `generate_password_hash` (scrypt by default) — no MD5/SHA
- **Password policy**: Minimum 16 characters, requires uppercase, lowercase, digit, and special character
- **Session fixation prevention**: `session.clear()` on login before setting new session data
- **Secure cookies**: `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE=Lax`, `SESSION_COOKIE_SECURE` enabled when `FLASK_ENV=production`
- **Login rate limiting**: 5 attempts per IP per 5-minute window; returns "Too many login attempts" on excess
- **Route protection**: All routes require authentication via `@app.before_request` check; admin-only routes use `@admin_required` decorator

## CSRF Protection

- **Session-based CSRF tokens**: Generated per session via `secrets.token_hex(32)`
- **Form protection**: All HTML forms include `<input type="hidden" name="csrf_token">` field
- **API protection**: All state-changing fetch requests include `X-CSRF-Token` header
- **Multipart uploads**: CSRF token sent as form field in FormData uploads
- **Validation**: `@app.before_request` hook validates tokens on all POST/PUT/PATCH/DELETE requests

## XSS Prevention

- **Jinja2 auto-escaping**: Enabled by default for all `{{ }}` expressions in HTML context
- **JavaScript context escaping**: All Jinja2 variables in inline JS handlers use `|tojson` filter for proper JS escaping
- **innerHTML sanitization**: Global `escapeHtml()` function applied to all user-controlled data before insertion via `innerHTML` or template literals
- **Integer coercion**: All numeric IDs use `parseInt()` in JS template literals to prevent injection
- **JSON.stringify**: String values in JS onclick handlers use `JSON.stringify()` for safe quoting

## Content Security Policy

```
default-src 'self';
script-src 'self' 'unsafe-inline';
style-src 'self' 'unsafe-inline';
img-src 'self' data: blob:;
font-src 'self';
form-action 'self';
frame-ancestors 'none';
```

## Security Headers

All responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy` (see above)
- `Strict-Transport-Security` (production only, when `FLASK_ENV=production`)

## File Upload Security

- **Extension whitelist**: Only `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.txt`, `.csv`, `.pptx`, `.zip`, `.md` are allowed
- **File size limit**: `MAX_CONTENT_LENGTH = 100 MB` — returns 413 on excess
- **Path traversal protection**: `serve_upload` validates resolved real path stays within `UPLOAD_DIR`
- **No execution**: Uploaded files are served via `send_from_directory` with explicit MIME types; no server-side execution

## SQL Injection Prevention

- All database queries use parameterized placeholders (`?`) — no string interpolation of user input into SQL
- Migration queries use hardcoded column names only (not user input)
- Audit log filtering constructs WHERE clauses from hardcoded condition strings with `?` placeholders

## Secrets Management

- `FLASK_SECRET` should be set via environment variable for production
- If not set, a random key is generated per process start (logs a warning to stderr)
- Debug mode defaults to **off** (`FLASK_DEBUG=0`); must be explicitly enabled

## Error Handling

- Custom error handlers for 404, 413, and 500 — no stack traces exposed to users
- API endpoints return JSON error responses; HTML pages return minimal text
- Debug mode disabled by default in production

## Authorization

- Admin routes (`/config`, `/admin/users`, `/audit`) protected by `@admin_required`
- Self-protection: admins cannot remove their own admin role or delete themselves
- Role validation: only `admin` and `user` roles accepted

## Deployment Recommendations

1. Set `FLASK_SECRET` to a strong random value: `python3 -c "import secrets; print(secrets.token_hex(32))"`
2. Set `FLASK_ENV=production` to enable secure cookies and HSTS
3. Run behind a reverse proxy (nginx/caddy) with TLS termination
4. Restrict `UPLOAD_PATH` directory permissions
5. Back up `cmmc.db` regularly — it contains all compliance data
6. Monitor the audit log for suspicious activity

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it responsibly via the project's issue tracker with the `security` label.
