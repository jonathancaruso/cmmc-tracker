# CMMC Artifact Tracker

Local tool for tracking NIST 800-171 Rev 2 assessment objective completion for CMMC Level 2 assessments. Tracks all 14 control families, 110 security requirements, and 320 assessment objectives.

## Features

- **Dashboard** with per-family progress bars and overall completion percentage
- **Family detail pages** with collapsible requirements and checkable objectives
- **Artifact uploads** — attach screenshots, docs, PDFs, spreadsheets to any objective
- **Team management** — add team members and assign artifact collection responsibilities
- **Bulk assignment** — assign an entire requirement group to a person
- **Due dates** with overdue tracking
- **Per-member progress view** — see each person's assignments, completion %, and overdue items
- **Search** — find any objective by ID, text, or family (embedded in nav, press `/` to focus)
- **CMMC artifact hashing** — SHA-256 hashing tool (official CMMC format) built into the dashboard
- **CSV export** with assigned-to column
- **Discussion text** from SP 800-171 for each requirement
- **Basic/Derived classification** tags on each requirement
- **Dark mode** UI

## Requirements

- Python 3.10+
- pip

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install flask openpyxl
python app.py
```

Open http://localhost:3300

The database auto-seeds from `nist-800-171a.xlsx` on first run.

## Data Files

- `nist-800-171a.xlsx` — SP 800-171A assessment objectives (297 bracketed + 23 single-objective requirements)
- `nist-800-171.xlsx` — SP 800-171 security requirements with discussions
- `ArtifactHash.ps1` — Official CMMC v1.11 PowerShell hashing script (from DoD CIO guide)

## Usage

1. **Add team members** at `/config`
2. **Browse families** from the dashboard, expand requirements, assign people
3. **Upload artifacts** (evidence) to each objective
4. **Check objectives** as captured (requires at least one artifact attached)
5. **Hash artifacts** when ready — click the 🔒 button on the dashboard to generate CMMC-compliant SHA-256 hashes
6. **Export CSV** for reporting

## Hashing

The built-in hashing tool generates two files in `uploads/`:
- `CMMCAssessmentArtifacts.log` — SHA-256 hash of every uploaded file
- `CMMCAssessmentLogHash.log` — SHA-256 hash of the log itself

These match the format required by eMASS for CMMC assessments. The standalone `ArtifactHash.ps1` script can also be run directly on Windows/Linux/macOS via PowerShell.

## Storage

All data is local:
- `cmmc.db` — SQLite database (objectives, assignments, team members)
- `uploads/` — uploaded artifact files organized by objective ID

**This is a local-only tool. Do not deploy to any public host.**
