"""
Shared mixins for DQ ViewSets.

Extracted from ``DQRunViewSet`` so the AUDITOR read-only permission
check is reusable across all DQ ViewSets that support write operations.
"""


class AuditorPermissionMixin:
    """Enforce AUDITOR role read-only access on write endpoints.

    Usage::

        class MyViewSet(AuditorPermissionMixin, DQFeatureFlagMixin,
                        viewsets.ModelViewSet):

            def create(self, request):
                self.check_auditor_permissions(request, "create")
                ...

            def update(self, request, *args, **kwargs):
                self.check_auditor_permissions(request, "update")
                return super().update(request, *args, **kwargs)
    """

    def check_auditor_permissions(self, request, view_action):
        """Check if AUDITOR role can perform the action (read-only)."""
        if not request.user or not request.user.is_authenticated:
            return True  # Let IsAuthenticated handle this

        # Check if user has AUDITOR role
        if hasattr(request.user, "user_roles"):
            role_names = [ur.role.name for ur in request.user.user_roles.all()]
            if "AUDITOR" in role_names:
                # AUDITOR can only read, not write
                if view_action in ["create", "update", "partial_update", "destroy"]:
                    from rest_framework.exceptions import PermissionDenied

                    raise PermissionDenied(
                        "AUDITOR role has read-only access. "
                        "Cannot perform write operations."
                    )

        return True
