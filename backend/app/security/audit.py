import logging
import uuid

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AuditLog
from .ratelimit import client_ip, hash_value

log = logging.getLogger("gamefy.audit")


async def audit(session: AsyncSession, request: Request, action: str,
                user_id: uuid.UUID | None = None, **meta: object) -> None:
    """Security/audit trail. Stores a hash of the IP, never raw IPs, emails or secrets."""
    ip_hash = hash_value(client_ip(request))
    log.info("audit", extra={"action": action, "ip_hash": ip_hash, "user_id": str(user_id) if user_id else None})
    try:
        session.add(AuditLog(user_id=user_id, action=action, ip_hash=ip_hash, meta=meta))
        await session.commit()
    except Exception:  # noqa: BLE001 - auditing must never break the request
        await session.rollback()
        log.exception("audit_write_failed")
