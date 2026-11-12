-- Access codes handed out individually, so usage is attributable to a
-- person and a single code can be revoked without disturbing the others.
create table if not exists guest_passes (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid references organizations(id) on delete cascade,
    code text not null unique,
    label text not null default '',          -- who it was given to
    note text,

    expires_at timestamptz not null,
    revoked boolean not null default false,

    -- Per-pass ceilings. Calls are the expensive one.
    max_messages int not null default 20,
    max_calls int not null default 1,

    used_messages int not null default 0,
    used_calls int not null default 0,

    first_used_at timestamptz,
    last_used_at timestamptz,
    created_at timestamptz not null default now()
);

create index if not exists guest_passes_code_idx on guest_passes(lower(code));

-- Every guest turn, kept separately so cost can be totalled per day
-- independently of the per-pass counters.
create table if not exists guest_events (
    id uuid primary key default uuid_generate_v4(),
    pass_id uuid references guest_passes(id) on delete cascade,
    kind text not null,                      -- message | call | tool
    detail text,
    cost_usd numeric(10, 6) not null default 0,
    created_at timestamptz not null default now()
);

create index if not exists guest_events_created_idx on guest_events(created_at);

alter table guest_passes enable row level security;
alter table guest_events enable row level security;

create policy guest_passes_service_role on guest_passes
    for all using (auth.role() = 'service_role');
create policy guest_events_service_role on guest_events
    for all using (auth.role() = 'service_role');
