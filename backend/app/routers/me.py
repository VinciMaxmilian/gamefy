import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_session
from ..kv import get_kv
from ..models import Game, HardwareProfile, Library, PreferenceProfile, Profile, Rating, UserEvent, UsageLog, Wishlist
from ..reco.hardware import cpu_tier, gpu_tier
from ..reco.profile import top_features
from ..schemas import EventIn, ExplicitPrefsIn, GameCard, HardwareIn, LibraryIn, RatingIn, Slug
from ..security.audit import audit
from ..security.auth import Principal, clear_auth_cookies, current_user
from ..security.sanitize import clean_text, looks_like_injection
from ..services import catalog, recommend
from ..routers.auth import _gotrue

router = APIRouter(prefix="/me", tags=["me"])


async def _game(session: AsyncSession, slug: str) -> Game:
    g = (await session.execute(select(Game).where(Game.slug == slug))).scalar_one_or_none()
    if not g:
        raise HTTPException(404, "Game not found")
    return g


@router.get("")
async def me(principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    s = get_settings()
    limits = s.limits_for(principal.limits_key)
    day = time.strftime("%Y%m%d", time.gmtime())
    used = int(await get_kv().get(f"quota:smart:{principal.user_id}:{day}") or 0)
    profile = await session.get(Profile, principal.user_id)
    return {
        "email": principal.email, "display_name": profile.display_name if profile else None,
        "plan": principal.plan, "role": principal.role,
        "limits": {"smart_search_per_day": limits.smart_search_per_day, "ai_chat_per_day": limits.ai_chat_per_day},
        "usage": {"smart_search_today": used},
    }


# ---------------------------------------------------------------- wishlist
@router.get("/wishlist", response_model=list[GameCard])
async def wishlist(principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Game).join(Wishlist, Wishlist.game_id == Game.id)
                                  .where(Wishlist.user_id == principal.user_id).order_by(Wishlist.created_at.desc()))).scalars()
    return [catalog.to_card(g) for g in rows]


@router.put("/wishlist/{slug}", status_code=204)
async def wishlist_add(slug: Slug, principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)):
    g = await _game(session, slug)
    count = (await session.execute(select(func.count()).select_from(Wishlist).where(Wishlist.user_id == principal.user_id))).scalar_one()
    if count >= 500:
        raise HTTPException(422, "Wishlist limit reached")
    await session.execute(insert(Wishlist).values(user_id=principal.user_id, game_id=g.id).on_conflict_do_nothing())
    await session.commit()
    return Response(status_code=204)


@router.delete("/wishlist/{slug}", status_code=204)
async def wishlist_remove(slug: Slug, principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)):
    g = await _game(session, slug)
    await session.execute(delete(Wishlist).where(Wishlist.user_id == principal.user_id, Wishlist.game_id == g.id))
    await session.commit()
    return Response(status_code=204)


# ----------------------------------------------------------------- library
@router.get("/library")
async def library(principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (await session.execute(select(Library, Game).join(Game, Game.id == Library.game_id)
                                  .where(Library.user_id == principal.user_id).order_by(Library.created_at.desc()))).all()
    return [{"game": catalog.to_card(g).model_dump(mode="json"), "status": lib.status, "playtime_minutes": lib.playtime_minutes}
            for lib, g in rows]


@router.put("/library/{slug}", status_code=204)
async def library_put(slug: Slug, body: LibraryIn, principal: Principal = Depends(current_user),
                      session: AsyncSession = Depends(get_session)):
    g = await _game(session, slug)
    stmt = insert(Library).values(user_id=principal.user_id, game_id=g.id, status=body.status, playtime_minutes=body.playtime_minutes)
    await session.execute(stmt.on_conflict_do_update(index_elements=["user_id", "game_id"],
                                                     set_={"status": body.status, "playtime_minutes": body.playtime_minutes}))
    await session.execute(delete(Wishlist).where(Wishlist.user_id == principal.user_id, Wishlist.game_id == g.id))
    await session.commit()
    return Response(status_code=204)


@router.delete("/library/{slug}", status_code=204)
async def library_remove(slug: Slug, principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)):
    g = await _game(session, slug)
    await session.execute(delete(Library).where(Library.user_id == principal.user_id, Library.game_id == g.id))
    await session.commit()
    return Response(status_code=204)


