-- ─────────────────────────────────────────────────────────────────────
--  Transfer ownership from one account to another.
--
--  WHY THIS EXISTS, AND WHY ORDER MATTERS
--
--  public.users.id references auth.users(id) ON DELETE CASCADE, and five
--  tables reference public.users(id) the same way. So deleting the old
--  account in the Supabase dashboard *first* would silently take the
--  Google integration, every conversation, every memory and the weekly
--  summaries with it. There is no warning and no undo.
--
--  This moves everything across while both accounts still exist. Only
--  after it reports zero rows left behind is the old account safe to
--  delete.
--
--  Edit the two emails below, then run the whole file in the Supabase
--  SQL editor. Safe to run more than once.
-- ─────────────────────────────────────────────────────────────────────

do $$
declare
    from_email text := 'admin@kaia.local';
    to_email   text := 'tanishqd423@gmail.com';
    old_id uuid;
    new_id uuid;
    the_org uuid;
    moved int;
begin
    select id into old_id from auth.users where lower(email) = lower(from_email);
    select id into new_id from auth.users where lower(email) = lower(to_email);

    if old_id is null then
        raise exception 'No account for %. Nothing changed.', from_email;
    end if;
    if new_id is null then
        raise exception 'No account for %. Sign up with it first, then re-run.', to_email;
    end if;
    if old_id = new_id then
        raise exception 'Those are the same account.';
    end if;

    select org_id into the_org from public.users where id = old_id;
    if the_org is null then
        -- Already transferred, or the old row is gone. Fall back to any org.
        select org_id into the_org from public.users where org_id is not null limit 1;
    end if;
    if the_org is null then
        raise exception 'No organisation found to transfer.';
    end if;

    -- The new owner must exist in the same organisation. Passing the owner
    -- check is not enough on its own: chat refuses a user with no org.
    insert into public.users (id, org_id, email, role)
    values (new_id, the_org, to_email, 'admin')
    on conflict (id) do update
        set org_id = excluded.org_id,
            role   = 'admin';

    -- Move the data across before anything can cascade.
    update public.integrations     set user_id = new_id where user_id = old_id;
    get diagnostics moved = row_count;  raise notice 'integrations:     %', moved;

    update public.conversations    set user_id = new_id where user_id = old_id;
    get diagnostics moved = row_count;  raise notice 'conversations:    %', moved;

    update public.memories         set user_id = new_id where user_id = old_id;
    get diagnostics moved = row_count;  raise notice 'memories:         %', moved;

    update public.weekly_summaries set user_id = new_id where user_id = old_id;
    get diagnostics moved = row_count;  raise notice 'weekly_summaries: %', moved;

    update public.usage_events     set user_id = new_id where user_id = old_id;
    get diagnostics moved = row_count;  raise notice 'usage_events:     %', moved;

    raise notice 'Transferred % -> %', from_email, to_email;
end $$;


-- ── Verify before deleting anything ──────────────────────────────────
-- Every count below must be 0. If any is not, do NOT delete the old
-- account: something still points at it and would be destroyed.

select 'integrations'     as table_name, count(*) as still_on_old_owner
from public.integrations     i join auth.users u on u.id = i.user_id
where lower(u.email) = 'admin@kaia.local'
union all
select 'conversations', count(*)
from public.conversations    c join auth.users u on u.id = c.user_id
where lower(u.email) = 'admin@kaia.local'
union all
select 'memories', count(*)
from public.memories         m join auth.users u on u.id = m.user_id
where lower(u.email) = 'admin@kaia.local'
union all
select 'weekly_summaries', count(*)
from public.weekly_summaries w join auth.users u on u.id = w.user_id
where lower(u.email) = 'admin@kaia.local'
union all
select 'usage_events', count(*)
from public.usage_events     e join auth.users u on u.id = e.user_id
where lower(u.email) = 'admin@kaia.local';
