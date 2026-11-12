-- Files attached to a conversation. Bytes live on disk; this is the index.
create table if not exists documents (
    id uuid primary key default uuid_generate_v4(),
    org_id uuid references organizations(id) on delete cascade,
    conversation_id uuid references conversations(id) on delete cascade,
    filename text not null,
    content_type text,
    size_bytes bigint not null default 0,
    -- 'table' goes to the pandas sandbox, 'text' is extracted into context.
    kind text not null default 'text' check (kind in ('table', 'text')),
    storage_path text not null,
    summary text,
    created_at timestamptz not null default now()
);

create index if not exists documents_conversation_idx on documents(conversation_id);

alter table documents enable row level security;

create policy documents_service_role on documents
    for all using (auth.role() = 'service_role');
