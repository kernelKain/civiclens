# CivicLens

CivicLens turns separate resident reports about local infrastructure problems into shared, community-verified civic issue records. The MVP pilot focuses on potholes, uncollected garbage, and broken streetlights in HSR Layout, Bengaluru.

Production: [https://civiclens-rho.vercel.app](https://civiclens-rho.vercel.app)

## Current milestone

The repository contains the FastAPI/Jinja foundation plus the Supabase foundation for:

- Email-and-password registration, confirmation, sign-in, token refresh, and sign-out.
- Locally verified Supabase access tokens.
- Protected Report, Following, and Account pages.
- Automatic resident profile creation.
- PostGIS and nine application tables.
- Row Level Security (RLS) and restricted SQL grants.
- A private evidence Storage bucket.
- Desktop and mobile CivicLens navigation.
- Vercel deployment configuration.

Reporting, maps, AI analysis, notifications, and other product features are intentionally not implemented yet.

## Technology stack

- Backend: Python 3.14, FastAPI, Uvicorn
- Templates: Jinja2
- Interface: Bootstrap 5, Bootstrap Icons, custom CSS, vanilla JavaScript
- Authentication, database, geospatial data, and Storage: Supabase
- Deployment: Vercel
- Tests: pytest and HTTPX

## Repository structure

```text
app/
  auth/                 Supabase client, cookies, CSRF, JWT verification, middleware
  routes/               Authentication and page routes
  templates/            Shared, authentication, error, and page templates
public/                  CSS and browser JavaScript
supabase/
  migrations/           Reviewable database, RLS, index, and Storage migrations
tests/                   Unit, route, privacy, and opt-in hosted acceptance tests
```

## Requirements

- Python 3.14
- Git
- Node.js/npm (for the Supabase CLI)
- A Supabase account and project
- A Vercel account for production deployment

Windows Smart App Control may block unsigned native Python extensions used by `cryptography`. If that occurs, run the application and tests in WSL or a GitHub Codespace rather than weakening Windows security.

## Local setup — PowerShell

```powershell
git clone https://github.com/kernelKain/civiclens.git
cd civiclens

py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

Copy-Item .env.example .env
python -m uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Local setup — WSL/Linux

```bash
python3 -m venv ~/.virtualenvs/civiclens
source ~/.virtualenvs/civiclens/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

cp .env.example .env
python -m uvicorn app.main:app --reload --host 0.0.0.0
```

## Environment variables

Copy `.env.example` to `.env` and replace the placeholders. Never commit `.env`, Supabase secret/service-role keys, database passwords, access tokens, refresh tokens, or signing keys.

| Variable | Purpose |
| --- | --- |
| `CIVICLENS_APP_NAME` | Application display name. |
| `CIVICLENS_ENVIRONMENT` | `development`, `preview`, or `production`; controls secure cookies. |
| `CIVICLENS_DEBUG` | Enables FastAPI debug behavior locally only. |
| `CIVICLENS_PUBLIC_BASE_URL` | Public application origin. |
| `CIVICLENS_SUPABASE_URL` | Supabase project URL. |
| `CIVICLENS_SUPABASE_PUBLISHABLE_KEY` | Browser-safe publishable/anon API key. |
| `CIVICLENS_AUTH_CONFIRMATION_REDIRECT` | Allowed destination after email confirmation. |

Production values belong in Vercel project settings. Use:

```text
CIVICLENS_ENVIRONMENT=production
CIVICLENS_DEBUG=false
CIVICLENS_PUBLIC_BASE_URL=https://civiclens-rho.vercel.app
CIVICLENS_AUTH_CONFIRMATION_REDIRECT=https://civiclens-rho.vercel.app/auth/sign-in?confirmed=1
```

## Supabase project and migrations

Install and authenticate the CLI:

```powershell
npm install
npx supabase login
npx supabase link --project-ref YOUR_PROJECT_REF
```

Review migration status:

```powershell
npx supabase migration list
```

Apply migrations that are not yet present remotely:

```powershell
npx supabase db push
```

The migrations are:

1. `20260806102053_civic_foundation.sql` — PostGIS, enums, nine tables, constraints, triggers, indexes, automatic profiles, and RLS enablement.
2. `20260806112231_indexes_rls_storage.sql` — final indexes, least-privilege grants, RLS policies, helper functions, and the private evidence bucket.

The nine public application tables are:

- `profiles`
- `civic_issues`
- `reports`
- `evidence`
- `confirmations`
- `status_events`
- `ai_runs`
- `follows`
- `flags`

PostGIS is installed in the `extensions` schema. Exact report locations remain private; public issues contain only an approximate public geography point.

## Supabase Auth Dashboard actions

In **Authentication → Providers → Email**, confirm:

- Email provider is enabled.
- New email sign-ups are enabled.
- Confirm email is enabled.
- Minimum password length is 10.

In **Authentication → URL Configuration**, set:

```text
Site URL
https://civiclens-rho.vercel.app

Redirect URLs
http://localhost:8000/auth/sign-in?confirmed=1
http://127.0.0.1:8000/auth/sign-in?confirmed=1
https://civiclens-rho.vercel.app/auth/sign-in?confirmed=1
```

The same settings are maintained in `supabase/config.toml`. Apply them to the linked hosted project with:

```powershell
npx supabase config push
```

For a production launch, configure a trusted custom SMTP provider in Supabase. The default mail service is suitable only for limited testing and has restrictive delivery limits.

## Automatic profiles

The `create_profile_after_signup` trigger runs after a row is added to `auth.users`. It creates the matching `public.profiles` row using the submitted `display_name`, while the database—not browser metadata—assigns the default `resident` role.

## RLS and security model

RLS is enabled on all nine application tables, and broad client privileges are revoked before narrowly scoped grants are added.

- **Profiles:** residents can read and edit only their own display name. Only staff can read all profiles. Residents cannot assign themselves a staff role.
- **Civic issues:** anonymous and authenticated visitors can read only public, visible, non-merged issue fields. Client-side issue writes are not enabled yet.
- **Reports:** exact locations and report records are visible only to their owner or staff.
- **Evidence metadata:** residents can read only metadata they uploaded; staff can read all.
- **Confirmations:** residents can read only their own confirmations; staff can read all.
- **Status events:** visitors receive only safe history fields for visible issues. Status history is immutable.
- **AI runs:** residents can read only runs they requested; clients cannot write model results.
- **Follows:** residents can read, add, and remove only their own follows.
- **Flags:** residents can create and read only their own flags; only staff can update review state.
- **Storage:** the `evidence` bucket is private. Authenticated residents can upload only to `<their-user-uuid>/<random-file-name>`, read only their own objects, and cannot overwrite or delete objects directly.

Anonymous database writes and anonymous Storage uploads are denied.

## Tests

Run the committed unit and route tests:

```powershell
python -m pytest -m "not acceptance"
```

Hosted acceptance tests are opt-in so secrets are never committed. Export two confirmed resident credentials, then run:

```powershell
$env:CIVICLENS_ACCEPTANCE_SUPABASE_URL="https://YOUR_PROJECT_REF.supabase.co"
$env:CIVICLENS_ACCEPTANCE_PUBLISHABLE_KEY="sb_publishable_REPLACE_ME"
$env:CIVICLENS_ACCEPTANCE_RESIDENT_A_EMAIL="resident-a@example.com"
$env:CIVICLENS_ACCEPTANCE_RESIDENT_A_PASSWORD="REPLACE_ME"
$env:CIVICLENS_ACCEPTANCE_RESIDENT_B_EMAIL="resident-b@example.com"
$env:CIVICLENS_ACCEPTANCE_RESIDENT_B_PASSWORD="REPLACE_ME"

python -m pytest -m acceptance
```

These acceptance tests verify:

- Both residents can sign in.
- Automatic profiles exist.
- Resident A cannot read Resident B's private profile.
- Anonymous database inserts fail.
- Anonymous Storage uploads fail.
- A resident cannot upload under another UUID folder.
- Resident B cannot read Resident A's private evidence object.

Acceptance tests upload a tiny uniquely named object. Remove test objects from the Supabase Storage Dashboard after a hosted test run until a trusted server-side cleanup job is added.

## Deployment

Vercel deploys the FastAPI application using `vercel.json`. After setting production environment variables, verify:

```text
https://civiclens-rho.vercel.app/
https://civiclens-rho.vercel.app/health
```

The health endpoint must return a small JSON response without secrets.

## Secret-handling rules

- Commit only `.env.example` placeholders.
- Never expose a Supabase secret/service-role key to templates or browser JavaScript.
- Access and refresh tokens remain in `HttpOnly` cookies.
- Never log passwords or raw tokens.
- Authentication pages and responses use `Cache-Control: private, no-store`.
