begin;

-- ============================================================
-- Extensions
-- ============================================================

create schema if not exists extensions;

create extension if not exists pgcrypto with schema extensions;
create extension if not exists postgis with schema extensions;

-- ============================================================
-- Enum types
-- ============================================================

create type public.user_role as enum (
    'resident',
    'moderator',
    'administrator'
);

create type public.issue_category as enum (
    'pothole',
    'garbage',
    'streetlight'
);

create type public.issue_status as enum (
    'reported',
    'community_verified',
    'in_progress',
    'resolution_submitted',
    'resolved'
);

create type public.evidence_kind as enum (
    'report_photo',
    'additional_photo',
    'resolution_photo'
);

create type public.confirmation_kind as enum (
    'issue',
    'resolution'
);

create type public.ai_run_kind as enum (
    'classification',
    'duplicate_comparison',
    'before_after_comparison'
);

create type public.ai_run_status as enum (
    'pending',
    'succeeded',
    'failed'
);

create type public.flag_status as enum (
    'open',
    'reviewing',
    'dismissed',
    'actioned'
);

-- ============================================================
-- Profiles
-- Safe application data linked to Supabase Auth.
-- Email remains only inside auth.users.
-- ============================================================

create table public.profiles (
    id uuid primary key
        references auth.users(id)
        on delete cascade,

    display_name text not null default 'Resident',

    role public.user_role not null default 'resident',

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint profiles_display_name_length_check
        check (
            char_length(btrim(display_name)) between 1 and 80
        )
);

-- ============================================================
-- Civic issues
-- Contains only a rounded location suitable for public display.
-- ============================================================

create table public.civic_issues (
    id uuid primary key default gen_random_uuid(),

    category public.issue_category not null,

    approved_summary text not null,

    public_location extensions.geography(point, 4326) not null,

    status public.issue_status not null default 'reported',

    created_by uuid not null
        references public.profiles(id)
        on delete restrict,

    merged_into_issue_id uuid,

    -- Used by the status trigger when a status change has evidence.
    status_evidence_id uuid,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint civic_issues_summary_length_check
        check (
            char_length(btrim(approved_summary)) between 1 and 500
        ),

    constraint civic_issues_not_merged_into_self_check
        check (
            merged_into_issue_id is null
            or merged_into_issue_id <> id
        ),

    constraint civic_issues_merged_issue_fk
        foreign key (merged_into_issue_id)
        references public.civic_issues(id)
        on delete restrict
);

comment on column public.civic_issues.public_location is
    'Rounded or approximate location safe for public display.';

-- ============================================================
-- Reports
-- Each report contains the resident's exact private location.
-- ============================================================

create table public.reports (
    id uuid primary key default gen_random_uuid(),

    issue_id uuid not null
        references public.civic_issues(id)
        on delete restrict,

    reporter_id uuid not null
        references public.profiles(id)
        on delete restrict,

    exact_location extensions.geography(point, 4326) not null,

    approved_summary text not null,

    created_at timestamptz not null default now(),

    constraint reports_summary_length_check
        check (
            char_length(btrim(approved_summary)) between 1 and 500
        ),

    -- Supports composite foreign keys that verify evidence and
    -- reports belong to the same civic issue.
    constraint reports_id_issue_unique
        unique (id, issue_id)
);

comment on column public.reports.exact_location is
    'Exact resident-submitted location. Never expose through public policies or responses.';

-- ============================================================
-- Evidence metadata
-- Files themselves will live in the private evidence bucket.
-- Bucket size must use the same 10 MiB limit.
-- ============================================================

