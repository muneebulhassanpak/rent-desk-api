import math
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.models.enums import LeaseStatus, UnitStatus, UserRole
from app.models.lease import Lease
from app.repositories.lease_repo import LeaseRepository
from app.repositories.property_repo import PropertyRepository
from app.repositories.unit_repo import UnitRepository
from app.schemas.leases import (
    LeaseCreate,
    LeaseDetailResponse,
    LeaseRenew,
    LeaseResponse,
    LeaseTenantResponse,
    LeaseTerminate,
    LeaseUpdate,
    PaginatedLeaseResponse,
)
from app.schemas.properties import PaginatedMeta


class LeaseService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = LeaseRepository(db)
        self.unit_repo = UnitRepository(db)
        self.property_repo = PropertyRepository(db)

    async def list_leases(
        self,
        user: CurrentUser,
        *,
        page: int = 1,
        page_size: int = 20,
        lease_status: LeaseStatus | None = None,
        property_id: UUID | None = None,
    ) -> PaginatedLeaseResponse:
        items, total = await self.repo.list(
            user.org_id, page=page, page_size=page_size, status=lease_status, property_id=property_id
        )
        return PaginatedLeaseResponse(
            items=[LeaseResponse.model_validate(ls) for ls in items],
            meta=PaginatedMeta(
                page=page, page_size=page_size, total=total, total_pages=max(1, math.ceil(total / page_size))
            ),
        )

    async def get_lease(self, user: CurrentUser, lease_id: UUID) -> LeaseDetailResponse:
        lease = await self.repo.get_by_id(user.org_id, lease_id)
        if not lease:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")

        self._check_property_access(user, lease.property_id)

        resp = LeaseDetailResponse.model_validate(lease)
        resp.tenants = [LeaseTenantResponse(tenant_id=lt.tenant_id, is_primary=lt.is_primary) for lt in lease.tenants]

        unit = await self.unit_repo.get_by_id(user.org_id, lease.unit_id)
        if unit:
            resp.unit_label = unit.label

        prop = await self.property_repo.get_by_id(user.org_id, lease.property_id)
        if prop:
            resp.property_name = prop.name

        return resp

    async def create_lease(self, user: CurrentUser, data: LeaseCreate) -> LeaseResponse:
        unit = await self.unit_repo.get_by_id(user.org_id, data.unit_id)
        if not unit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found")

        self._check_property_access(user, unit.property_id)

        lease = Lease(
            org_id=user.org_id,
            property_id=unit.property_id,
            unit_id=data.unit_id,
            start_date=data.start_date,
            end_date=data.end_date,
            monthly_rent=data.monthly_rent,
            security_deposit=data.security_deposit,
            payment_due_day=data.payment_due_day,
            status=LeaseStatus.DRAFT,
            created_by=user.user_id,
        )
        lease = await self.repo.create(lease)
        await self.repo.add_tenants(lease.id, data.tenant_ids, data.primary_tenant_id)

        return LeaseResponse.model_validate(lease)

    async def update_lease(self, user: CurrentUser, lease_id: UUID, data: LeaseUpdate) -> LeaseResponse:
        lease = await self.repo.get_by_id(user.org_id, lease_id)
        if not lease:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")
        if lease.status != LeaseStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft leases can be edited")

        self._check_property_access(user, lease.property_id)
        updates = data.model_dump(exclude_unset=True)
        if not updates:
            return LeaseResponse.model_validate(lease)
        lease = await self.repo.update(lease, updates)
        return LeaseResponse.model_validate(lease)

    async def activate_lease(self, user: CurrentUser, lease_id: UUID) -> LeaseResponse:
        lease = await self.repo.get_by_id(user.org_id, lease_id)
        if not lease:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")
        if lease.status != LeaseStatus.DRAFT:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft leases can be activated")

        self._check_property_access(user, lease.property_id)

        lease = await self.repo.update(lease, {"status": LeaseStatus.ACTIVE})

        # Mark unit as occupied
        unit = await self.unit_repo.get_by_id(user.org_id, lease.unit_id)
        if unit:
            await self.unit_repo.update(unit, {"status": UnitStatus.OCCUPIED})

        return LeaseResponse.model_validate(lease)

    async def renew_lease(self, user: CurrentUser, lease_id: UUID, data: LeaseRenew) -> LeaseResponse:
        old_lease = await self.repo.get_by_id(user.org_id, lease_id)
        if not old_lease:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")
        if old_lease.status not in (LeaseStatus.ACTIVE, LeaseStatus.EXPIRING_SOON):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Only active or expiring leases can be renewed"
            )

        self._check_property_access(user, old_lease.property_id)

        new_lease = Lease(
            org_id=user.org_id,
            property_id=old_lease.property_id,
            unit_id=old_lease.unit_id,
            start_date=data.start_date,
            end_date=data.end_date,
            monthly_rent=data.monthly_rent,
            security_deposit=data.security_deposit if data.security_deposit is not None else old_lease.security_deposit,
            payment_due_day=data.payment_due_day if data.payment_due_day is not None else old_lease.payment_due_day,
            status=LeaseStatus.DRAFT,
            renewed_from_lease_id=old_lease.id,
            created_by=user.user_id,
        )
        new_lease = await self.repo.create(new_lease)

        # Copy tenants from old lease
        if old_lease.tenants:
            primary_id = next(
                (lt.tenant_id for lt in old_lease.tenants if lt.is_primary), old_lease.tenants[0].tenant_id
            )
            tenant_ids = [lt.tenant_id for lt in old_lease.tenants]
            await self.repo.add_tenants(new_lease.id, tenant_ids, primary_id)

        return LeaseResponse.model_validate(new_lease)

    async def terminate_lease(self, user: CurrentUser, lease_id: UUID, data: LeaseTerminate) -> LeaseResponse:
        lease = await self.repo.get_by_id(user.org_id, lease_id)
        if not lease:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease not found")
        if lease.status not in (LeaseStatus.ACTIVE, LeaseStatus.EXPIRING_SOON):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Only active or expiring leases can be terminated"
            )

        self._check_property_access(user, lease.property_id)

        lease = await self.repo.update(
            lease,
            {
                "status": LeaseStatus.TERMINATED,
                "terminated_at": data.termination_date,
                "termination_reason": data.reason,
                "deposit_settlement_notes": data.deposit_settlement_notes,
            },
        )

        # Mark unit as vacant
        unit = await self.unit_repo.get_by_id(user.org_id, lease.unit_id)
        if unit:
            await self.unit_repo.update(unit, {"status": UnitStatus.VACANT})

        return LeaseResponse.model_validate(lease)

    @staticmethod
    def _check_property_access(user: CurrentUser, property_id: UUID) -> None:
        if user.role == UserRole.MANAGER and property_id not in user.property_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this property")
