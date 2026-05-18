import logging

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.RESEND_API_KEY


async def send_magic_link_email(to: str, token: str) -> None:
    link = f"{settings.BACKEND_CORS_ORIGINS[0]}/magic-link?token={token}"
    try:
        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM,
                "to": [to],
                "subject": "Your RentDesk login link",
                "html": (
                    f"<p>Click the link below to sign in to RentDesk:</p>"
                    f'<p><a href="{link}">Sign in to RentDesk</a></p>'
                    f"<p>This link expires in 15 minutes.</p>"
                    f"<p>If you didn't request this, you can safely ignore this email.</p>"
                ),
            }
        )
    except Exception:
        logger.exception("Failed to send magic link email to %s", to)


async def send_password_reset_email(to: str, token: str) -> None:
    link = f"{settings.BACKEND_CORS_ORIGINS[0]}/reset-password?token={token}"
    try:
        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM,
                "to": [to],
                "subject": "Reset your RentDesk password",
                "html": (
                    f"<p>You requested a password reset for your RentDesk account.</p>"
                    f'<p><a href="{link}">Reset your password</a></p>'
                    f"<p>This link expires in 1 hour.</p>"
                    f"<p>If you didn't request this, you can safely ignore this email.</p>"
                ),
            }
        )
    except Exception:
        logger.exception("Failed to send password reset email to %s", to)
