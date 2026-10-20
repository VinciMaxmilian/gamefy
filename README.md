# ✦ Gamefy — game discovery, powered by understanding (not by an LLM for everything)

> *Don't search for a game. Say what you want to play.*

A store/catalog with wishlist, library, ratings and a recommendation engine. Most intelligence is
**deterministic and cheap** (SQL, full-text search, a behaviour-based taste profile, pgvector
embeddings, a configurable ranker, rule-based hardware checks). A generative LLM is an optional,
tightly sandboxed layer — **not enabled in this MVP**, by design.

```
Browser ──► Netlify (React SPA)  ──/api/*  proxy──►  Vercel (FastAPI)  ──►  Supabase Postgres + pgvector
                                                          │  └─► Supabase Auth (GoTrue)
                                                          ├─► Upstash Redis (rate limits, cache)  [optional]
                                                          └─► Gemini (embeddings only, behind AIProvider)
```

## What's in the MVP

| Area | Status |
|---|---|
| Auth (signup/login/logout/refresh/recover/reset), HttpOnly cookies, CSRF, brute-force limits | ✅ |
| Catalog, FTS search, filters, sorting, game page, similar games (pgvector) | ✅ |
| Wishlist, library (status/playtime), ratings/reviews, profile | ✅ |
| **Level 1** taste profile from behaviour (+ explicit prefs), time-decayed | ✅ |
| **Level 2** semantic search (`/search/smart`): rule-based intent parser (PT/EN) + embeddings | ✅ |
| Configurable ranking (`Score = Σ wᵢ·componentᵢ`) with explainable reasons | ✅ |
| Hardware compatibility (deterministic tiers) | ✅ |
| Real catalog sync + "where to buy" store links and per-store prices | ✅ |
| Plans (visitor/free/premium/admin), per-plan quotas, rate limiting, cost telemetry | ✅ |
| Chat / comparison / curation by LLM (Premium) | ⏳ next phase (see `docs/AI_SECURITY.md`) |
| Payments | ⏳ plan is set server-side in `profiles.plan` (no client path to change it) |

## Repo layout

```
supabase/migrations/0001_init.sql   schema, FTS, pgvector, RLS deny-by-default
backend/                            FastAPI (Vercel serverless)
  app/security/                     auth, csrf+headers middleware, rate limit, sanitize, passwords, audit
  app/reco/                         profile · engine · hardware · intent  (pure, unit-tested)
  app/ai/                           AIProvider interface · Gemini · offline hash fallback · semantic doc
  app/services/ app/routers/        catalog · recommend · embeddings · HTTP layer
  scripts/seed*.py                  sample catalog + embedding builder (idempotent)
frontend/                           React + TS + Vite + Tailwind v4, shadcn-style components
  src/design/tokens.css             ← the whole visual language (Apple-inspired). Swap it to re-theme.
netlify.toml                        build, /api proxy, security headers + CSP
```

## Run locally

```bash
# 1. Database (any Postgres 15+ with pgvector; Supabase CLI or local)
psql -f backend/scripts/local_bootstrap.sql   # ONLY for a plain local PG: stubs auth schema/roles
psql -f supabase/migrations/0001_init.sql
psql -f supabase/migrations/0002_store_links.sql

# 2. Backend
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
cp .env.example .env            # fill in; never commit
python -m scripts.seed          # sample games + embeddings (uses GEMINI_API_KEY if set, else offline embedder)
uvicorn app.main:app --reload   # :8000
pytest                          # 59 tests (security, reco, API integration)

# 3. Frontend (Vite proxies /api → :8000, so cookies are same-origin like in production)
cd frontend && npm i && npm run dev   # :5173
```

## Deploy

All environment variables, per platform, are listed in [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md).

1. **Supabase** — run `supabase/migrations/0001_init.sql` then `0002_store_links.sql` in the SQL editor (or `supabase db push`).
   Auth → URL Configuration: set *Site URL* to your Netlify URL and add `https://<site>/reset-password` to *Redirect URLs*.
   Enable email confirmation if you want it (the API works either way).
2. **Vercel** (backend) — project root `backend/`. Set the env vars from `backend/.env.example`
   (`ENVIRONMENT=production`, `COOKIE_SECURE=true`, `CORS_ORIGINS=https://<your-site>.netlify.app`).
   Use Supabase's **transaction pooler** string (port 6543) for `DATABASE_URL`: Vercel has no IPv6 egress, and
   the direct `db.<ref>.supabase.co` host is IPv6-only.
3. **Seed** — run `python -m scripts.seed` once with `DATABASE_URL` + `GEMINI_API_KEY` pointing at production.
4. **Netlify** (frontend) — edit the `to =` host in `netlify.toml` to your Vercel URL, connect the repo. No frontend secrets are needed
   (the browser never talks to Supabase directly).
