"""
Developer Experience Views

REST API views for developer experience endpoints (plugins, SDK documentation).
"""

import logging

from django.db.models import Q
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Plugin, PluginCategory, PluginStatus, SDKDocumentation, SDKLanguage
from .serializers import PluginSerializer, SDKDocumentationSerializer

logger = logging.getLogger(__name__)


class PluginViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for plugin marketplace.

    Public endpoint - no authentication required.
    """

    queryset = Plugin.objects.filter(status=PluginStatus.AVAILABLE)
    serializer_class = PluginSerializer
    permission_classes = [AllowAny]
    lookup_field = "id"

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


class SDKDocumentationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for SDK documentation.

    Public endpoint - no authentication required.
    """

    queryset = SDKDocumentation.objects.filter(is_active=True)
    serializer_class = SDKDocumentationSerializer
    permission_classes = [AllowAny]
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
    def list(self, request, *args, **kwargs):
        """
        Get SDK documentation and examples.

        GET /api/v1/developer/sdk/?language=python&version=1.0.0&include_examples=true

        Returns SDK documentation for the specified language and version.
        If language='all', returns documentation for all languages.
        """
        language = request.query_params.get("language", "all")
        version = request.query_params.get("version")
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
