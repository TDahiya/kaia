-- Kaia AI Assistant — Initial Schema
-- Run in Supabase SQL Editor in order

-- Enable required extensions
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";

-- Organizations (future multi-tenant support)
create table if not exists organizations (
    id uuid primary key default uuid_generate_v4(),
    name text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Users
create table if not exists users (
    id uuid primary key references auth.users(id) on delete cascade,
    org_id uuid references organizations(id) on delete set null,
    email text not null,
    display_name text,
    role text not null default 'admin' check (role in ('admin', 'member')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Agents
create table if not exists agents (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references organizations(id) on delete cascade,
    name text not null,
    description text,
    system_prompt text not null default '',
    personality text,
    model_fast text not null default 'gpt-4o-mini',
    model_standard text not null default 'gpt-4o',
    model_premium text not null default 'gpt-4.1',
    voice_id text not null default 'aura-2-theia-en',
    language text not null default 'en',
    max_tool_calls_per_turn int not null default 15,
    is_default boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Integration connections (Google OAuth etc.)
create table if not exists integrations (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references organizations(id) on delete cascade,
    user_id uuid not null references users(id) on delete cascade,
    provider text not null check (provider in ('google', 'telnyx')),
    access_token_encrypted text,
    refresh_token_encrypted text,
    token_expiry timestamptz,
    scopes text[],
    status text not null default 'active' check (status in ('active', 'revoked', 'expired')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, provider)
);

-- Conversations
create table if not exists conversations (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references organizations(id) on delete cascade,
    user_id uuid not null references users(id) on delete cascade,
    agent_id uuid references agents(id) on delete set null,
    title text,
    mode text not null default 'text' check (mode in ('text', 'voice', 'phone')),
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    metadata jsonb default '{}'::jsonb
);

-- Messages
create table if not exists messages (
    id uuid primary key default uuid_generate_v4(),
    conversation_id uuid not null references conversations(id) on delete cascade,
    role text not null check (role in ('user', 'assistant', 'system', 'tool')),
    content text not null,
    tool_name text,
    tool_args jsonb,
    tool_result jsonb,
    tokens_in int,
    tokens_out int,
    model_used text,
    created_at timestamptz not null default now()
);

-- Persistent memories
create table if not exists memories (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references organizations(id) on delete cascade,
    user_id uuid not null references users(id) on delete cascade,
    category text not null default 'general'
        check (category in ('preference', 'fact', 'project', 'contact', 'general')),
    content text not null,
    importance int not null default 5 check (importance between 1 and 10),
    source text, -- conversation_id or 'manual' or 'weekly_summary'
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Weekly summaries
create table if not exists weekly_summaries (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references organizations(id) on delete cascade,
    user_id uuid not null references users(id) on delete cascade,
    week_start date not null,
    week_end date not null,
    summary text not null,
    memories_updated int not null default 0,
    conversations_processed int not null default 0,
    created_at timestamptz not null default now(),
    unique (user_id, week_start)
);

-- Phone numbers
create table if not exists phone_numbers (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references organizations(id) on delete cascade,
    provider text not null default 'telnyx',
    phone_number text not null,
    country_code text not null default 'IE',
    connection_id text,
    status text not null default 'active' check (status in ('active', 'inactive', 'pending')),
    created_at timestamptz not null default now()
);

-- Call logs
create table if not exists call_logs (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references organizations(id) on delete cascade,
    conversation_id uuid references conversations(id) on delete set null,
    phone_number_id uuid references phone_numbers(id) on delete set null,
    direction text not null check (direction in ('inbound', 'outbound')),
    caller_number text,
    callee_number text,
    status text not null default 'initiated'
        check (status in ('initiated', 'ringing', 'answered', 'completed', 'failed', 'busy', 'no_answer')),
    duration_seconds int,
    telnyx_call_control_id text,
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    metadata jsonb default '{}'::jsonb
);

-- Tool execution log
create table if not exists tool_executions (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references organizations(id) on delete cascade,
    conversation_id uuid references conversations(id) on delete set null,
    tool_name text not null,
    tool_args jsonb,
    result jsonb,
    success boolean not null default true,
    duration_ms int,
    created_at timestamptz not null default now()
);

-- Usage tracking
create table if not exists usage_events (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references organizations(id) on delete cascade,
    user_id uuid references users(id) on delete set null,
    provider text not null check (provider in ('openai', 'anthropic', 'deepgram_stt', 'deepgram_tts', 'telnyx', 'openweather', 'google')),
    event_type text not null,
    quantity numeric not null default 0,
    unit text not null,
    estimated_cost_usd numeric not null default 0,
    model text,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz not null default now()
);

-- CRM sync state
create table if not exists crm_sync_state (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid not null references organizations(id) on delete cascade,
    spreadsheet_id text not null,
    last_synced_at timestamptz,
    row_count int not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Indexes
create index if not exists idx_messages_conversation on messages(conversation_id, created_at);
create index if not exists idx_conversations_user on conversations(user_id, started_at desc);
create index if not exists idx_conversations_org on conversations(org_id);
create index if not exists idx_memories_user on memories(user_id, is_active, category);
create index if not exists idx_memories_org on memories(org_id);
create index if not exists idx_usage_events_org_date on usage_events(org_id, created_at);
create index if not exists idx_usage_events_provider on usage_events(provider, created_at);
create index if not exists idx_tool_executions_conv on tool_executions(conversation_id);
create index if not exists idx_call_logs_org on call_logs(org_id, started_at desc);

-- Row Level Security
alter table organizations enable row level security;
alter table users enable row level security;
alter table agents enable row level security;
alter table integrations enable row level security;
alter table conversations enable row level security;
alter table messages enable row level security;
alter table memories enable row level security;
alter table weekly_summaries enable row level security;
alter table phone_numbers enable row level security;
alter table call_logs enable row level security;
alter table tool_executions enable row level security;
alter table usage_events enable row level security;
alter table crm_sync_state enable row level security;

-- RLS policies: users see only their org's data
-- (service_role key bypasses RLS for backend operations)
create policy "Users see own org" on organizations
    for select using (id in (select org_id from users where id = auth.uid()));

create policy "Users see own profile" on users
    for all using (id = auth.uid());

create policy "Org members see agents" on agents
    for all using (org_id in (select org_id from users where id = auth.uid()));

create policy "Users see own integrations" on integrations
    for all using (user_id = auth.uid());

create policy "Org members see conversations" on conversations
    for all using (org_id in (select org_id from users where id = auth.uid()));

create policy "Org members see messages" on messages
    for all using (conversation_id in (
        select id from conversations where org_id in (
            select org_id from users where id = auth.uid()
        )
    ));

create policy "Org members see memories" on memories
    for all using (org_id in (select org_id from users where id = auth.uid()));

create policy "Org members see summaries" on weekly_summaries
    for all using (org_id in (select org_id from users where id = auth.uid()));

create policy "Org members see phone numbers" on phone_numbers
    for all using (org_id in (select org_id from users where id = auth.uid()));

create policy "Org members see call logs" on call_logs
    for all using (org_id in (select org_id from users where id = auth.uid()));

create policy "Org members see tool executions" on tool_executions
    for all using (org_id in (select org_id from users where id = auth.uid()));

create policy "Org members see usage" on usage_events
    for all using (org_id in (select org_id from users where id = auth.uid()));

create policy "Org members see crm sync" on crm_sync_state
    for all using (org_id in (select org_id from users where id = auth.uid()));

-- Updated_at trigger function
create or replace function update_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger tr_organizations_updated before update on organizations
    for each row execute function update_updated_at();
create trigger tr_users_updated before update on users
    for each row execute function update_updated_at();
create trigger tr_agents_updated before update on agents
    for each row execute function update_updated_at();
create trigger tr_integrations_updated before update on integrations
    for each row execute function update_updated_at();
create trigger tr_memories_updated before update on memories
    for each row execute function update_updated_at();
create trigger tr_crm_sync_updated before update on crm_sync_state
    for each row execute function update_updated_at();
