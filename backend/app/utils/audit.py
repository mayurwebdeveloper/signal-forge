"""Audit logging helper."""
from typing import Any

from sqlalchemy.orm import Session

from app.database.models import AuditLog


def log_audit(
    db: Session,
    action: str,
    user_id: int | None = None,
    resource: str | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            details=details,
            ip_address=ip_address,
        )
    )
    db.commit()
