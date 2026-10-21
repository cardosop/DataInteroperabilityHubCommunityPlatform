"""
Developer Experience Views

REST API views for developer experience endpoints (plugins, SDK documentation).
"""

import logging
import re
from datetime import UTC, datetime

from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import Plugin, PluginStatus, SDKDocumentation
from .serializers import PluginSerializer, SDKDocumentationSerializer

logger = logging.getLogger(__name__)


class PluginViewSet(viewsets.ModelViewSet):
    """
    Plugin marketplace ViewSet.

    Reads (list/retrieve/marketplace) are public — the plugin marketplace
    is a public surface (AllowAny).  Writes (create/update/destroy and the
    test/validate/publish/deploy lifecycle actions) require authentication.

    Lifecycle: ``create`` starts a plugin at ALPHA (invisible to the
    public marketplace list), ``validate`` promotes ALPHA -> BETA when all
    checks pass, ``publish`` promotes to AVAILABLE (marketplace-visible),
    and ``deploy`` records a deployment entry in the plugin's metadata.
    """

    queryset = Plugin.objects.filter(status=PluginStatus.AVAILABLE)
    serializer_class = PluginSerializer
    permission_classes = (AllowAny,)
    lookup_field = "id"

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated()]

    def initial(self, request, *args, **kwargs):
        from rest_framework.exceptions import PermissionDenied

        from hub.apps.tenants.feature_flag_gates import check_developer_enabled

        result = check_developer_enabled(request)
        if isinstance(result, Response):
            raise PermissionDenied(detail=result.data)
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        """Filter queryset by category, status, and search"""
        queryset = Plugin.objects.filter(status=PluginStatus.AVAILABLE)

        # Filter by category
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category=category)

        # Filter by status (allow deprecated/beta/alpha if explicitly requested)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        else:
            # Default: only show available plugins
            queryset = queryset.filter(status=PluginStatus.AVAILABLE)

        # Search in name and description
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Sort options
        sort = self.request.query_params.get("sort", "popularity")
        if sort == "popularity":
            queryset = queryset.order_by("-download_count", "-rating", "-created_at")
        elif sort == "rating":
            queryset = queryset.order_by("-rating", "-download_count", "-created_at")
        elif sort == "recency":
            queryset = queryset.order_by("-created_at")
        elif sort == "name":
            queryset = queryset.order_by("name")
        else:
            queryset = queryset.order_by("-download_count", "-created_at")

        return queryset

    @action(detail=False, methods=["post"], url_path="install")
    def install(self, request):
        """
        Install a plugin (placeholder).

        POST /api/v1/developer/plugins/install/
        """
        plugin_id = request.data.get("plugin_id")
        return Response(
            {
                "status": "installed",
                "plugin_id": plugin_id,
                "message": "Plugin install placeholder",
            },
            status=status.HTTP_200_OK,
        )

    def create(self, request, *_args, **_kwargs):
        """Create a plugin. New plugins start at ALPHA — invisible to the
        public marketplace until ``publish`` promotes them to AVAILABLE.
        The client cannot set ``status`` directly; lifecycle actions own
        status transitions."""
        data = request.data.copy()
        data.pop("status", None)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data["status"] = PluginStatus.ALPHA
        plugin = serializer.save()
        return Response(self.get_serializer(plugin).data, status=status.HTTP_201_CREATED)

    def update(self, request, *_args, **kwargs):
        """Update plugin fields; ``status`` transitions stay lifecycle-owned."""
        data = request.data.copy()
        data.pop("status", None)
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        plugin = serializer.save()
        return Response(self.get_serializer(plugin).data, status=status.HTTP_200_OK)

    @staticmethod
    def _run_plugin_checks(plugin: Plugin) -> list[dict]:
        """Static integrity checks for the plugin lifecycle.

        Checks are additive and stateless — ``test`` reports them,
        ``validate`` gates the ALPHA -> BETA promotion on them.
        """
        metadata = plugin.metadata_json or {}
        entrypoint = metadata.get("entrypoint")
        dependencies = metadata.get("dependencies")
        checks = [
            {
                "name": "entrypoint",
                "passed": bool(isinstance(entrypoint, str) and entrypoint.strip()),
            },
            {
                "name": "dependencies",
                "passed": isinstance(dependencies, list)
                and all(isinstance(dep, str) for dep in dependencies),
            },
            {
                "name": "version_format",
                "passed": bool(re.fullmatch(r"\d+\.\d+\.\d+", plugin.version or "")),
            },
        ]
        return checks

    def _get_lifecycle_plugin(self, pk):
        """Lifecycle actions must reach ALPHA/BETA plugins, which the
        public marketplace queryset (AVAILABLE-only) hides."""
        return get_object_or_404(Plugin, pk=pk)

    @action(detail=True, methods=["post"], url_path="test")
    def test_plugin(self, _request, id=None):  # noqa: PT019 — DRF @action method, not a pytest test
        """
        Run integrity checks on a plugin and report the results.

        POST /api/v1/developer/plugins/{id}/test/
        """
        plugin = self._get_lifecycle_plugin(id)
        checks = self._run_plugin_checks(plugin)
        return Response(
            {
                "status": "tested",
                "plugin_id": str(plugin.id),
                "passed": all(check["passed"] for check in checks),
                "checks": checks,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="validate")
    def validate_plugin(self, _request, id=None):
        """
        Validate a plugin and promote ALPHA -> BETA when all checks pass.

        POST /api/v1/developer/plugins/{id}/validate/
        """
        plugin = self._get_lifecycle_plugin(id)
        checks = self._run_plugin_checks(plugin)
        failed = [check for check in checks if not check["passed"]]
        if failed:
            return Response(
                {
                    "error": "validation_failed",
                    "failed_checks": failed,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if plugin.status == PluginStatus.ALPHA:
            plugin.status = PluginStatus.BETA
            plugin.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "status": "validated",
                "plugin_id": str(plugin.id),
                "plugin_status": plugin.status,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="publish")
    def publish_plugin(self, _request, id=None):
        """
        Publish a plugin to the marketplace (status -> AVAILABLE).

        POST /api/v1/developer/plugins/{id}/publish/
        """
        plugin = self._get_lifecycle_plugin(id)
        if plugin.status == PluginStatus.DEPRECATED:
            return Response(
                {"error": "deprecated_plugins_cannot_be_published"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if plugin.status != PluginStatus.AVAILABLE:
            plugin.status = PluginStatus.AVAILABLE
            plugin.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "status": "published",
                "plugin_id": str(plugin.id),
                "plugin_status": plugin.status,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="deploy")
    def deploy_plugin(self, request, id=None):
        """
        Record a deployment of a published plugin in its metadata.

        POST /api/v1/developer/plugins/{id}/deploy/
        """
        plugin = self._get_lifecycle_plugin(id)
        if plugin.status != PluginStatus.AVAILABLE:
            return Response(
                {
                    "error": "plugin_not_published",
                    "detail": "publish the plugin before deploying it",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        metadata = dict(plugin.metadata_json or {})
        metadata["deployment"] = {
            "deployed_at": datetime.now(UTC).isoformat(),
            "mode": request.data.get("mode", "local"),
        }
        plugin.metadata_json = metadata
        plugin.save(update_fields=["metadata_json", "updated_at"])

        return Response(
            {
                "status": "deployed",
                "plugin_id": str(plugin.id),
                "deployment": metadata["deployment"],
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="marketplace")
    def marketplace(self, _request):
        """
        List plugins available in marketplace.

        GET /api/v1/developer/plugins/marketplace/
        """
        queryset = self.get_queryset()
        serializer = PluginSerializer(queryset, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="marketplace/usage")
    def marketplace_usage(self, _request):
        """
        Get plugin marketplace usage statistics.

        GET /api/v1/developer/plugins/marketplace/usage/
        """
        from django.db.models import Sum

        queryset = self.get_queryset()
        total = queryset.count()
        downloads = queryset.aggregate(total=Sum("download_count")) or {"total": 0}
        return Response(
            {
                "plugins_count": total,
                "total_downloads": downloads.get("total", 0) or 0,
                "usage": [],
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="execute")
    def execute(
        self, _request, id=None
    ):  # DRF detail action — lookup_field kwarg injected from URL
        """
        Execute a plugin (placeholder).

        POST /api/v1/developer/plugins/{id}/execute/
        """
        plugin = self.get_object()
        return Response(
            {
                "plugin_id": str(plugin.id),
                "status": "executed",
                "result": {},
            },
            status=status.HTTP_200_OK,
        )


class SDKDocumentationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for SDK documentation.

    Public endpoint - no authentication required.
    """

    queryset = SDKDocumentation.objects.filter(is_active=True)
    serializer_class = SDKDocumentationSerializer
    permission_classes = (AllowAny,)
    lookup_field = "id"

    def get_queryset(self):
        """Filter queryset by language and version"""
        queryset = SDKDocumentation.objects.filter(is_active=True)

        # Filter by language
        language = self.request.query_params.get("language", "all")
        if language and language != "all":
            queryset = queryset.filter(language=language)

        # Filter by version (optional)
        version = self.request.query_params.get("version")
        if version:
            queryset = queryset.filter(version=version)

        return queryset.order_by("language", "-version")

    def retrieve(self, request, *args, **kwargs):
        """Retrieve SDK documentation by ID"""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        operation_id="get_sdk_documentation",
        responses={
            200: inline_serializer(
                name="SDKDocumentationResponse",
                fields={
                    "sdk_name": serializers.CharField(),
                    "version": serializers.CharField(),
                    "documentation": serializers.CharField(),
                    "examples": serializers.ListField(),
                    "api_reference": serializers.DictField(),
                },
            ),
            404: OpenApiResponse(description="SDK documentation not found"),
        },
        tags=["Developer Experience"],
    )
    def list(self, request, *_args, **_kwargs):
        """
        Get SDK documentation and examples.

        GET /api/v1/developer/sdk/?language=python&version=1.0.0&include_examples=true

        Returns SDK documentation for the specified language and version.
        If language='all', returns documentation for all languages.
        """
        language = request.query_params.get("language", "all")
        request.query_params.get("version")
        include_examples = request.query_params.get("include_examples", "true").lower() == "true"

        queryset = self.get_queryset()

        # If specific language requested, return single SDK
        if language and language != "all":
            # get_queryset() already filtered by language, so just get first
            sdk_doc = queryset.first()
            if not sdk_doc:
                return Response(
                    {"error": f"SDK documentation not found for language: {language}"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Build response - ensure language is included as string value
            response_data = {
                "language": str(sdk_doc.language),  # Ensure it's a string, not enum
                "sdk_name": f"{sdk_doc.language.title()} SDK",
                "version": sdk_doc.version,
                "documentation": sdk_doc.documentation,
                "installation": sdk_doc.installation,
                "quick_start": sdk_doc.quick_start,
                "documentation_url": sdk_doc.documentation_url,
                "examples": sdk_doc.examples_json if include_examples else [],
                "api_reference": sdk_doc.api_reference_json or {},
            }

            return Response(response_data, status=status.HTTP_200_OK)

        # Return all SDKs
        sdk_docs = queryset.all()
        response_data = {"sdks": []}

        for sdk_doc in sdk_docs:
            sdk_data = {
                "language": sdk_doc.language,
                "sdk_name": f"{sdk_doc.language.title()} SDK",
                "version": sdk_doc.version,
                "documentation": sdk_doc.documentation,
                "installation": sdk_doc.installation,
                "quick_start": sdk_doc.quick_start,
                "documentation_url": sdk_doc.documentation_url,
                "examples": sdk_doc.examples_json if include_examples else [],
                "api_reference": sdk_doc.api_reference_json or {},
            }
            response_data["sdks"].append(sdk_data)

        return Response(response_data, status=status.HTTP_200_OK)


class DocumentationViewSet(viewsets.ViewSet):
    """
    Developer documentation (alias for SDK docs).

    GET /api/v1/developer/documentation/
    """
    serializer_class = SDKDocumentationSerializer  # W12.9: real response schema for OpenAPI

    permission_classes = (AllowAny,)

    def list(self, _request):
        """Get developer documentation (SDK docs summary)."""
        docs = SDKDocumentation.objects.filter(is_active=True).order_by("language", "-version")
        data = {
            "documentation": [
                {
                    "language": str(d.language),
                    "version": d.version,
                    "sdk_name": f"{d.language.title()} SDK",
                }
                for d in docs[:20]
            ],
        }
        return Response(data, status=status.HTTP_200_OK)


@extend_schema(
    # W12.9: class-level fallback — actions either carry their own
    # @extend_schema or return a 200 payload (service-backed shapes).
    responses={200: OpenApiResponse(description="OK")},
    request=OpenApiTypes.OBJECT,  # W12.9: free-form request body fallback
)
class PortalViewSet(viewsets.ViewSet):
    """
    Developer portal info.

    GET /api/v1/developer/portal/
    """

    permission_classes = (AllowAny,)

    def list(self, _request):
        """Get developer portal info."""
        return Response(
            {
                "name": "Developer Portal",
                "plugins_count": Plugin.objects.filter(status=PluginStatus.AVAILABLE).count(),
                "docs_available": True,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    # W12.9: class-level fallback — actions either carry their own
    # @extend_schema or return a 200 payload (service-backed shapes).
    responses={200: OpenApiResponse(description="OK")},
    request=OpenApiTypes.OBJECT,  # W12.9: free-form request body fallback
)
class APIKeysViewSet(viewsets.ViewSet):
    """API key management - GET list, POST create."""

    permission_classes = (IsAuthenticated,)

    def list(self, _request):
        """List API keys (placeholder).

        GET /api/v1/developer/api-keys/
        """
        return Response(
            {
                "results": [],
                "count": 0,
            },
            status=status.HTTP_200_OK,
        )

    def create(self, _request):
        """Generate API key (placeholder)."""
        return Response(
            {
                "key_id": str(__import__("uuid").uuid4()),
                "message": "API key generation placeholder",
            },
            status=status.HTTP_201_CREATED,
        )


# NOTE: the developer ``api-usage`` registration was REMOVED (Phase 313
# single identity — D2). The placeholder ViewSet shadowed the real BaaS
# APIUsageViewSet (same ``api-usage`` basename) so ``reverse("api-usage-list")``
# never reached the implementation that actually lists usage records. The
# real endpoint lives under the paid BaaS app and enforces authentication,
# tenant isolation, filters, and standard pagination.
