-- Store links + external ids. Prices are per store; games.price_cents becomes the cached
-- "best current price" (min over store_links) so existing filters/sorting keep working.
alter table public.games
  add column if not exists igdb_id    bigint unique,
  add column if not exists steam_appid integer;
create index if not exists games_steam_appid_idx on public.games (steam_appid);

create table if not exists public.store_links (
  game_id           uuid not null references public.games(id) on delete cascade,
  store             text not null check (store ~ '^[a-z0-9-]{1,40}$'),
  source            text not null check (source in ('igdb', 'steam', 'cheapshark')),
  url               text not null check (url ~ '^https://' and char_length(url) <= 500),
  price_cents       integer check (price_cents is null or price_cents >= 0),
  normal_price_cents integer check (normal_price_cents is null or normal_price_cents >= 0),
  currency          text not null default 'USD',
  external_id       text,
  updated_at        timestamptz not null default now(),
  primary key (game_id, store, source)
);
create index if not exists store_links_game_idx on public.store_links (game_id);

alter table public.store_links enable row level security;
revoke all on public.store_links from anon, authenticated;
