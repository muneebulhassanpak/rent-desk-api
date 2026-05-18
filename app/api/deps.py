from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.core.security import decode_token
from app.models.enums import UserRole

bearer_scheme = HTTPBearer()


class CurrentUser:
    """Extracted from JWT claims."""

    def __init__(self, user_id: UUID, org_id: UUID, role: UserRole, property_ids: list[UUID] | None = None) -> None:
        self.user_id = user_id
        self.org_id = org_id
        self.role = role
        self.property_ids = property_ids or []


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),  # noqa: B008
) -> CurrentUser:
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        return CurrentUser(
            user_id=UUID(payload["sub"]),
            org_id=UUID(payload["org_id"]),
            role=UserRole(payload["role"]),
            property_ids=[UUID(pid) for pid in payload.get("property_ids", [])],
        )
    except (JWTError, KeyError, ValueError) as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from err


def require_role(*roles: UserRole) -> Callable[..., Coroutine[Any, Any, CurrentUser]]:
    """Dependency factory: Depends(require_role(UserRole.LANDLORD, UserRole.MANAGER))"""

    async def _check(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:  # noqa: B008
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return _check
