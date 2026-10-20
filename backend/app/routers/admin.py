from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..security.auth import admin_user

# Every route here requires the admin role, checked server-side from the database (never from the client).
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(admin_user)])


def _usd(micro) -> float:
    return round((micro or 0) / 1e6, 6)


@router.get("/overview")
async def overview(days: Annotated[int, Query(ge=1, le=90)] = 7, session: AsyncSession = Depends(get_session)) -> dict:
    """Answers "what does each user cost?", cache effectiveness and abuse signals for the last N days."""
    q = lambda sql: session.execute(text(sql), {"days": days})  # noqa: E731
    users, premium, games, links = (await session.execute(text(
        "select (select count(*) from profiles), (select count(*) from profiles where plan = 'premium'),"
        " (select count(*) from games), (select count(*) from store_links)"))).one()
    total = (await q("select count(*), coalesce(sum(cached::int), 0), coalesce(sum(cost_micro_usd), 0), coalesce(sum(tokens_in + tokens_out), 0)"
                     " from usage_log where created_at >= now() - make_interval(days => :days)")).one()
    by_endpoint = (await q("select kind, coalesce(endpoint, ''), count(*), coalesce(sum(cached::int), 0), coalesce(sum(tokens_in + tokens_out), 0),"
                           " coalesce(sum(cost_micro_usd), 0) from usage_log where created_at >= now() - make_interval(days => :days)"
                           " group by 1, 2 order by 3 desc limit 30")).all()
    per_user = (await q("select coalesce(u.email, '(deleted)'), count(*), coalesce(sum(l.cached::int), 0), coalesce(sum(l.cost_micro_usd), 0)"
                        " from usage_log l left join auth.users u on u.id = l.user_id"
                        " where l.created_at >= now() - make_interval(days => :days)"
                        " group by 1 order by 4 desc, 2 desc limit 25")).all()
    daily = (await q("select date_trunc('day', created_at)::date, count(*), coalesce(sum(cost_micro_usd), 0) from usage_log"
                     " where created_at >= now() - make_interval(days => :days) group by 1 order by 1")).all()
    security = (await q("select action, count(*) from audit_log where created_at >= now() - make_interval(days => :days)"
                        " group by 1 order by 2 desc limit 30")).all()
    calls, hits, cost, tokens = total
    return {
        "days": days,
        "totals": {"users": users, "premium_users": premium, "games": games, "store_links": links},
        "usage": {"calls": calls, "cache_hits": int(hits), "cache_hit_rate": round(hits / calls, 3) if calls else None,
                  "cost_usd": _usd(cost), "tokens": int(tokens)},
        "by_endpoint": [{"kind": k, "endpoint": e, "calls": c, "cache_hits": int(h), "tokens": int(t), "cost_usd": _usd(m)} for k, e, c, h, t, m in by_endpoint],
        "per_user": [{"email": e, "calls": c, "cache_hits": int(h), "cost_usd": _usd(m)} for e, c, h, m in per_user],
        "daily": [{"day": d.isoformat(), "calls": c, "cost_usd": _usd(m)} for d, c, m in daily],
        "security_events": [{"action": a, "count": n} for a, n in security],
    }
