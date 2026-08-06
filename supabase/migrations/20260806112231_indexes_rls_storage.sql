begin;

-- ============================================================
-- Schema adjustments required by Steps 4 and 5
-- ============================================================

-- Step 3 used occurred_at, but the required Step 4 index expects
-- status_events.created_at. Rename the column without losing data.
alter table public.status_events
rename column occurred_at to created_at;

-- Required by the public civic-issue visibility policy.
alter table public.civic_issues
add column is_hidden boolean not null default false;

comment on column public.civic_issues.is_hidden is
    'Set by trusted moderation operations to remove an issue from public results.';

-- ============================================================
-- Step 4: Required indexes
-- ============================================================

-- Remove older indexes whose work is replaced by the required
-- composite indexes below. Keeping both would waste storage and
-- make inserts and updates slower.
drop index if exists public.civic_issues_public_location_gist;
drop index if exists public.civic_issues_category_idx;
drop index if exists public.reports_issue_idx;
drop index if exists public.evidence_issue_idx;
drop index if exists public.status_events_issue_time_idx;
drop index if exists public.ai_runs_issue_idx;
drop index if exists public.follows_user_idx;

-- Specialized geographic index for approximate public issue points.
create index if not exists civic_issues_location_gist
on public.civic_issues
using gist (public_location);

-- This index may already exist from Step 3. IF NOT EXISTS prevents
-- creating it twice.
create index if not exists reports_exact_location_gist
on public.reports
using gist (exact_location);

-- Supports category + status filtering, ordered newest first.
create index if not exists civic_issues_category_status_created
on public.civic_issues (
    category,
    status,
    created_at desc
);

-- Supports loading the newest reports belonging to an issue.
create index if not exists reports_issue_created
on public.reports (
    issue_id,
    created_at desc
);

-- Supports loading the newest evidence belonging to an issue.
create index if not exists evidence_issue_created
on public.evidence (
    issue_id,
    created_at desc
);

-- Supports loading an issue's status history.
create index if not exists status_events_issue_created
on public.status_events (
    issue_id,
    created_at
);

-- Supports loading the newest AI operations for an issue.
create index if not exists ai_runs_issue_created
on public.ai_runs (
    issue_id,
    created_at desc
);

-- Supports loading the issues followed by a user.
create index if not exists follows_user_created
on public.follows (
    user_id,
    created_at desc
);

-- Supports moderation queues ordered by flag status and time.
create index if not exists flags_status_created
on public.flags (
    status,
    created_at
);

-- ============================================================
-- Step 5: Private security helper
-- ============================================================

create schema if not exists private;

-- No client gets automatic access to the private schema.
revoke all on schema private
from public, anon, authenticated;

-- Signed-in users require schema usage so RLS policies can call
-- the staff helper. This does not expose tables inside the schema.
grant usage on schema private
to authenticated;

create or replace function private.is_staff()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.profiles
        where profiles.id = (select auth.uid())
          and profiles.role in ('moderator', 'administrator')
    );
$$;

-- Functions receive PUBLIC execute permission by default.
-- Remove it, then grant only to signed-in users.
revoke all on function private.is_staff()
from public;

grant execute on function private.is_staff()
to authenticated;

-- ============================================================
-- Safe helper for public status-event visibility
-- ============================================================

