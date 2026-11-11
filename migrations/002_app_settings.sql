-- Runtime-editable settings. Env vars stay the fallback; a row here wins.
create table if not exists app_settings (
    key text primary key,
    value text,
    updated_at timestamptz not null default now()
);

alter table app_settings enable row level security;

-- Service-role only. The backend validates every write; no client writes directly.
create policy app_settings_service_role on app_settings
    for all using (auth.role() = 'service_role');