create table public.evidence (
    id uuid primary key default gen_random_uuid(),

    issue_id uuid not null
        references public.civic_issues(id)
        on delete restrict,

    report_id uuid,

    uploader_id uuid not null
        references public.profiles(id)
        on delete restrict,

    kind public.evidence_kind not null,

    storage_path text not null unique,

    mime_type text not null,

    byte_size bigint not null,

    created_at timestamptz not null default now(),

    constraint evidence_storage_path_length_check
        check (
            char_length(btrim(storage_path)) between 1 and 1024
        ),

    constraint evidence_mime_type_length_check
        check (
            char_length(btrim(mime_type)) between 1 and 100
        ),

    constraint evidence_size_check
        check (
            byte_size > 0
            and byte_size <= 10485760
        ),

    constraint evidence_report_kind_check
        check (
            (kind = 'report_photo' and report_id is not null)
            or kind = 'additional_photo'
            or (kind = 'resolution_photo' and report_id is null)
        ),

    constraint evidence_report_same_issue_fk
        foreign key (report_id, issue_id)
        references public.reports(id, issue_id)
        on delete restrict,

    constraint evidence_id_issue_unique
        unique (id, issue_id)
);

-- The current status evidence must belong to the same issue.
alter table public.civic_issues
    add constraint civic_issues_status_evidence_same_issue_fk
    foreign key (status_evidence_id, id)
    references public.evidence(id, issue_id)
    on delete restrict;

-- ============================================================
-- Confirmations
-- A withdrawn confirmation remains available for audit history.
-- ============================================================

create table public.confirmations (
    id uuid primary key default gen_random_uuid(),

    issue_id uuid not null
        references public.civic_issues(id)
        on delete restrict,

    confirmer_id uuid not null
        references public.profiles(id)
        on delete restrict,

    kind public.confirmation_kind not null,

    evidence_id uuid,

    created_at timestamptz not null default now(),
    withdrawn_at timestamptz,

    constraint confirmations_evidence_kind_check
        check (
            (kind = 'issue' and evidence_id is null)
            or
            (kind = 'resolution' and evidence_id is not null)
        ),

    constraint confirmations_withdrawal_time_check
        check (
            withdrawn_at is null
            or withdrawn_at >= created_at
        ),

    constraint confirmations_evidence_same_issue_fk
        foreign key (evidence_id, issue_id)
        references public.evidence(id, issue_id)
        on delete restrict
);

-- One active confirmation of each kind per resident and issue.
create unique index confirmations_one_active_per_kind
    on public.confirmations (issue_id, confirmer_id, kind)
    where withdrawn_at is null;

-- ============================================================
-- Immutable status history
-- ============================================================

create table public.status_events (
    id uuid primary key default gen_random_uuid(),

    issue_id uuid not null
        references public.civic_issues(id)
        on delete restrict,

    old_status public.issue_status,

    new_status public.issue_status not null,

    -- Null represents an internal/system operation.
    actor_id uuid
        references public.profiles(id)
        on delete restrict,

    evidence_id uuid,

    occurred_at timestamptz not null default now(),

    constraint status_events_actual_change_check
        check (
            old_status is null
            or old_status <> new_status
        ),

    constraint status_events_evidence_same_issue_fk
        foreign key (evidence_id, issue_id)
        references public.evidence(id, issue_id)
        on delete restrict
);

-- ============================================================
-- AI runs
-- Raw model output stays separate from validated application data.
-- ============================================================

create table public.ai_runs (
    id uuid primary key default gen_random_uuid(),

    issue_id uuid
        references public.civic_issues(id)
        on delete restrict,

    report_id uuid
        references public.reports(id)
        on delete restrict,

    requested_by uuid
        references public.profiles(id)
        on delete restrict,

    task public.ai_run_kind not null,

    status public.ai_run_status not null default 'pending',

    model text not null,

    raw_output jsonb,

    validated_output jsonb,

    confidence numeric(5, 4),

    error_message text,

    created_at timestamptz not null default now(),
    completed_at timestamptz,

    constraint ai_runs_model_length_check
        check (
            char_length(btrim(model)) between 1 and 120
        ),

    constraint ai_runs_confidence_check
        check (
            confidence is null
            or confidence between 0 and 1
        ),

    constraint ai_runs_error_length_check
        check (
            error_message is null
            or char_length(error_message) <= 2000
        ),

    constraint ai_runs_completed_time_check
        check (
            completed_at is null
            or completed_at >= created_at
        )
);

-- ============================================================
-- Follows
-- ============================================================

create table public.follows (
    issue_id uuid not null
        references public.civic_issues(id)
        on delete restrict,

    user_id uuid not null
        references public.profiles(id)
        on delete cascade,

    created_at timestamptz not null default now(),

    primary key (issue_id, user_id)
);

