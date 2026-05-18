from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.schemas.tenants import (
    PaginatedTenantResponse,
    TenantDetailResponse,
    TenantInvite,
    TenantResponse,
    TenantUpdate,
)
from app.services.tenant_service import TenantService

router = APIRouter()

_landlord_or_manager = require_role(UserRole.LANDLORD, UserRole.MANAGER)


@router.get("", response_model=PaginatedTenantResponse)
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    active_only: bool = Query(False),
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaginatedTenantResponse:
    service = TenantService(db)
    return await service.list_tenants(user, page=page, page_size=page_size, search=search, active_only=active_only)


@router.post("/invite", response_model=TenantResponse, status_code=201)
async def invite_tenant(
    data: TenantInvite,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TenantResponse:
    service = TenantService(db)
    return await service.invite_tenant(user, data)


@router.get("/{tenant_id}", response_model=TenantDetailResponse)
async def get_tenant(
    tenant_id: UUID,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TenantDetailResponse:
    service = TenantService(db)
    return await service.get_tenant(user, tenant_id)


@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: UUID,
    data: TenantUpdate,
    user: CurrentUser = Depends(_landlord_or_manager),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TenantResponse:
    service = TenantService(db)
    return await service.update_tenant(user, tenant_id, data)


@router.patch("/{tenant_id}/deactivate", response_model=TenantResponse)
async def deactivate_tenant(
    tenant_id: UUID,
    user: CurrentUser = Depends(require_role(UserRole.LANDLORD)),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> TenantResponse:
    service = TenantService(db)
    return await service.deactivate_tenant(user, tenant_id)
