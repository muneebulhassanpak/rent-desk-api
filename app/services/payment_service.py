import math
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.config import settings
from app.models.enums import PaymentStatus, UserRole
from app.repositories.payment_repo import PaymentRepository
from app.repositories.property_repo import PropertyRepository
from app.schemas.payments import (
    CollectionSummary,
    PaginatedPaymentResponse,
    PaymentDetailResponse,
    PaymentResponse,
    RecordPayment,
    RentRollResponse,
    RentRollUnit,
    StripeCheckoutResponse,
)
from app.schemas.properties import PaginatedMeta


class PaymentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = PaymentRepository(db)
        self.property_repo = PropertyRepository(db)

    async def list_payments(
        self,
        user: CurrentUser,
        *,
        page: int = 1,
        page_size: int = 20,
        payment_status: PaymentStatus | None = None,
        property_id: UUID | None = None,
        month: date | None = None,
    ) -> PaginatedPaymentResponse:
        items, total = await self.repo.list(
            user.org_id, page=page, page_size=page_size, status=payment_status, property_id=property_id, month=month
        )
        return PaginatedPaymentResponse(
            items=[PaymentResponse.model_validate(p) for p in items],
            meta=PaginatedMeta(
                page=page, page_size=page_size, total=total, total_pages=max(1, math.ceil(total / page_size))
            ),
        )

    async def get_payment(self, user: CurrentUser, payment_id: UUID) -> PaymentDetailResponse:
        payment = await self.repo.get_by_id(user.org_id, payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

        await self._check_payment_access(user, payment)

        resp = PaymentDetailResponse.model_validate(payment)
        context = await self.repo.get_detail_context(payment)
        resp.tenant_name = context.get("tenant_name")
        resp.unit_label = context.get("unit_label")
        resp.property_name = context.get("property_name")
        return resp

    async def record_payment(self, user: CurrentUser, payment_id: UUID, data: RecordPayment) -> PaymentResponse:
        payment = await self.repo.get_by_id(user.org_id, payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

        await self._check_payment_access(user, payment)

        if payment.status in (PaymentStatus.PAID, PaymentStatus.OVERPAID, PaymentStatus.WAIVED):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment already settled")

        new_amount_paid = payment.amount_paid + data.amount
        total_owed = payment.amount_due + payment.late_fee_amount

        if new_amount_paid >= total_owed:
            new_status = PaymentStatus.OVERPAID if new_amount_paid > total_owed else PaymentStatus.PAID
        else:
            new_status = PaymentStatus.PARTIAL

        payment = await self.repo.update(
            payment,
            {
                "amount_paid": new_amount_paid,
                "status": new_status,
                "method": data.method,
                "reference": data.reference,
                "notes": data.notes,
                "paid_at": datetime.now(UTC),
                "recorded_by": user.user_id,
            },
        )
        return PaymentResponse.model_validate(payment)

    async def waive_payment(self, user: CurrentUser, payment_id: UUID, notes: str | None = None) -> PaymentResponse:
        payment = await self.repo.get_by_id(user.org_id, payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

        if payment.status in (PaymentStatus.PAID, PaymentStatus.OVERPAID, PaymentStatus.WAIVED):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment already settled")

        payment = await self.repo.update(
            payment,
            {"status": PaymentStatus.WAIVED, "notes": notes or payment.notes, "recorded_by": user.user_id},
        )
        return PaymentResponse.model_validate(payment)

    async def waive_late_fee(self, user: CurrentUser, payment_id: UUID) -> PaymentResponse:
        payment = await self.repo.get_by_id(user.org_id, payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

        if payment.late_fee_amount == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No late fee to waive")

        payment = await self.repo.update(payment, {"late_fee_amount": Decimal("0"), "late_fee_applied_at": None})
        return PaymentResponse.model_validate(payment)

    async def collection_summary(self, user: CurrentUser, month: date) -> CollectionSummary:
        raw = await self.repo.collection_summary(user.org_id, month)
        total_expected = raw["total_expected"]
        total_collected = raw["total_collected"]
        outstanding = total_expected - total_collected
        rate = (total_collected / total_expected * 100) if total_expected > 0 else Decimal("0")

        return CollectionSummary(
            month=month.strftime("%Y-%m"),
            total_expected=total_expected,
            total_collected=total_collected,
            outstanding=outstanding,
            late_count=raw["late_count"],
            collection_rate=round(rate, 1),
        )

    async def lease_payments(self, user: CurrentUser, lease_id: UUID) -> list[PaymentResponse]:
        payments = await self.repo.get_payments_for_lease(user.org_id, lease_id)
        return [PaymentResponse.model_validate(p) for p in payments]

    async def rent_roll(self, user: CurrentUser, property_id: UUID, month: date) -> RentRollResponse:
        prop = await self.property_repo.get_by_id(user.org_id, property_id)
        if not prop:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

        self._check_property_access(user, property_id)

        rows = await self.repo.rent_roll(user.org_id, property_id, month)

        units = [
            RentRollUnit(
                unit_id=r["unit_id"],
                unit_label=r["unit_label"],
                tenant_name=r["tenant_name"],
                monthly_rent=r["monthly_rent"],
                payment_status=r["payment_status"],
                amount_paid=r["amount_paid"],
            )
            for r in rows
        ]

        total_expected = sum(u.monthly_rent for u in units)
        total_collected = sum(u.amount_paid for u in units)
        rate = (total_collected / total_expected * 100) if total_expected > 0 else Decimal("0")

        return RentRollResponse(
            property_id=property_id,
            property_name=prop.name,
            month=month.strftime("%Y-%m"),
            units=units,
            total_expected=total_expected,
            total_collected=total_collected,
            collection_rate=round(rate, 1),
        )

    async def create_stripe_checkout(self, user: CurrentUser, payment_id: UUID) -> StripeCheckoutResponse:
        payment = await self.repo.get_by_id(user.org_id, payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

        if payment.status in (PaymentStatus.PAID, PaymentStatus.OVERPAID, PaymentStatus.WAIVED):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment already settled")

        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe is not configured")

        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY

        amount_remaining = payment.amount_due + payment.late_fee_amount - payment.amount_paid
        context = await self.repo.get_detail_context(payment)

        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": int(amount_remaining * 100),
                        "product_data": {
                            "name": f"Rent - {context.get('unit_label', 'Unit')}",
                            "description": f"Due {payment.due_date.isoformat()}",
                        },
                    },
                    "quantity": 1,
                }
            ],
            metadata={"payment_id": str(payment.id), "org_id": str(payment.org_id)},
            success_url=f"{settings.BACKEND_CORS_ORIGINS[0]}/payments/{payment.id}?status=success",
            cancel_url=f"{settings.BACKEND_CORS_ORIGINS[0]}/payments/{payment.id}?status=cancelled",
        )

        await self.repo.update(payment, {"stripe_payment_intent_id": session.payment_intent})

        return StripeCheckoutResponse(checkout_url=session.url)

    async def generate_receipt(self, user: CurrentUser, payment_id: UUID) -> bytes:
        payment = await self.repo.get_by_id(user.org_id, payment_id)
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

        if payment.status not in (PaymentStatus.PAID, PaymentStatus.OVERPAID):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Receipt only available for paid payments"
            )

        await self._check_payment_access(user, payment)
        context = await self.repo.get_detail_context(payment)

        from io import BytesIO

        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas

        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        width, height = letter

        # Header
        c.setFont("Helvetica-Bold", 20)
        c.drawString(1 * inch, height - 1 * inch, "Payment Receipt")

        c.setFont("Helvetica", 10)
        c.drawString(1 * inch, height - 1.4 * inch, f"Receipt ID: {payment.id}")

        # Details
        y = height - 2 * inch
        c.setFont("Helvetica-Bold", 11)
        fields = [
            ("Property", context.get("property_name", "—")),
            ("Unit", context.get("unit_label", "—")),
            ("Tenant", context.get("tenant_name", "—")),
            ("Due Date", str(payment.due_date)),
            ("Amount Due", f"${payment.amount_due:,.2f}"),
            ("Late Fee", f"${payment.late_fee_amount:,.2f}"),
            ("Amount Paid", f"${payment.amount_paid:,.2f}"),
            ("Payment Method", payment.method.value if payment.method else "—"),
            ("Reference", payment.reference or "—"),
            ("Paid At", payment.paid_at.strftime("%Y-%m-%d %H:%M UTC") if payment.paid_at else "—"),
            ("Status", payment.status.value.upper()),
        ]
        for label, value in fields:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(1 * inch, y, f"{label}:")
            c.setFont("Helvetica", 10)
            c.drawString(3 * inch, y, str(value))
            y -= 0.3 * inch

        # Footer
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(1 * inch, 0.75 * inch, "Generated by RentDesk — this is an official payment receipt.")

        c.save()
        return buf.getvalue()

    async def _check_payment_access(self, user: CurrentUser, payment: object) -> None:
        """Managers can only access payments for their assigned properties."""
        if user.role == UserRole.MANAGER:
            property_id = await self.repo.get_lease_property_id(payment.lease_id)
            if property_id and property_id not in user.property_ids:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this property")

    @staticmethod
    def _check_property_access(user: CurrentUser, property_id: UUID) -> None:
        if user.role == UserRole.MANAGER and property_id not in user.property_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this property")
