# CivicLens

CivicLens turns separate resident reports about local infrastructure problems into shared, community-verified civic issue records.

The initial issue categories are:

- Potholes
- Uncollected garbage
- Broken streetlights

## Pilot area

The CivicLens MVP is designed for:

- City: Bengaluru, Karnataka, India
- Neighbourhood: HSR Layout
- Focus area: approximately 3 km around HSR Layout
- Initial location: `12.9121, 77.6446`
- Interface language: English

## Current milestone

This repository currently contains only the CivicLens application foundation.

The foundation will include:

- FastAPI application structure
- Jinja2 template rendering
- CivicLens branding
- Bootstrap desktop navigation
- Mobile bottom navigation
- Placeholder pages
- Health-check endpoint
- Environment-based configuration
- Vercel deployment configuration

The current pages are placeholders and do not yet implement CivicLens product functionality.

## Technology stack

- Backend: Python and FastAPI
- Templates: Jinja2
- Interface: Bootstrap 5 and Bootstrap Icons
- Styling: Custom CSS
- Browser logic: Vanilla JavaScript
- Deployment: Vercel

## Requirements

- Python 3.14
- Git
- A PowerShell terminal
- A Vercel account for deployment

## Local setup

```powershell
git clone https://github.com/kernelKain/civiclens.git
cd civiclens
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload