"""HTTP surface for DSAR (public ingress + tenant handler console)."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings as django_settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from hub.apps.dsar.captcha import verify_hcaptcha
from hub.apps.dsar.email_notify import send_dsar_otp_email
from hub.apps.dsar.models import DSARRequest, DSARStatus, DSARVerificationMethod
from hub.apps.dsar.packaging import materialize_dsar_package
from hub.apps.dsar.permissions import IsDsarHandler
from hub.apps.dsar.serializers import (
    DSARRequestSerializer,
    PublicDsarOtpSerializer,
    PublicDsarSubmitSerializer,
)
from hub.apps.dsar.throttles import DsarPublicIPThrottle
from hub.apps.dsar.workflow import (
    begin_identity_email_otp,
    create_dsar_public,
    set_legal_hold,
    submit_email_otp,
    transition_status,
)
from hub.apps.files.storage import S3StorageClient


def _localized_fulfil_iso(row: DSARRequest, tz_name: str) -> str | None:
    """ISO-8601 in ``tz_name`` (invalid IANA → UTC)."""
    dt = row.statutory_fulfil_deadline_utc
    if not dt:
        return None
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    label = (tz_name or "UTC").strip() or "UTC"
    try:
        return dt.astimezone(ZoneInfo(label)).isoformat()
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return dt.astimezone(ZoneInfo("UTC")).isoformat()


def _client_ip(request) -> str:
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return xff or (request.META.get("REMOTE_ADDR") or "")


class PublicDsarSubmitView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [DsarPublicIPThrottle]

    def post(self, request):
        ser = PublicDsarSubmitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ip = _client_ip(request)
        captcha_ok = verify_hcaptcha(
            response_token=ser.validated_data["hcaptcha_response"],
            remote_ip=ip or None,
        )
        if not captcha_ok:
            return Response(
                {"detail": "Captcha verification failed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        idem_key = (request.META.get("HTTP_IDEMPOTENCY_KEY", "").strip()[:128]) or ""
        tenant_id = str(ser.validated_data["tenant_id"])

        window_h = int(getattr(django_settings, "DSAR_PUBLIC_IDEMPOTENCY_WINDOW_HOURS", 24))
        cutoff = timezone.now() - timedelta(hours=window_h)
        dup = None
        if idem_key:
            dup = (
                DSARRequest.objects.filter(
                    tenant_id=tenant_id,
                    idempotency_key=idem_key,
                    created_at__gte=cutoff,
                )
                .order_by("-created_at")
                .first()
            )
        if idem_key and dup:
            return Response(
                {
                    "id": str(dup.id),
                    "public_reference_token": str(dup.public_reference_token),
                    "status": dup.status,
                    "duplicate": True,
                },
                status=status.HTTP_200_OK,
            )

        try:
            row = create_dsar_public(
                tenant_id=tenant_id,
                request_type=ser.validated_data["request_type"],
                subject_email=ser.validated_data["subject_email"],
                regimes=list(ser.validated_data["regimes"]),
                subject_name=ser.validated_data.get("subject_name") or "",
                subject_timezone=ser.validated_data.get("subject_timezone") or "UTC",
                regulator_timezone=ser.validated_data.get("regulator_timezone") or "UTC",
                verification_method=(
                    ser.validated_data.get("verification_method")
                    or DSARVerificationMethod.EMAIL_OTP
                ),
                idempotency_key=idem_key,
                extension_path_selected=ser.validated_data.get("extension_path_selected", False),
            )
        except DjangoValidationError as exc:
            err_list = getattr(exc, "error_list", None)
            msgs = getattr(exc, "messages", None)
            if err_list:
                payload = {"detail": [str(e) for e in exc.error_list]}
            elif msgs:
                payload = {"detail": list(msgs)}
            else:
                payload = {"detail": [str(exc)]}
            return Response(payload, status=422)

        if row.verification_method == DSARVerificationMethod.EMAIL_OTP:
            code = begin_identity_email_otp(row)
            send_dsar_otp_email(row, code)

        return Response(
            {
                "id": str(row.id),
                "public_reference_token": str(row.public_reference_token),
                "status": row.status,
            },
            status=status.HTTP_201_CREATED,
        )


class PublicDsarVerifyOtpView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [DsarPublicIPThrottle]

    def post(self, request, dsar_id):
        row = get_object_or_404(DSARRequest, id=dsar_id)
        ser = PublicDsarOtpSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if not submit_email_otp(row, ser.validated_data["code"]):
            return Response(
                {"detail": "Invalid or expired OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        row.refresh_from_db()
        return Response({"status": row.status}, status=status.HTTP_200_OK)


class PublicDsarStatusByTokenView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [DsarPublicIPThrottle]

    def get(self, request, reference_token):
        row = get_object_or_404(DSARRequest, public_reference_token=reference_token)
        payload = DSARRequestSerializer(instance=row).data
        sub_tz = row.subject_timezone or "UTC"
        reg_tz = row.regulator_timezone or "UTC"
        return Response(
            {
                "status": payload["status"],
                "request_type": payload["request_type"],
                "statutory_ack_deadline_utc": payload["statutory_ack_deadline_utc"],
                "statutory_fulfil_deadline_utc": payload["statutory_fulfil_deadline_utc"],
                "subject_timezone": sub_tz,
                "regulator_timezone": reg_tz,
                "statutory_fulfil_deadline_subject_local": _localized_fulfil_iso(row, sub_tz),
                "statutory_fulfil_deadline_regulator_local": _localized_fulfil_iso(row, reg_tz),
                "legal_hold": payload["legal_hold"],
            },
            status=status.HTTP_200_OK,
        )


class DSARRequestViewSet(viewsets.ModelViewSet):
    """Tenant-authenticated handlers (queues, fulfilment tooling)."""

    serializer_class = DSARRequestSerializer
    permission_classes = [IsDsarHandler]
    throttle_classes = [DsarPublicIPThrottle]  # 283.3.2.4 — G8 Rate gate
    http_method_names = ["get", "head", "patch", "options", "post"]
    queryset = DSARRequest.objects.all()

    def perform_create(self, serializer):
        tenant_id = getattr(self.request.user, "tenant_id", None)
        if tenant_id is None:
            raise ValidationError("Cannot create a DSAR request without a tenant context.")
        serializer.save(tenant_id=tenant_id)

    def get_queryset(self):
        qs = super().get_queryset().select_related("tenant")
        user = self.request.user
        if getattr(user, "is_platform_admin", False):
            return qs
        if not user.is_authenticated or not getattr(user, "tenant_id", None):
            return qs.none()
        return qs.filter(tenant_id=user.tenant_id)

    @action(detail=True, methods=["post"])
    def materialize_package(self, request, pk=None):
        row = self.get_object()
        materialize_dsar_package(row, actor_user_id=str(request.user.id))
        row.refresh_from_db()
        return Response(DSARRequestSerializer(instance=row).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        row = self.get_object()
        reason = request.data.get("reason", "")
        transition_status(row, DSARStatus.CLOSED_REJECTED, actor_user=request.user, notes=reason)
        row.refresh_from_db()
        return Response(DSARRequestSerializer(instance=row).data)

    @action(detail=True, methods=["post"])
    def legal_hold(self, request, pk=None):
        row = self.get_object()
        active = bool(request.data.get("active", False))
        reason = str(request.data.get("reason") or "")
        set_legal_hold(row, active=active, reason=reason, actor_user=request.user)
        row.refresh_from_db()
        return Response(DSARRequestSerializer(instance=row).data)

    @action(detail=True, methods=["post"])
    def issue_download_url(self, request, pk=None):
        row = self.get_object()
        if not row.response_object_key:
            return Response(
                {"detail": "Package not materialised yet."},
                status=status.HTTP_409_CONFLICT,
            )
        if row.download_consumed_at:
            return Response(
                {"detail": "Download already issued (one-time)."},
                status=status.HTTP_410_GONE,
            )
        client = S3StorageClient()
        url = client.generate_presigned_download_url(
            key=row.response_object_key,
            expires_in=86400,
            filename=f"dsar-{row.id}.zip",
        )
        DSARRequest.objects.filter(pk=row.pk).update(
            download_consumed_at=timezone.now(),
            download_url_issued_at=timezone.now(),
        )
        return Response({"download_url": url, "expires_in": 86400})