# ----------------------------------------------------------------- ratings
@router.put("/ratings/{slug}", status_code=204)
async def rate(slug: Slug, body: RatingIn, request: Request, principal: Principal = Depends(current_user),
               session: AsyncSession = Depends(get_session)):
    g = await _game(session, slug)
    review = clean_text(body.review, 2000) if body.review else None   # stored sanitised; still treated as untrusted data everywhere
    if review and looks_like_injection(review):
        await audit(session, request, "review_flagged", user_id=principal.user_id, game=slug)
    stmt = insert(Rating).values(user_id=principal.user_id, game_id=g.id, score=body.score, review=review)
    await session.execute(stmt.on_conflict_do_update(index_elements=["user_id", "game_id"],
                                                     set_={"score": body.score, "review": review, "updated_at": func.now()}))
    await session.commit()
    return Response(status_code=204)


@router.get("/ratings")
async def my_ratings(principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.execute(select(Game.slug, Rating.score).join(Rating, Rating.game_id == Game.id)
                                  .where(Rating.user_id == principal.user_id))).all()
    return {slug: score for slug, score in rows}


# ------------------------------------------------------------------ events
@router.post("/events", status_code=204)
async def event(body: EventIn, principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)):
    g = await _game(session, body.slug)
    session.add(UserEvent(user_id=principal.user_id, game_id=g.id, type=body.type))
    await session.commit()
    return Response(status_code=204)


# --------------------------------------------------------------- taste/hw
@router.get("/taste")
async def taste(principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    profile, _, _ = await recommend.compute_profile(session, principal.user_id)
    pos, neg = top_features(profile)
    fmt = lambda items: [{"key": k, "label": k.split(":", 1)[1].replace("-", " "), "kind": k.split(":", 1)[0], "weight": w} for k, w in items]  # noqa: E731
    pp = await session.get(PreferenceProfile, principal.user_id)
    return {"likes": fmt(pos), "dislikes": fmt(neg), "explicit": (pp.explicit if pp else {}) or {}}


@router.put("/taste/explicit", status_code=204)
async def explicit(body: ExplicitPrefsIn, principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)):
    weights: dict[str, float] = {}
    for tok, val in [(t, 1.0) for t in body.likes] + [(t, -1.0) for t in body.dislikes]:
        for kind in ("genre", "tag", "feature"):
            weights[f"{kind}:{tok}"] = val
    stmt = insert(PreferenceProfile).values(user_id=principal.user_id, weights={}, explicit=weights)
    await session.execute(stmt.on_conflict_do_update(index_elements=["user_id"], set_={"explicit": weights}))
    await session.commit()
    return Response(status_code=204)


@router.get("/hardware")
async def get_hardware(principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    hw = await session.get(HardwareProfile, principal.user_id)
    if not hw:
        return {}
    return {"cpu": hw.cpu, "gpu": hw.gpu, "ram_gb": hw.ram_gb, "vram_gb": hw.vram_gb, "storage_gb": hw.storage_gb, "os": hw.os,
            "gpu_recognized": hw.gpu_tier is not None, "cpu_recognized": hw.cpu_tier is not None}


@router.put("/hardware")
async def put_hardware(body: HardwareIn, principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    values = body.model_dump() | {"gpu_tier": gpu_tier(body.gpu), "cpu_tier": cpu_tier(body.cpu)}
    stmt = insert(HardwareProfile).values(user_id=principal.user_id, **values)
    await session.execute(stmt.on_conflict_do_update(index_elements=["user_id"], set_=values))
    await session.commit()
    return {"gpu_recognized": values["gpu_tier"] is not None, "cpu_recognized": values["cpu_tier"] is not None}


# ------------------------------------------------------------- usage/cost
@router.get("/usage")
async def usage(principal: Principal = Depends(current_user), session: AsyncSession = Depends(get_session)) -> dict:
    row = (await session.execute(select(
        func.coalesce(func.sum(UsageLog.cost_micro_usd), 0), func.coalesce(func.sum(UsageLog.tokens_in + UsageLog.tokens_out), 0),
        func.count(), func.count().filter(UsageLog.cached.is_(True)),
    ).where(UsageLog.user_id == principal.user_id))).one()
    return {"cost_usd": row[0] / 1e6, "tokens": row[1], "calls": row[2], "cache_hits": row[3]}


# --------------------------------------------------------- account deletion
@router.delete("/account", status_code=204)
async def delete_account(request: Request, response: Response, principal: Principal = Depends(current_user),
                         session: AsyncSession = Depends(get_session)):
    """Right to erasure: removes the auth user; all user data cascades from profiles."""
    r = await _gotrue("DELETE", f"/admin/users/{principal.user_id}", secret=True)
    if r.status_code not in (200, 204, 404):
        raise HTTPException(502, "Could not delete account")
    await session.execute(delete(Profile).where(Profile.id == principal.user_id))
    await session.commit()
    await audit(session, request, "account_deleted", user_id=None)
    out = Response(status_code=204)
    clear_auth_cookies(out)
    return out
