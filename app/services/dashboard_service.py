from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.models.enums import UserRole
from app.repositories.dashboard_repo import DashboardRepository
from app.schemas.dashboards import (
    ActivityItem,
    CategoryCount,
    LandlordDashboard,
    ManagerDashboard,
    RentChartPoint,
    TenantDashboard,
    TenantLeaseInfo,
    TenantPaymentDue,
    TenantTicketSummary,
    TodoItem,
    VendorDashboard,
)


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = DashboardRepository(db)

    async def landlord_dashboard(self, user: CurrentUser) -> LandlordDashboard:
        kpis = await self.repo.landlord_kpis(user.org_id)
        chart = await self.repo.rent_chart(user.org_id)
        categories = await self.repo.issues_by_category(user.org_id)
        activity = await self.repo.recent_activity(user.org_id, limit=10)

        return LandlordDashboard(
            **kpis,
            rent_chart=[RentChartPoint(**p) for p in chart],
            issues_by_category=[CategoryCount(**c) for c in categories],
            recent_activity=[ActivityItem(**a) for a in activity],
        )

    async def manager_dashboard(self, user: CurrentUser) -> ManagerDashboard:
        kpis = await self.repo.manager_kpis(user.org_id, user.property_ids)
        todo_raw = await self.repo.manager_todo(user.org_id, user.property_ids)

        return ManagerDashboard(
            **kpis,
            todo=[TodoItem(**t) for t in todo_raw],
        )

    async def tenant_dashboard(self, user: CurrentUser) -> TenantDashboard:
        raw = await self.repo.tenant_dashboard(user.org_id, user.user_id)

        return TenantDashboard(
            lease=TenantLeaseInfo(**raw["lease"]) if raw["lease"] else None,
            next_payment=TenantPaymentDue(**raw["next_payment"]) if raw["next_payment"] else None,
            open_tickets=raw["open_tickets"],
            recent_tickets=[TenantTicketSummary(**t) for t in raw["recent_tickets"]],
        )

    async def vendor_dashboard(self, user: CurrentUser) -> VendorDashboard:
        raw = await self.repo.vendor_dashboard(user.org_id, user.user_id)
        return VendorDashboard(**raw)

    async def activity_feed(self, user: CurrentUser, *, limit: int = 20) -> list[ActivityItem]:
        property_ids = user.property_ids if user.role == UserRole.MANAGER else None
        raw = await self.repo.activity_feed(user.org_id, limit=limit, property_ids=property_ids)
        return [ActivityItem(**a) for a in raw]
