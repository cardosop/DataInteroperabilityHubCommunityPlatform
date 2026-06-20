"""
285.5.2.1 — Marketplace integrations feature-flag gate mixin.

Follows the DQFeatureFlagMixin pattern.  Gates the marketplace
integrations ViewSet on ``Tenant.marketplace_integrations_enabled``.
"""

from __future__ import annotations

from rest_framework.response import Response

from hub.apps.tenants.feature_flag_gates import check_marketplace_integrations_enabled


class _MarketplaceIntegrationsFlagDeniedException(Exception):
    def __init__(self, response: Response):
        self.response = response


class MarketplaceIntegrationsFeatureFlagMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        result = check_marketplace_integrations_enabled(request)
        if isinstance(result, Response):
            raise _MarketplaceIntegrationsFlagDeniedException(result)

    def handle_exception(self, exc):
        if isinstance(exc, _MarketplaceIntegrationsFlagDeniedException):
            return exc.response
        return super().handle_exception(exc)
