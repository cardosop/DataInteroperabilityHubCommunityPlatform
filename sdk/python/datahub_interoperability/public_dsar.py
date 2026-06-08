"""
283.3.2.1 — Public DSAR (Data Subject Access Request) SDK.

Expanded from 12L to ~85L with full CRUD surface.
All operations are unauthenticated (public ingress per GDPR Art. 15-22).
Backward-compatible — existing ``submit()``, ``status()``, ``verify_otp()``
signatures preserved.
"""
from typing import Any, Dict, List, Optional
from .client import DataHubClient


class PublicDsarAPI:
    """Public DSAR operations — no authentication required."""

    def __init__(self, client: DataHubClient):
        self.client = client

    # ── Submit ──────────────────────────────────────────────────────────

    async def submit(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Submit a DSAR with a raw payload dict (backward-compat)."""
        return await self.client.post("public/dsar-requests/", data=data)

    async def submit_request(
        self,
        email: str,
        request_type: str,
        tenant_id: Optional[str] = None,
        regimes: Optional[List[str]] = None,
        hcaptcha_token: Optional[str] = None,
        subject_tz: Optional[str] = None,
        regulator_tz: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a new data subject rights request.

        Args:
            email: Subject's email address.
            request_type: One of ``access``, ``erasure``, ``rectification``,
                ``portability``, ``restriction``, ``objection``.
            tenant_id: Optional organisation UUID.
            regimes: Applicable privacy regimes (e.g. ``["GDPR", "CCPA"]``).
            hcaptcha_token: hCaptcha verification token.
            subject_tz: IANA timezone for deadline presentation.
            regulator_tz: IANA timezone for regulator deadline.
        """
        payload: Dict[str, Any] = {"email": email, "type": request_type}
        if tenant_id:
            payload["tenant_id"] = tenant_id
        if regimes:
            payload["regimes"] = regimes
        if hcaptcha_token:
            payload["hcaptcha_token"] = hcaptcha_token
        if subject_tz:
            payload["subject_tz"] = subject_tz
        if regulator_tz:
            payload["regulator_tz"] = regulator_tz
        return await self.client.post("public/dsar-requests/", data=payload)

    # ── OTP verification ────────────────────────────────────────────────

    async def verify_otp(self, request_id: str, otp: str) -> Dict[str, Any]:
        """Verify the one-time password sent to the subject's email.

        Returns ``{status, access_token}``.
        """
        return await self.client.post(
            f"public/dsar-requests/{request_id}/verify-otp/",
            data={"request_id": request_id, "otp": otp},
        )

    # ── Status ──────────────────────────────────────────────────────────

    async def status(self, request_id: str) -> Dict[str, Any]:
        """Get current request status (backward-compat alias for get_status)."""
        return await self.get_status(request_id)

    async def get_status(self, request_id: str) -> Dict[str, Any]:
        """Get the current status of a DSAR.

        Returns ``{request_id, status, type, ack_deadline, fulfil_deadline,
        subject_local, regulator_local, countdown}``.
        """
        return await self.client.get(f"public/dsar-requests/status/{request_id}/")

    # ── List / filter ───────────────────────────────────────────────────

    async def list_requests(
        self,
        status: Optional[str] = None,
        request_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """List DSAR requests (authenticated, admin-only).

        Args:
            status: Filter by status.
            request_type: Filter by type.
            page: Page number (1-indexed).
            page_size: Items per page (max 100).
        """
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if status:
            params["status"] = status
        if request_type:
            params["type"] = request_type
        return await self.client.get("dsar/requests/", params=params)

    # ── Cancel ──────────────────────────────────────────────────────────

    async def cancel_request(self, request_id: str) -> Dict[str, Any]:
        """Cancel a pending DSAR.

        Only ``PENDING`` / ``VERIFIED`` requests can be cancelled.
        Returns ``{status: "CANCELLED"}`` on success.
        """
        return await self.client.post(f"dsar/requests/{request_id}/cancel/", data={})

    # ── Convenience: full OTP flow ──────────────────────────────────────

    async def submit_and_verify(
        self, email: str, request_type: str, otp: str, **kwargs,
    ) -> Dict[str, Any]:
        """Submit a DSAR and verify the OTP in one call."""
        submit_resp = await self.submit_request(email, request_type, **kwargs)
        request_id = submit_resp.get("request_id") or submit_resp.get("id")
        if not request_id:
            raise ValueError(f"Submit did not return request_id: {submit_resp}")
        return await self.verify_otp(request_id, otp)
