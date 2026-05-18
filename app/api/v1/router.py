from fastapi import APIRouter

from app.api.v1.endpoints import auth, photos, properties, units

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(properties.router, prefix="/properties", tags=["properties"])
# Units router mounts at /api/v1 since it has /properties/{id}/units and /units/{id} paths
api_router.include_router(units.router)
# Photos router mounts at /api/v1 since it has /properties/{id}/photos and /photos/{id} paths
api_router.include_router(photos.router)
# api_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
# api_router.include_router(leases.router, prefix="/leases", tags=["leases"])
# api_router.include_router(payments.router, prefix="/payments", tags=["payments"])
# api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
# api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
# api_router.include_router(vendors.router, prefix="/vendors", tags=["vendors"])
# api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
# api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
# api_router.include_router(settings_.router, prefix="/settings", tags=["settings"])
# api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
# api_router.include_router(audit.router, prefix="/audit-log", tags=["audit"])
