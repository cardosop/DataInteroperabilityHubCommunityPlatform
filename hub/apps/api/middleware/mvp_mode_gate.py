"""
Block /api/v1/* non-MVP prefixes when MVP_MODE is enabled.

Reads ``settings.MVP_MODE`` per request so ``override_settings`` works in tests.
Routes remain in URLconf; this middleware is the runtime gate (see ``hub.apps.api.mvp_mode``).
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.http import Http404

from hub.apps.api.mvp_mode import is_mvp_gated_api_v1_path

logger = logging.getLogger(__name__)


class MvpModeApiGateMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(settings, "MVP_MODE", False) and is_mvp_gated_api_v1_path(
            request.path
        ):
            # Track A observability: surface every gate-blocked request so
            # staging scanner probes and real-user bookmark drift become
            # visible via structured logs. No request body, no auth info —
            # just path + source IP for rate/anomaly analysis.
            logger.info(
                "mvp_gate_blocked",
                extra={
                    "path": request.path,
                    "remote_addr": request.META.get("REMOTE_ADDR"),
                },
            )
            # Use Django Http404 so middleware returns a normal 404 response and
            # @override_settings contexts exit cleanly (DRF NotFound can leak as 500).
            raise Http404("Resource not found")
        return self.get_response(request)
