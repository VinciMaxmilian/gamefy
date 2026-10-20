# Variáveis de ambiente

> Nunca coloque valores reais em arquivos do repositório nem em chats. Rotacione qualquer chave que já tenha sido exposta.

Seu projeto Supabase: **ref** `ywphrlusrmnlygqjmxjm` → `SUPABASE_URL = https://ywphrlusrmnlygqjmxjm.supabase.co`.
Site: `https://gamefyapp.netlify.app` · API: `https://gamefy-backend.vercel.app`.

## 1) Vercel — projeto `gamefy-backend` (Settings → Environment Variables → Production)

| Variável | Valor | Obrigatória |
|---|---|---|
| `ENVIRONMENT` | `production` | sim (desliga `/docs`, liga HSTS) |
| `DATABASE_URL` | Supabase → **Connect → Transaction pooler** (porta **6543**), formato `postgresql://postgres.ywphrlusrmnlygqjmxjm:SENHA@aws-0-REGIAO.pooler.supabase.com:6543/postgres`. Senha com `* @ # / ? :` precisa estar codificada (`*`→`%2A`, `@`→`%40`, `#`→`%23`). **Não** use `db.<ref>.supabase.co` (IPv6; a Vercel não alcança) nem `[colchetes]` | sim |
| `SUPABASE_URL` | `https://ywphrlusrmnlygqjmxjm.supabase.co` | sim |
| `SUPABASE_PUBLISHABLE_KEY` | a chave `sb_publishable_…` | sim |
| `SUPABASE_SECRET_KEY` | a chave `sb_secret_…` (só servidor; usada para apagar conta) | sim |
| `SUPABASE_JWT_SECRET` | Supabase → Settings → **JWT Keys** → *Legacy JWT Secret*. Só se o projeto ainda assina com HS256. Se você já usa chaves assimétricas (ES256), deixe vazio. Se ficar vazio num projeto HS256, funciona, mas valida cada token com uma chamada ao Supabase (cache de 60 s) | recomendada se HS256 |
| `CORS_ORIGINS` | `https://gamefyapp.netlify.app` (o **primeiro** da lista também é usado no link do e-mail de recuperar senha) | sim |
| `COOKIE_SECURE` | `true` | sim |
| `GEMINI_API_KEY` | chave do Google AI Studio | recomendada (sem ela usa embeddings locais, bem piores) |
| `GEMINI_EMBED_MODEL` | `gemini-embedding-001` | não (já é o padrão) |
| `EMBED_DIM` | `768` (**não mude**: o banco é `vector(768)`) | não |
| `TRUSTED_IP_HEADER` | `x-nf-client-connection-ip` (padrão). Ver "Verificar o IP do cliente" abaixo | não |
| `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` | do console do Upstash (Redis gratuito → REST API) | recomendadas: sem elas os limites de uso valem por instância e o cache de buscas é perdido |
| `PLAN_LIMITS` | JSON, só para sobrescrever cotas. Ex.: `{"free":{"requests_per_minute":120,"smart_search_per_day":10,"ai_chat_per_day":0,"ai_tokens_per_day":0}}` — o mapa inteiro de planos é substituído, então inclua `visitor`, `free`, `premium`, `admin` | não |
| `RECO_WEIGHTS` | JSON, pesos do ranking. Ex.: `{"semantic_similarity":0.4,"rating":0.05}` (os demais mantêm o padrão) | não |
| `PROFILE_HALF_LIFE_DAYS`, `MAX_BODY_BYTES`, `AI_*`, `EMBED_COST_PER_MTOK_USD`, `GEMINI_CHAT_MODEL` | ajustes finos / chat (ainda desligado) | não |

**Não precisa:** as chaves legadas `anon` e `service_role` (eyJ…) — o código não as usa. As variáveis do IGDB/Steam **não** vão na Vercel (jobs rodam fora).

Depois de salvar as variáveis, faça **Redeploy** (elas só valem em deploys novos).

## 2) Netlify — site `gamefyapp`

**Nenhuma variável.** O navegador nunca fala com o Supabase; tudo passa por `/api/*` → Vercel (regra em `netlify.toml`).

## 3) GitHub → Settings → Secrets and variables → Actions (jobs de catálogo)

| Secret | Valor |
|---|---|
| `DATABASE_URL` | o mesmo do pooler acima |
| `IGDB_CLIENT_ID`, `IGDB_CLIENT_SECRET` | dev.twitch.tv → Applications → Manage (Client Credentials) |
| `GEMINI_API_KEY` | a mesma chave |
| `STEAM_WEB_API_KEY` | opcional: https://steamcommunity.com/dev/apikey |
| `STORE_COUNTRY` (variável, não secret) | `us` (região do preço da Steam; ex. `br`) |

## 4) Rodando na sua máquina (`backend/.env`, nunca commitado)

Copie `backend/.env.example`; com `ENVIRONMENT=development`, `COOKIE_SECURE=false`, `CORS_ORIGINS=http://localhost:5173`, e `DATABASE_URL` do pooler (ou um Postgres local).

## 5) Configurações do Supabase que **não** são variáveis (painel)

* **Authentication → URL Configuration**
  * *Site URL*: `https://gamefyapp.netlify.app`
  * *Redirect URLs*: `https://gamefyapp.netlify.app/reset-password` (e `http://localhost:5173/reset-password` para testar)
  * Sem isso o e-mail de "esqueci a senha" não leva à página certa.
* **Authentication → Providers → Email**: decida se exige confirmação de e-mail (a API funciona nos dois casos).
* **Authentication → Emails → Templates → Reset Password**: o link padrão (`{{ .ConfirmationURL }}`) funciona; ele chega em `/reset-password#access_token=…`.
* **SQL Editor**: rode `supabase/setup.sql` uma vez.

## IP do cliente atrás do Netlify (verificado)

Testado em produção: pelo Netlify o backend recebe `x-nf-client-connection-ip` com o **IP real do visitante**, e o Netlify
**sobrescreve** valores forjados pelo cliente. Então o padrão (`TRUSTED_IP_HEADER=x-nf-client-connection-ip`) está certo e cada usuário
tem seu próprio limite.

Limitação conhecida: quem chamar a Vercel **diretamente** (`gamefy-backend.vercel.app`, sem passar pelo Netlify) consegue forjar esse
cabeçalho e escapar dos limites **por IP**. Os limites por conta (tentativas de login por e-mail, quotas e limites por usuário
logado) continuam valendo. Se quiser fechar isso: valide um segredo compartilhado enviado pelo proxy (ex.: Netlify Edge Function
adicionando um cabeçalho com um segredo guardado em variável de ambiente).

Para conferir: `curl -s https://gamefyapp.netlify.app/api/health/ip` deve mostrar `"source":"x-nf-client-connection-ip"`.
(O `ip_hash` é um hash; não compare com chamadas diretas à Vercel: elas enxergam outro cabeçalho.)

## Diagnóstico rápido

* `GET /api/health` → `{"ok":true}` (função no ar)
* `GET /api/health/ready` → `{"ok":true,"db":true}` (banco e tabelas OK)
* `GET /api/games?limit=1` → `total: 0` = banco sem jogos (rode `python -m scripts.seed` ou os jobs `sync`)
