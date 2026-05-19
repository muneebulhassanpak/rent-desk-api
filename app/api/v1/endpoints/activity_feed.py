from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.dashboards import ActivityItem
from app.services.dashboard_service import DashboardService

router = APIRouter()

_landlord_or_manager = require_role(UserRole.LANDLORD, UserRole.MANAGER)


@router.get("", response_model=list[ActivityItem])
async def activity_feed(
    limit: int = Query(20, ge=1, le=100),
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[ActivityItem]:
    service = DashboardService(db)
    return await service.activity_feed(user, limit=limit)
