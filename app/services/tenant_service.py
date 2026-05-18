import math
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.lease_repo import LeaseRepository
from app.repositories.tenant_repo import TenantRepository
from app.schemas.properties import PaginatedMeta
from app.schemas.tenants import (
    LeaseShortResponse,
    PaginatedTenantResponse,
    TenantDetailResponse,
    TenantInvite,
    TenantResponse,
    TenantUpdate,
)


class TenantService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TenantRepository(db)
        self.lease_repo = LeaseRepository(db)

    async def list_tenants(
        self,
        user: CurrentUser,
        *,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        active_only: bool = False,
    ) -> PaginatedTenantResponse:
        items, total = await self.repo.list(
            user.org_id, page=page, page_size=page_size, search=search, active_only=active_only
        )
        return PaginatedTenantResponse(
            items=[TenantResponse.model_validate(t) for t in items],
            meta=PaginatedMeta(
                page=page, page_size=page_size, total=total, total_pages=max(1, math.ceil(total / page_size))
            ),
        )

    async def invite_tenant(self, user: CurrentUser, data: TenantInvite) -> TenantResponse:
        existing = await self.repo.get_by_email(user.org_id, data.email)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists in this org")

        tenant = User(
            org_id=user.org_id,
            email=data.email,
            full_name=data.full_name,
            phone=data.phone,
            role=UserRole.TENANT,
            is_active=True,
            is_email_verified=False,
            totp_enabled=False,
            notification_prefs={},
        )
        tenant = await self.repo.create(tenant)
        return TenantResponse.model_validate(tenant)

    async def get_tenant(self, user: CurrentUser, tenant_id: UUID) -> TenantDetailResponse:
        tenant = await self.repo.get_by_id(user.org_id, tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        resp = TenantDetailResponse.model_validate(tenant)

        profile = await self.repo.get_profile(tenant_id)
        if profile:
            resp.emergency_contact_name = profile.emergency_contact_name
            resp.emergency_contact_phone = profile.emergency_contact_phone
            resp.notes = profile.notes

        leases = await self.lease_repo.get_leases_for_tenant(user.org_id, tenant_id)
        resp.lease_history = [
            LeaseShortResponse(
                id=ls.id,
                unit_id=ls.unit_id,
                property_id=ls.property_id,
                start_date=str(ls.start_date),
                end_date=str(ls.end_date),
                monthly_rent=str(ls.monthly_rent),
                status=ls.status.value,
            )
            for ls in leases
        ]
        return resp

    async def update_tenant(self, user: CurrentUser, tenant_id: UUID, data: TenantUpdate) -> TenantResponse:
        tenant = await self.repo.get_by_id(user.org_id, tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        user_fields = {}
        profile_fields = {}
        updates = data.model_dump(exclude_unset=True)

        for key, value in updates.items():
            if key in ("emergency_contact_name", "emergency_contact_phone", "notes"):
                profile_fields[key] = value
            else:
                user_fields[key] = value

        if user_fields:
            tenant = await self.repo.update(tenant, user_fields)
        if profile_fields:
            await self.repo.upsert_profile(tenant_id, profile_fields)

        return TenantResponse.model_validate(tenant)

    async def deactivate_tenant(self, user: CurrentUser, tenant_id: UUID) -> TenantResponse:
        tenant = await self.repo.get_by_id(user.org_id, tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        tenant = await self.repo.deactivate(tenant)
        return TenantResponse.model_validate(tenant)
