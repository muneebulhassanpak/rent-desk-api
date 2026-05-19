from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.dashboards import (
    LandlordDashboard,
    ManagerDashboard,
    TenantDashboard,
    VendorDashboard,
)
from app.services.dashboard_service import DashboardService

router = APIRouter()

_landlord_only = require_role(UserRole.LANDLORD)
_manager_only = require_role(UserRole.MANAGER)
_tenant_only = require_role(UserRole.TENANT)
_vendor_only = require_role(UserRole.VENDOR)
_landlord_or_manager = require_role(UserRole.LANDLORD, UserRole.MANAGER)


@router.get("/landlord", response_model=LandlordDashboard)
async def landlord_dashboard(
    user: CurrentUser = Depends(_landlord_only),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> LandlordDashboard:
    service = DashboardService(db)
    return await service.landlord_dashboard(user)


@router.get("/manager", response_model=ManagerDashboard)
async def manager_dashboard(
    user: CurrentUser = Depends(_manager_only),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ManagerDashboard:
    service = DashboardService(db)
    return await service.manager_dashboard(user)


@router.get("/tenant", response_model=TenantDashboard)
async def tenant_dashboard(
    user: CurrentUser = Depends(_tenant_only),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TenantDashboard:
    service = DashboardService(db)
    return await service.tenant_dashboard(user)


@router.get("/vendor", response_model=VendorDashboard)
async def vendor_dashboard(
    user: CurrentUser = Depends(_vendor_only),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> VendorDashboard:
    service = DashboardService(db)
    return await service.vendor_dashboard(user)