-- ============================================================
-- Flags
-- Moderation remains auditable rather than deleting complaints.
-- ============================================================

create table public.flags (
    id uuid primary key default gen_random_uuid(),

    issue_id uuid not null
        references public.civic_issues(id)
        on delete restrict,

    evidence_id uuid,

    flagger_id uuid not null
        references public.profiles(id)
        on delete restrict,

    reason text not null,

    status public.flag_status not null default 'open',

    reviewer_id uuid
        references public.profiles(id)
        on delete restrict,

    review_notes text,

    reviewed_at timestamptz,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint flags_reason_length_check
        check (
            char_length(btrim(reason)) between 10 and 1000
        ),

    constraint flags_review_notes_length_check
        check (
            review_notes is null
            or char_length(review_notes) <= 2000
        ),

    constraint flags_review_state_check
        check (
            (
                status = 'open'
                and reviewer_id is null
                and reviewed_at is null
            )
            or
            (
                status = 'reviewing'
                and reviewer_id is not null
                and reviewed_at is null
            )
            or
            (
                status in ('dismissed', 'actioned')
                and reviewer_id is not null
                and reviewed_at is not null
            )
        ),

    constraint flags_evidence_same_issue_fk
        foreign key (evidence_id, issue_id)
        references public.evidence(id, issue_id)
        on delete restrict
);

-- ============================================================
-- Query indexes
-- ============================================================

create index civic_issues_public_location_gist
    on public.civic_issues
    using gist (public_location);

create index civic_issues_status_idx
    on public.civic_issues (status);

create index civic_issues_category_idx
    on public.civic_issues (category);

create index civic_issues_merged_into_idx
    on public.civic_issues (merged_into_issue_id)
    where merged_into_issue_id is not null;

create index reports_exact_location_gist
    on public.reports
    using gist (exact_location);

create index reports_issue_idx
    on public.reports (issue_id);

create index reports_reporter_idx
    on public.reports (reporter_id);

create index evidence_issue_idx
    on public.evidence (issue_id);

create index evidence_report_idx
    on public.evidence (report_id)
    where report_id is not null;

create index evidence_uploader_idx
    on public.evidence (uploader_id);

create index confirmations_confirmer_idx
    on public.confirmations (confirmer_id);

create index status_events_issue_time_idx
    on public.status_events (issue_id, occurred_at desc);

create index ai_runs_issue_idx
    on public.ai_runs (issue_id)
    where issue_id is not null;

create index ai_runs_report_idx
    on public.ai_runs (report_id)
    where report_id is not null;

create index ai_runs_status_idx
    on public.ai_runs (status);

create index follows_user_idx
    on public.follows (user_id);

create index flags_issue_status_idx
    on public.flags (issue_id, status);

create index flags_evidence_idx
    on public.flags (evidence_id)
    where evidence_id is not null;

create index flags_flagger_idx
    on public.flags (flagger_id);

-- ============================================================
-- Updated-at function and triggers
-- ============================================================

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger profiles_set_updated_at
before update on public.profiles
for each row
execute function public.set_updated_at();

create trigger civic_issues_set_updated_at
before update on public.civic_issues
for each row
execute function public.set_updated_at();

create trigger flags_set_updated_at
before update on public.flags
for each row
execute function public.set_updated_at();

-- ============================================================
-- Automatic profile creation
-- Role always defaults to resident. Browser metadata cannot assign
-- moderator or administrator privileges.
-- ============================================================

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.profiles (id, display_name)
    values (
        new.id,
        coalesce(
            nullif(
                left(
                    btrim(new.raw_user_meta_data ->> 'display_name'),
                    80
                ),
                ''
            ),
            'Resident'
        )
    );

    return new;
end;
$$;

drop trigger if exists create_profile_after_signup on auth.users;

create trigger create_profile_after_signup
after insert on auth.users
for each row
execute function public.handle_new_user();