5. *(Recommended)* create a free Upstash Redis and set `UPSTASH_REDIS_REST_URL/TOKEN` — without it rate limits are per serverless instance (approximate).
6. Give a user Premium: `update profiles set plan = 'premium' where id = '<uuid>';`

## Catalog sync (IGDB + Steam + CheapShark)

The demo catalog is replaced by real data through offline jobs (`backend/scripts/sync.py`, scheduled by
`.github/workflows/catalog-sync.yml` — not by Vercel, whose function time limits are too short for rate-limited APIs).

| Job | Source | Writes |
|---|---|---|
| `igdb` | IGDB (Twitch OAuth, Apicalypse) | games, genres/tags/modes/platforms, ratings, art, **store links** (Steam/Epic/GOG… from IGDB `websites`), `steam_appid`; then (re)builds embeddings |
| `steam` / `steam-changed` | Steam `appdetails` (+ official `IStoreService/GetAppList` to find apps changed since X) | PC requirements → deterministic tiers, price, art |
| `prices` | CheapShark (`/games?steamAppID=` → `/games?id=` deals) | per-store prices with CheapShark redirect links |

```bash
cd backend && export DATABASE_URL=… IGDB_CLIENT_ID=… IGDB_CLIENT_SECRET=… GEMINI_API_KEY=…
psql "$DATABASE_URL" -f ../supabase/migrations/0002_store_links.sql
python -m scripts.sync igdb --pages 3 --min-ratings 100   # ≈300 well-known games
python -m scripts.sync steam --limit 300                  # requirements + Steam price
python -m scripts.sync prices --limit 300                 # cross-store prices
python -m scripts.sync purge-seed                         # remove the demo catalog
```

Safety: base URLs are hard-coded (no SSRF); redirects are not followed; responses are size-capped; all imported text is sanitised and
injection-scanned; **only https links on an allow-listed set of store domains** are stored or served (`ingest/allowlist.py`, re-checked on
output); adult-themed IGDB entries are skipped. The web request path never calls these APIs — it only reads the database.

> **Check each provider's terms before launch.** IGDB's free tier is for non-commercial use and has attribution requirements; Steam
> `appdetails` is an unofficial endpoint (rate limit ≈200 req/5 min, so the job throttles to 1 req/1.6 s); CheapShark asks for a
> descriptive User-Agent and referral links via its redirect. Cover art belongs to the publishers — the UI hot-links it from the
> providers' CDNs and credits the sources in the footer.

## Security model (short version)

* **Backend is the only data path.** Every table has RLS enabled with *no* policies and grants revoked from `anon/authenticated`, so the public Supabase Data API sees nothing. The browser never receives a Supabase key.
* **Identity comes from the verified session**, never from request bodies/params. Plan and role are read from the DB per request, not from the token.
* Tokens live in `HttpOnly; Secure; SameSite=Lax` cookies; unsafe methods need an allow-listed `Origin` **and** a double-submit CSRF token. JWT verification pins the algorithm (HS256 secret or JWKS), requires `aud`/`exp`, rejects `none`.
* Account-enumeration safe (signup/recover/login responses are uniform); per-IP and per-account throttles; audit log stores hashed IPs only.
* All inputs are validated by strict Pydantic models (`extra="forbid"`, regex-constrained tokens, length caps); SQL goes through SQLAlchemy bound parameters; the FTS query is rebuilt from `\w` tokens only.
* Body-size cap (streamed, not just `Content-Length`), security headers, no docs/OpenAPI in production, no stack traces to clients, restrictive CORS.
* Untrusted text (reviews, descriptions, tags, queries) is sanitised, scanned for injection patterns and — when an LLM is added — only ever inserted as delimited, flagged **data** (`security/sanitize.py:wrap_untrusted`).

Full AI threat model and the planned tool-calling design: [`docs/AI_SECURITY.md`](docs/AI_SECURITY.md).

## Cost control

No LLM is called today. Embeddings: documents once (hash-gated, idempotent), queries cached 24h. Every AI-adjacent call is written to
`usage_log` (tokens, micro-USD, cache hit) — `select * from user_cost_daily` answers *"what does each user cost?"*. Quotas per plan
(`PLAN_LIMITS`, JSON env), ranking weights (`RECO_WEIGHTS`) and profile half-life are config, not code.

## ⚠️ Secrets

Never commit `.env`. If any real keys were ever pasted into chats, tickets or commits, **rotate them** in Supabase (DB password,
secret key, JWT secret) and Google AI Studio before going live.
