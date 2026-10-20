# AI security architecture

**Assumption:** the LLM is an *untrusted, unprivileged component*, and every string it sees that did not come from our
own code (user messages, reviews, game descriptions, tags, imported metadata, RAG hits, tool results) is *hostile data*.

## What exists today (MVP)

| Control | Where |
|---|---|
| No generative model is invoked anywhere; semantic search uses embeddings + a rule-based parser | `reco/intent.py`, `routers/reco.py` |
| Sanitisation (NFKC, control/zero-width/bidi stripping, markup removal, length caps) | `security/sanitize.py:clean_text` |
| Injection heuristics → drop from semantic docs, flag, audit | `looks_like_injection`, `ai/semantic_doc.py`, `routers/reco.py` |
| Provider abstraction (swap Gemini/OpenAI/Anthropic/local) | `ai/provider.py` |
| Cost telemetry per user/endpoint, cache hit tracking | `services/embeddings.py`, `usage_log`, `user_cost_daily` |
| Quotas + rate limits by plan/user/IP, configurable | `config.py:PlanLimits`, `security/ratelimit.py` |
| Embedding-provider failure → clean 503, client falls back to classic search | `routers/reco.py` |

Tests that pin this behaviour: `tests/test_security.py` (injection corpus, wrapper cannot be closed by content, malicious
description dropped from the document) and `tests/test_api.py::test_injection_text_in_query_is_just_data`.

## Design for the Premium chat (next phase)

```
user msg ─► size/rate/quota gate ─► sanitize ─► LLM  (system prompt = our code only)
                                                  │ tool request (JSON)
                                                  ▼
                          backend: allow-list ─► strict schema (Pydantic, extra=forbid)
                                   ─► authz with *session* user (LLM-supplied user_id is ignored/absent)
                                   ─► execute bounded query (limits, timeouts) ─► sanitise result
                                                  │ result wrapped as <<untrusted_data>>
                                                  ▼
                                                 LLM ─► answer (facts re-hydrated from DB, not from model text)
```

Rules the implementation must keep:

1. **No ambient authority.** The model gets no DB/Redis/FS/shell/secrets access. Tools are an explicit allow-list
   (`search_games`, `get_game`, `compare_games`, `get_my_taste`, `get_my_wishlist`…), each with a rigid schema. Unknown tool or
   extra argument ⇒ rejected and logged.
2. **Identity is never an argument.** Tools take no `user_id`; the executor injects the authenticated principal.
3. **Instructions vs data.** System prompt is static code. Everything else is passed in delimited data blocks
   (`wrap_untrusted`) that the system prompt declares non-authoritative. Content cannot close a block (delimiters are neutralised).
4. **The model interprets; the backend decides.** The LLM outputs a `ParsedQuery`-shaped JSON (same structure the rule-based parser emits);
   the backend validates it and runs the search. Prices, requirements, durations, availability and compatibility come from the DB / rule
   engine and are re-attached after generation — the model may only *explain* them.
5. **No leakage.** Prompts, keys, schema and internal tool names are never echoed; a refusal template handles "show your system prompt".
   Output is post-filtered for secret-shaped strings.
6. **Cost guard rails.** `ai_max_message_chars`, `ai_max_context_chars`, `ai_timeout_seconds`, per-plan daily interactions and
   tokens (`PlanLimits`), per-user concurrency cap, response cache + request dedupe, circuit breaker on provider errors with
   fallback to the deterministic path.
7. **RAG hygiene.** Ingestion: sanitise → injection-scan → chunk → embed; flagged chunks are quarantined. Retrieval results are
   filtered and wrapped as data. Nothing retrieved can grant tools or change policy.
8. **Observability.** Every call logs user, endpoint, model, tokens in/out, cost, cache hit, outcome; alerts on spend spikes,
   quota-exhaustion bursts and flagged-injection rate.
