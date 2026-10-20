-- Gamefy — initial schema.
-- Security model: every table has RLS enabled and NO policies for anon/authenticated,
-- so the Supabase Data API can never read them. Only the backend (server-side DB role)
-- touches data, and it enforces authorization using the verified session user.

create extension if not exists vector with schema extensions;
create extension if not exists pgcrypto with schema extensions;

-- ---------------------------------------------------------------- profiles
create table if not exists public.profiles (
  id            uuid primary key references auth.users(id) on delete cascade,
  display_name  text check (display_name is null or char_length(display_name) <= 40),
  plan          text not null default 'free' check (plan in ('free', 'premium')),
  role          text not null default 'user' check (role in ('user', 'admin')),
  created_at    timestamptz not null default now()
);

create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id) values (new.id) on conflict do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- ------------------------------------------------------------------- games
-- Public identifiers are UUIDs + slugs (never sequential ints) to avoid enumeration.
create table if not exists public.games (
  id                  uuid primary key default gen_random_uuid(),
  slug                text not null unique check (slug ~ '^[a-z0-9-]{1,100}$'),
  title               text not null check (char_length(title) between 1 and 200),
  summary             text not null default '' check (char_length(summary) <= 600),
  description         text not null default '' check (char_length(description) <= 8000),
  developer           text,
  release_date        date,
  price_cents         integer check (price_cents is null or price_cents >= 0),
  currency            text not null default 'USD',
  platforms           text[] not null default '{}',
  genres              text[] not null default '{}',
  tags                text[] not null default '{}',
  features            text[] not null default '{}',   -- single-player, co-op, controller...
  avg_duration_hours  real check (avg_duration_hours is null or avg_duration_hours > 0),
  difficulty          smallint check (difficulty between 1 and 5),
  rating              smallint check (rating between 0 and 100),
  rating_count        integer not null default 0,
  cover_url           text,
  -- {"min": {gpu_tier,cpu_tier,ram_gb,vram_gb,storage_gb}, "rec": {...}}
  req                 jsonb not null default '{}'::jsonb,
  source              text not null default 'seed',
  search              tsvector,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

create or replace function public.games_search_update() returns trigger
language plpgsql as $$
begin
  new.search :=
    setweight(to_tsvector('simple', coalesce(new.title, '')), 'A') ||
    setweight(to_tsvector('simple', coalesce(array_to_string(new.genres, ' '), '') || ' ' ||
                                    coalesce(array_to_string(new.tags, ' '), '')), 'B') ||
    setweight(to_tsvector('simple', coalesce(new.summary, '') || ' ' || coalesce(new.developer, '')), 'C');
  new.updated_at := now();
  return new;
end $$;

drop trigger if exists games_search_trg on public.games;
create trigger games_search_trg before insert or update on public.games
  for each row execute function public.games_search_update();

create index if not exists games_search_idx   on public.games using gin (search);
create index if not exists games_genres_idx   on public.games using gin (genres);
create index if not exists games_tags_idx     on public.games using gin (tags);
create index if not exists games_platforms_idx on public.games using gin (platforms);
create index if not exists games_rating_idx   on public.games (rating desc nulls last);

-- -------------------------------------------------------------- embeddings
-- 768 dims = gemini-embedding-001 with outputDimensionality=768 (provider-swappable:
-- changing dimension requires a new column/migration + re-embedding, tracked by `model`).
create table if not exists public.game_embeddings (
  game_id    uuid primary key references public.games(id) on delete cascade,
  embedding  extensions.vector(768) not null,
  doc_hash   text not null,
  model      text not null,
  updated_at timestamptz not null default now()
);
create index if not exists game_embeddings_hnsw
  on public.game_embeddings using hnsw (embedding extensions.vector_cosine_ops);

-- ------------------------------------------------------------- user data
create table if not exists public.wishlist (
  user_id    uuid not null references public.profiles(id) on delete cascade,
  game_id    uuid not null references public.games(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, game_id)
);

create table if not exists public.library (
  user_id          uuid not null references public.profiles(id) on delete cascade,
  game_id          uuid not null references public.games(id) on delete cascade,
  status           text not null default 'owned' check (status in ('owned', 'playing', 'completed', 'dropped')),
  playtime_minutes integer not null default 0 check (playtime_minutes between 0 and 600000),
  created_at       timestamptz not null default now(),
  primary key (user_id, game_id)
);

create table if not exists public.ratings (
  user_id    uuid not null references public.profiles(id) on delete cascade,
  game_id    uuid not null references public.games(id) on delete cascade,
  score      smallint not null check (score between 1 and 10),
  review     text check (review is null or char_length(review) <= 2000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (user_id, game_id)
);

create table if not exists public.user_events (
  id         bigint generated always as identity primary key,
  user_id    uuid not null references public.profiles(id) on delete cascade,
  game_id    uuid references public.games(id) on delete cascade,
  type       text not null check (type in ('view', 'ignore', 'search')),
  query      text check (query is null or char_length(query) <= 200),
  created_at timestamptz not null default now()
);
create index if not exists user_events_user_idx on public.user_events (user_id, created_at desc);

create table if not exists public.preference_profiles (
  user_id    uuid primary key references public.profiles(id) on delete cascade,
  weights    jsonb not null default '{}'::jsonb,   -- {"genre:rpg": 0.92, ...} in [-1, 1]
  explicit   jsonb not null default '{}'::jsonb,   -- user-declared likes/dislikes
  updated_at timestamptz not null default now()
);

create table if not exists public.hardware_profiles (
  user_id    uuid primary key references public.profiles(id) on delete cascade,
  cpu        text check (cpu is null or char_length(cpu) <= 80),
  gpu        text check (gpu is null or char_length(gpu) <= 80),
  cpu_tier   smallint,
  gpu_tier   smallint,
  ram_gb     smallint check (ram_gb between 1 and 1024),
  vram_gb    smallint check (vram_gb between 0 and 256),
  storage_gb integer check (storage_gb between 0 and 100000),
  os         text check (os is null or os in ('windows', 'linux', 'macos')),
  updated_at timestamptz not null default now()
);

-- ------------------------------------------------- cost + security telemetry
create table if not exists public.usage_log (
  id              bigint generated always as identity primary key,
  user_id         uuid references public.profiles(id) on delete set null,
  kind            text not null,            -- embed_query, smart_search, chat, ...
  endpoint        text,
  provider        text,
  model           text,
  tokens_in       integer not null default 0,
  tokens_out      integer not null default 0,
  cost_micro_usd  integer not null default 0,
  cached          boolean not null default false,
  created_at      timestamptz not null default now()
);
create index if not exists usage_log_user_idx on public.usage_log (user_id, created_at desc);

create table if not exists public.audit_log (
  id         bigint generated always as identity primary key,
  user_id    uuid,
  action     text not null,
  ip_hash    text,
  meta       jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists audit_log_action_idx on public.audit_log (action, created_at desc);

-- "How much does each user cost us?"
create or replace view public.user_cost_daily as
  select user_id, date_trunc('day', created_at) as day,
         sum(cost_micro_usd) / 1e6 as cost_usd,
         sum(tokens_in) as tokens_in, sum(tokens_out) as tokens_out,
         count(*) as calls, count(*) filter (where cached) as cache_hits
  from public.usage_log group by 1, 2;

-- ------------------------------------------------------------------- RLS
alter table public.profiles            enable row level security;
alter table public.games               enable row level security;
alter table public.game_embeddings     enable row level security;
alter table public.wishlist            enable row level security;
alter table public.library             enable row level security;
alter table public.ratings             enable row level security;
alter table public.user_events         enable row level security;
alter table public.preference_profiles enable row level security;
alter table public.hardware_profiles   enable row level security;
alter table public.usage_log           enable row level security;
alter table public.audit_log           enable row level security;

revoke all on all tables in schema public from anon, authenticated;
alter view public.user_cost_daily set (security_invoker = true);
