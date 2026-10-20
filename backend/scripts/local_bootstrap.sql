-- Minimal stand-ins for Supabase-managed objects, ONLY for local development/CI.
create schema if not exists auth;
create table if not exists auth.users (id uuid primary key default gen_random_uuid(), email text);
create schema if not exists extensions;
do $$ begin
  if not exists (select from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
end $$;
alter database gamefy_dev set search_path = "$user", public, extensions;
