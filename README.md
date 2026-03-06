# CMMC Artifact Tracker

A self-hosted, open-source compliance tracking tool for **CMMC Level 2** (NIST 800-171 Rev 2) assessments. Track all 14 control families, 110 security requirements, and 320 assessment objectives with full artifact management, team assignments, and assessment reporting.

Built for security teams, IT managers, and compliance officers preparing for CMMC certification.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)

---

## Screenshots

### Dashboard
![Dashboard showing family progress bars, completion stats, and charts](screenshots/dashboard.png)
*Track progress across all 14 NIST 800-171 control families with visual charts and status breakdowns.*

### Family Detail
![Family detail page with collapsible requirements and artifact uploads](screenshots/family-detail.png)
*Drill into any family to manage objectives, upload evidence, assign team members, and track status.*

### Evidence Library
![Evidence library showing all artifacts with linking capability](screenshots/evidence-library.png)
*Central evidence library lets you link one artifact to multiple objectives.*

### POA&M Generator
![POA&M page with risk levels and remediation plans](screenshots/poam.png)
*Auto-generated Plan of Action & Milestones with inline editing for risk, remediation, and milestones.*

### Assessment Report
![Printable assessment report](screenshots/report.png)
*Generate print-ready assessment reports covering all objectives, artifacts, and POA&M items.*

---

## Why This Exists

CMMC Level 2 certification requires organizations to demonstrate compliance with 320 assessment objectives across 14 control families. Most teams track this in spreadsheets, which quickly becomes unmanageable. Commercial GRC tools cost $15,000-50,000+/year and are overkill for small-to-mid defense contractors.

This tool gives you everything you need to manage your CMMC assessment for free.

---

## Features

### Core Tracking
- **Interactive Dashboard** -- per-family progress bars, status breakdown, artifact coverage stats
- **Family Detail Pages** -- collapsible requirements with checkable objectives
- **5-Stage Status Workflow** -- Not Started, In Progress, Evidence Collected, Reviewed, Complete
- **Global Search** -- find any objective by ID, text, family, or requirement (press `/` to focus)

### Artifact Management
- **File Uploads** -- attach screenshots, PDFs, docs, spreadsheets to any objective
- **Auto-Rename** -- files automatically renamed to CMMC format (e.g. `AC-3.01.01.a-IT.pdf`)
- **Domain/Asset Tagging** -- tag artifacts by source system or AD domain
- **File Metadata Extraction** -- pulls creation dates from EXIF, PDF, docx, xlsx, pptx
- **"How Was This Obtained?"** -- document collection method per artifact
- **SHA-256 Hashing** -- generate CMMC-compliant artifact hashes (eMASS format)

### Evidence Mapping
- **Many-to-Many Linking** -- link one artifact to multiple objectives (e.g. one SSP covers dozens of controls)
- **Evidence Library** -- searchable view of ALL artifacts across all objectives
- **Link/Unlink** from any objective or from the library
- **Shared artifact tracking** on dashboard

### Team Collaboration
- **User Authentication** -- first-run setup flow, role-based access (admin/user)
- **Team Assignments** -- assign objectives to team members with due dates
- **Bulk Assignment** -- assign entire requirement groups at once
- **Per-Member Dashboard** -- each person sees their assignments, completion %, overdue items
- **Comments/Discussion** -- threaded comments on each objective
- **Audit Trail** -- every action logged with user, timestamp, and details

### Assessment Deliverables
- **POA&M Generator** -- Plan of Action & Milestones for incomplete objectives with risk levels, remediation plans, and milestone dates
- **Assessment Report** -- printable/PDF report covering all families, objectives, artifacts, and POA&M
- **CSV Export** -- full data export with assignments and status

### User Experience
- **Dark/Light Mode** -- toggle with persistent preference
- **Font Size Controls** -- adjustable for accessibility
- **Toast Notifications** -- non-intrusive feedback
- **Responsive Design** -- works on desktop and tablet

### Security
- **CSRF Protection** -- session-based tokens on all forms and API calls
- **XSS Prevention** -- escaped output in all templates and JS contexts
- **Login Rate Limiting** -- 5 attempts per 5 minutes per IP
- **Security Headers** -- CSP, X-Frame-Options, HSTS, X-Content-Type-Options
- **File Upload Hardening** -- extension whitelist, 100MB limit, path traversal protection
- **Secure Sessions** -- httponly, samesite, secure cookies in production

See [SECURITY.md](SECURITY.md) for full details.

---

## Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/jonathancaruso/cmmc-tracker.git
cd cmmc-tracker
docker compose up -d
```

Open **http://localhost:3300** -- you'll be prompted to create your admin account on first visit.

Data persists in a Docker volume. To back up:
```bash
docker compose cp cmmc-tracker:/data ./backup
```

### Local Python

```bash
git clone https://github.com/jonathancaruso/cmmc-tracker.git
cd cmmc-tracker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open **http://localhost:3300**

The database auto-seeds all 320 objectives from `nist-800-171a.xlsx` on first run.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_SECRET` | Random (regenerated on restart) | Session secret key. **Set this in production.** |
| `FLASK_ENV` | `development` | Set to `production` for secure cookies + HSTS |
| `DB_PATH` | `./cmmc.db` | Path to SQLite database |
| `UPLOAD_PATH` | `./uploads` | Path to artifact storage |
| `FLASK_DEBUG` | `1` | Set to `0` in production |

---

## Usage

1. **First Visit** -- create your admin account (16-char password with complexity requirements)
2. **Add Users** -- Admin > Users to create accounts for your team
3. **Add Domains/Assets** -- Config page to define your AD domains or asset categories
4. **Browse Families** -- click any family card on the dashboard
5. **Assign Objectives** -- assign team members to collect evidence
6. **Upload Artifacts** -- attach evidence files, they auto-rename to CMMC format
7. **Link Evidence** -- link shared artifacts across multiple objectives
8. **Track Progress** -- dashboard shows real-time completion by family
9. **Generate POA&M** -- document remediation plans for incomplete objectives
10. **Export Report** -- print assessment report or export CSV

---

## Data Files

| File | Description |
|------|-------------|
| `nist-800-171a.xlsx` | SP 800-171A assessment objectives (source data for all 320 objectives) |
| `nist-800-171.xlsx` | SP 800-171 security requirements with discussion text |
| `ArtifactHash.ps1` | Official CMMC v1.11 PowerShell hashing script (DoD CIO format) |

---

## Artifact Hashing

The built-in hashing tool generates two files:
- `CMMCAssessmentArtifacts.log` -- SHA-256 hash of every uploaded file
- `CMMCAssessmentLogHash.log` -- SHA-256 hash of the log itself

These match the format required by eMASS for CMMC assessments.

---

## Tech Stack

- **Backend:** Python 3.10+ / Flask 3.x
- **Database:** SQLite (zero config, single file)
- **Auth:** Session-based with Werkzeug scrypt password hashing
- **Frontend:** Vanilla JS + Jinja2 templates (no build step)
- **Deployment:** Docker or bare Python

---

## Contributing

Contributions welcome. Please:

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Test that `python app.py` starts without errors
5. Submit a PR

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

## Disclaimer

This tool assists with CMMC assessment preparation. It does not guarantee compliance or certification. Consult with a certified CMMC assessor (C3PAO) for official assessment guidance.