-- Status-event policies need to check private issue visibility
-- columns. This narrowly scoped function exposes only a boolean.
create or replace function public.is_public_issue(
    target_issue_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select exists (
        select 1
        from public.civic_issues
        where civic_issues.id = target_issue_id
          and civic_issues.is_hidden = false
          and civic_issues.merged_into_issue_id is null
    );
$$;

revoke all on function public.is_public_issue(uuid)
from public;

grant execute on function public.is_public_issue(uuid)
to anon, authenticated;

-- ============================================================
-- Remove broad client permissions
-- ============================================================

-- RLS controls rows. SQL grants control which operations and columns
-- a role may attempt to access. Both layers are necessary.
revoke all privileges on table public.profiles
from public, anon, authenticated;

revoke all privileges on table public.civic_issues
from public, anon, authenticated;

revoke all privileges on table public.reports
from public, anon, authenticated;

revoke all privileges on table public.evidence
from public, anon, authenticated;

revoke all privileges on table public.confirmations
from public, anon, authenticated;

revoke all privileges on table public.status_events
from public, anon, authenticated;

revoke all privileges on table public.ai_runs
from public, anon, authenticated;

revoke all privileges on table public.follows
from public, anon, authenticated;

revoke all privileges on table public.flags
from public, anon, authenticated;

-- ============================================================
-- Profiles policies
-- ============================================================

-- Residents can read their own profile.
create policy profiles_read_own
on public.profiles
for select
to authenticated
using (
    id = (select auth.uid())
);

-- Staff can read every safe application profile.
create policy profiles_staff_read
on public.profiles
for select
to authenticated
using (
    (select private.is_staff())
);

-- Residents can update their own profile row.
create policy profiles_update_own
on public.profiles
for update
to authenticated
using (
    id = (select auth.uid())
)
with check (
    id = (select auth.uid())
);

grant select on table public.profiles
to authenticated;

-- Column-level permission prevents residents from changing role.
grant update (display_name)
on table public.profiles
to authenticated;

-- ============================================================
-- Civic issue policies
-- ============================================================

-- Signed-out and signed-in users can read only visible,
-- non-merged issues.
create policy civic_issues_public_read
on public.civic_issues
for select
to anon, authenticated
using (
    is_hidden = false
    and merged_into_issue_id is null
);

-- Staff can also read hidden and merged issue rows.
create policy civic_issues_staff_read
on public.civic_issues
for select
to authenticated
using (
    (select private.is_staff())
);

-- Grant only columns safe for public maps and issue feeds.
-- created_by, is_hidden, merged_into_issue_id and
-- status_evidence_id are intentionally excluded.
grant select (
    id,
    category,
    approved_summary,
    public_location,
    status,
    created_at,
    updated_at
)
on table public.civic_issues
to anon, authenticated;

-- No client INSERT, UPDATE or DELETE permission is granted.

-- ============================================================
-- Report policies
-- ============================================================

create policy reports_read_own
on public.reports
for select
to authenticated
using (
    reporter_id = (select auth.uid())
);

create policy reports_staff_read
on public.reports
for select
to authenticated
using (
    (select private.is_staff())
);

grant select on table public.reports
to authenticated;

-- Reporting writes will be added later through a controlled flow.

-- ============================================================
-- Evidence metadata policies
-- ============================================================

create policy evidence_read_own
on public.evidence
for select
to authenticated
using (
    uploader_id = (select auth.uid())
);

create policy evidence_staff_read
on public.evidence
for select
to authenticated
using (
    (select private.is_staff())
);

grant select on table public.evidence
to authenticated;

-- Metadata INSERT, UPDATE and DELETE are not granted yet.

-- ============================================================
-- Confirmation policies
-- ============================================================

create policy confirmations_read_own
on public.confirmations
for select
to authenticated
using (
    confirmer_id = (select auth.uid())
);

create policy confirmations_staff_read
on public.confirmations
for select
to authenticated
using (
    (select private.is_staff())
);

grant select on table public.confirmations
to authenticated;

-- Confirmation writes will be introduced through the later
-- confirmation feature.

-- ============================================================
-- Status-event policies
-- ============================================================

-- Visitors can read status history only for visible issues.
create policy status_events_public_read
on public.status_events
for select
to anon, authenticated
using (
    public.is_public_issue(issue_id)
);

-- This allows staff RLS access to hidden-issue history.
-- Full sensitive columns should still be retrieved through FastAPI.
create policy status_events_staff_read
on public.status_events
for select
to authenticated
using (
    (select private.is_staff())
);

-- actor_id and evidence_id are not publicly exposed.
grant select (
    id,
    issue_id,
    old_status,
    new_status,
    created_at
)
on table public.status_events
to anon, authenticated;

-- No INSERT, UPDATE or DELETE grants are provided.
-- Step 3 triggers create events automatically.

-- ============================================================
-- AI-run policies
-- ============================================================

create policy ai_runs_read_own
on public.ai_runs
for select
to authenticated
using (
    requested_by = (select auth.uid())
);

create policy ai_runs_staff_read
on public.ai_runs
for select
to authenticated
using (
    (select private.is_staff())
);

grant select on table public.ai_runs
to authenticated;

-- Clients cannot insert or modify AI results.

-- ============================================================
-- Follow policies
-- ============================================================

create policy follows_read_own
on public.follows
for select
to authenticated
using (
    user_id = (select auth.uid())
);

create policy follows_staff_read
on public.follows
for select
to authenticated
using (
    (select private.is_staff())
);

create policy follows_insert_own
on public.follows
for insert
to authenticated
with check (
    user_id = (select auth.uid())
);

create policy follows_delete_own
on public.follows
for delete
to authenticated
using (
    user_id = (select auth.uid())
);

grant select on table public.follows
to authenticated;

-- Residents provide only these two columns. created_at uses its
-- database default.
grant insert (
    issue_id,
    user_id
)
on table public.follows
to authenticated;

grant delete on table public.follows
to authenticated;

-- ============================================================
-- Flag policies
-- ============================================================

create policy flags_read_own
on public.flags
for select
to authenticated
using (
    flagger_id = (select auth.uid())
);

create policy flags_staff_read
on public.flags
for select
to authenticated
using (
    (select private.is_staff())
);

create policy flags_insert_own
on public.flags
for insert
to authenticated
with check (
    flagger_id = (select auth.uid())
    and status = 'open'
    and reviewer_id is null
    and reviewed_at is null
);

create policy flags_staff_update
on public.flags
for update
to authenticated
using (
    (select private.is_staff())
)
with check (
    (select private.is_staff())
);

grant select on table public.flags
to authenticated;

-- Residents can only supply the content being flagged and reason.
grant insert (
    issue_id,
    evidence_id,
    flagger_id,
    reason
)
on table public.flags
to authenticated;

-- Staff can update only review-related fields.
grant update (
    status,
    reviewer_id,
    review_notes,
    reviewed_at
)
on table public.flags
to authenticated;

-- No client DELETE permission is provided.

-- ============================================================
-- Step 6: Private evidence Storage bucket
-- ============================================================

insert into storage.buckets (
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
)
values (
    'evidence',
    'evidence',
    false,
    10485760,
    array[
        'image/jpeg',
        'image/png',
        'image/webp'
    ]
)
on conflict (id) do update set
    name = excluded.name,
    public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

-- A resident can upload only inside a folder named with their
-- authenticated Supabase user UUID:
-- <user-uuid>/<random-file-uuid>.jpg
create policy evidence_upload_own_folder
on storage.objects
for insert
to authenticated
with check (
    bucket_id = 'evidence'
    and (storage.foldername(name))[1]
        = (select auth.uid())::text
);

-- A resident can directly read only objects they own.
create policy evidence_read_own_objects
on storage.objects
for select
to authenticated
using (
    bucket_id = 'evidence'
    and owner_id = (select auth.uid())::text
);

-- No resident UPDATE, overwrite or DELETE policies are added.

commit;