-- Backfill profiles if test users already existed before this migration.
insert into public.profiles (id, display_name)
select
    users.id,
    coalesce(
        nullif(
            left(
                btrim(users.raw_user_meta_data ->> 'display_name'),
                80
            ),
            ''
        ),
        'Resident'
    )
from auth.users as users
on conflict (id) do nothing;

-- ============================================================
-- Status-event triggers
-- ============================================================

create or replace function public.log_initial_issue_status()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.status_events (
        issue_id,
        old_status,
        new_status,
        actor_id,
        evidence_id
    )
    values (
        new.id,
        null,
        new.status,
        new.created_by,
        new.status_evidence_id
    );

    return new;
end;
$$;

create trigger civic_issues_log_initial_status
after insert on public.civic_issues
for each row
execute function public.log_initial_issue_status();

create or replace function public.log_issue_status_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    if old.status is distinct from new.status then
        insert into public.status_events (
            issue_id,
            old_status,
            new_status,
            actor_id,
            evidence_id
        )
        values (
            new.id,
            old.status,
            new.status,
            auth.uid(),
            new.status_evidence_id
        );
    end if;

    return new;
end;
$$;

create trigger civic_issues_log_status_change
after update of status on public.civic_issues
for each row
execute function public.log_issue_status_change();

create or replace function public.reject_status_event_change()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    raise exception 'Status events are immutable';
end;
$$;

create trigger status_events_reject_change
before update or delete on public.status_events
for each row
execute function public.reject_status_event_change();

-- ============================================================
-- Confirmation validation
-- Runs with definer privileges so RLS cannot hide records needed
-- for the cross-table security checks.
-- ============================================================

create or replace function public.validate_confirmation()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    evidence_issue_id uuid;
    evidence_uploader_id uuid;
    selected_evidence_kind public.evidence_kind;
begin
    -- Withdrawn records remain historical and are not active.
    if new.withdrawn_at is not null then
        return new;
    end if;

    if new.kind = 'issue' then
        if new.evidence_id is not null then
            raise exception
                'Issue confirmations must not reference evidence';
        end if;

        if exists (
            select 1
            from public.reports
            where reports.issue_id = new.issue_id
              and reports.reporter_id = new.confirmer_id
        ) then
            raise exception
                'Report authors cannot confirm their own issue';
        end if;

        return new;
    end if;

    if new.kind = 'resolution' then
        if new.evidence_id is null then
            raise exception
                'Resolution confirmations require resolution evidence';
        end if;

        select
            evidence.issue_id,
            evidence.uploader_id,
            evidence.kind
        into
            evidence_issue_id,
            evidence_uploader_id,
            selected_evidence_kind
        from public.evidence
        where evidence.id = new.evidence_id;

        if not found then
            raise exception 'Referenced evidence does not exist';
        end if;

        if evidence_issue_id <> new.issue_id then
            raise exception
                'Confirmation evidence must belong to the same issue';
        end if;

        if selected_evidence_kind <> 'resolution_photo' then
            raise exception
                'Resolution confirmations require resolution-photo evidence';
        end if;

        if evidence_uploader_id = new.confirmer_id then
            raise exception
                'Residents cannot confirm resolution evidence they uploaded';
        end if;

        return new;
    end if;

    raise exception 'Unsupported confirmation kind';
end;
$$;

create trigger confirmations_validate_before_write
before insert or update on public.confirmations
for each row
execute function public.validate_confirmation();

-- ============================================================
-- Secure default
-- No browser/client access is allowed until explicit RLS policies
-- are added in the later security-policy migration.
-- ============================================================

alter table public.profiles enable row level security;
alter table public.civic_issues enable row level security;
alter table public.reports enable row level security;
alter table public.evidence enable row level security;
alter table public.confirmations enable row level security;
alter table public.status_events enable row level security;
alter table public.ai_runs enable row level security;
alter table public.follows enable row level security;
alter table public.flags enable row level security;

-- Trigger functions are not intended to be called directly.
revoke execute on function public.handle_new_user() from public;
revoke execute on function public.log_initial_issue_status() from public;
revoke execute on function public.log_issue_status_change() from public;
revoke execute on function public.reject_status_event_change() from public;
revoke execute on function public.validate_confirmation() from public;

commit;