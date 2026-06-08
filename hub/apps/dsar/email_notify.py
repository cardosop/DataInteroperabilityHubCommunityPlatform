"""Send DSAR OTP email (production uses tenant-branded templates in a later phase)."""

from __future__ import annotations
from django.conf import settings
from django.core.mail import send_mail


def send_dsar_otp_email(dsar, code: str) -> None:
    send_mail(
        subject=f"Verify your DSAR request — {dsar.tenant.name}",
        message=(
            f"Your DSAR verification code is: {code}\n\n"
            "If you did not submit this request, contact the data controller."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
        recipient_list=[dsar.subject_email],
        fail_silently=False,
    )
