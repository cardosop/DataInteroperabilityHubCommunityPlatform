"""
Asset Serializers
"""

import re

from rest_framework import serializers

# Phase 226 G7a — canonical IRI exposure for SDK + dereferenceability proofs.
# Phase 313.1 — imported from core so the core app never imports paid code.
from hub.apps.core.identifiers import canonical_iri_for

from .models import Asset, AssetStatus, AssetVisibility

# Asset keys are user-facing tenant-scoped identifiers used in URLs, contract
# bindings, and ODPS payloads. They must be lowercase alphanumeric with optional
# single hyphens between segments — no underscores, uppercase, or punctuation —
# so the same value renders identically across UI, API, and downstream systems.
_ASSET_KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_asset_key(value: str) -> str:
    """Enforce the asset-key format (lowercase, digits, single hyphens)."""
    if not _ASSET_KEY_RE.match(value or ""):
        raise serializers.ValidationError(
            "Invalid key format: must be lowercase alphanumeric with hyphens "
            "between segments (e.g. 'my-asset-1'). Underscores, uppercase, and "
            "other punctuation are not allowed."
        )
    return value


class AssetSerializer(serializers.ModelSerializer):
    """Serializer for Asset model"""

    contract_id = serializers.SerializerMethodField()
    dataset_id = serializers.SerializerMethodField()
    # Phase 250.3.B.1 — ``visibility`` is now a derived property on
    # the Asset model (PUBLIC iff status==PUBLIC, else INTERNAL). It
    # is no longer a stored CharField, so DRF's ``ModelSerializer``
    # auto-discovery can't bind it — we expose it explicitly via a
    # SerializerMethodField that calls the model property.
    visibility = serializers.SerializerMethodField(
        help_text=(
            "DERIVED visibility (Phase 250.3.B / D250.4): PUBLIC iff "
            "status==PUBLIC, else INTERNAL. The legacy stored column "
            "is being removed in phase-2 — clients SHOULD read this "
            "field but treat it as read-only."
        ),
    )
    canonical_iri = serializers.SerializerMethodField(
        help_text=(
            "Canonical Linked Data IRI: {SEMANTIC_BASE_IRI}/id/asset/{id}. "
            "Stable identifier for JSON-LD dereference, SPARQL queries, and "
            "cross-system references. See Phase 226 G7a."
        )
    )
    # Phase 231.3 (AUDIT.5) — exposes the most recent SUCCEEDED
    # ComplianceRun for this asset so the Asset detail page can
    # surface the latest passing compliance summary without an
    # extra API call.  Returns ``None`` when only FAILED runs exist
    # (or when the asset has never been scanned).
    latest_compliance_run = serializers.SerializerMethodField(
        help_text=(
            "Latest SUCCEEDED ComplianceRun summary for this asset "
            "(status, risk_level, overall_status, allowed_to_store, "
            "completed_at).  None when no SUCCEEDED run exists."
        )
    )

    class Meta:
        model = Asset
        fields = [
            "id",
            "tenant",
            "key",
            "name",
            "description",
            "domain",
            "source_type",
            "status",
            "visibility",
            "dq_status",
            "compliance_status",
            # Phase 250.7.A.1 — semantic_status surfaces the
            # post-activation degradation state for the SPA's
            # SemanticDegradedBanner.
            "semantic_status",
            "version",
            "created_by",
            "created_at",
            "updated_at",
            "contract_id",
            "dataset_id",
            "canonical_iri",
            "latest_compliance_run",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "version",
            "visibility",  # 250.3.B — derived from status; never accept on input
            "dq_status",
            "compliance_status",
            "semantic_status",  # 250.7.A — workflow-managed; never client-writable
            "created_by",
            "created_at",
            "updated_at",
            "contract_id",
            "dataset_id",
            "canonical_iri",
            "latest_compliance_run",
        ]

    def get_visibility(self, obj) -> str:
        """Return the derived visibility from the Asset model property."""
        return obj.visibility

    def get_contract_id(self, obj):
        """Get the ID of the active contract for this asset"""
        try:
            active_contract = obj.contracts.filter(status="ACTIVE").first()
            if active_contract:
                return str(active_contract.id)
            # If no active contract, return the latest contract
            latest_contract = obj.contracts.order_by("-created_at").first()
            if latest_contract:
                return str(latest_contract.id)
        except (AttributeError, TypeError, ValueError):
            pass
        return None

    def get_dataset_id(self, obj):
        """Get the ID of the latest dataset for this asset"""
        try:
            # Get latest dataset by version (or created_at if version not set)
            latest_dataset = obj.datasets.order_by("-version", "-created_at").first()
            if latest_dataset:
                return str(latest_dataset.id)
        except (AttributeError, TypeError, ValueError):
            pass
        return None

    def get_canonical_iri(self, obj) -> str:
        """Phase 226 G7a — JSON-LD canonical IRI for this asset.

        Dereferenceable as JSON-LD via the 303 handler at
        `/api/v1/semantic/id/asset/{id}`. Always present on a persisted
        Asset (id is a UUID set on save).
        """
        return canonical_iri_for("asset", obj.id)

    def get_latest_compliance_run(self, obj) -> dict | None:
        """Phase 231.3 (AUDIT.5) — latest SUCCEEDED ComplianceRun.

        Returns a summary dict for the most recent SUCCEEDED run, or
        ``None`` when only FAILED / non-terminal runs exist (or the
        asset has never been scanned).  FAILED runs are explicitly
        excluded so the Asset detail page doesn't surface a transient
        failure as the authoritative compliance signal.

        Uses Python-side filtering on the prefetched queryset rather
        than ``.filter().first()`` — Django's ``.filter()`` on a
        related manager always issues a fresh query, bypassing the
        ``prefetch_related('compliance_runs')`` in the view queryset
        and producing an N+1 query storm on list endpoints.
        """
        from hub.apps.compliance.models import ComplianceRunStatus

        all_runs = obj.compliance_runs.all()
        succeeded = [
            r for r in all_runs if r.status == ComplianceRunStatus.SUCCEEDED
        ]
        if not succeeded:
            return None
        latest = max(succeeded, key=lambda r: r.completed_at or r.created_at)
        return {
            "id": str(latest.id),
            "status": latest.status,
            "risk_level": latest.risk_level,
            "overall_status": latest.overall_status,
            "allowed_to_store": latest.allowed_to_store,
            "completed_at": latest.completed_at.isoformat()
            if latest.completed_at
            else None,
        }


class AssetCreateSerializer(serializers.Serializer):
    """Serializer for asset creation"""

    key = serializers.CharField(
        max_length=255,
        help_text="Human-friendly identifier, unique per tenant. Must be lowercase alphanumeric with hyphens.",
        validators=[validate_asset_key],
    )
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    domain = serializers.CharField(
        max_length=100, required=False, allow_blank=True, allow_null=True
    )
    # Phase 250.3.B — visibility is accepted for backwards compat
    # but MUST NOT have a default. A default would inject a legacy
    # value into every create, triggering the deprecation signal on
    # every POST even when the client didn't send it.
    visibility = serializers.ChoiceField(
        choices=AssetVisibility.choices, required=False
    )


class AssetUpdateSerializer(serializers.Serializer):
    """Serializer for asset update"""

    name = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    domain = serializers.CharField(
        max_length=100, required=False, allow_blank=True, allow_null=True
    )
    status = serializers.ChoiceField(choices=AssetStatus.choices, required=False)
    # Phase 250.3.B.4 — ``visibility`` is still ACCEPTED in the
    # request body for phase-1 backwards compat, but is silently
    # ignored on save (and a deprecation warning + audit row fire
    # via the model setter). Removing the serializer field would
    # 400 pre-phase-1 clients which is too aggressive for phase 1.
    # Phase 2 removes this field entirely.
    visibility = serializers.ChoiceField(
        choices=AssetVisibility.choices,
        required=False,
        help_text=(
            "DEPRECATED (Phase 250.3.B / D250.4): writes are silently "
            "ignored. Visibility derives from ``status`` — set "
            "``status=PUBLIC`` to make an asset public."
        ),
    )
    version = serializers.IntegerField(
        required=False,
        help_text=(
            "Deprecated fallback for optimistic locking. PATCH now uses "
            "If-Match header and this field is accepted only for backward compatibility."
        ),
    )

    def save(self, instance=None):
        """
        Update the asset instance with validated data.

        Args:
            instance: Asset instance to update (uses self.instance if not provided)

        Returns:
            Updated Asset instance
        """
        # Use instance from constructor if not provided
        if not instance:
            instance = self.instance

        if not instance:
            raise ValueError("Instance is required for AssetUpdateSerializer.save()")

        # Update fields
        if "name" in self.validated_data:
            instance.name = self.validated_data["name"]
        if "description" in self.validated_data:
            instance.description = self.validated_data["description"]
        if "domain" in self.validated_data:
            instance.domain = self.validated_data["domain"]
        if "status" in self.validated_data:
            instance.status = self.validated_data["status"]
        # Phase 250.3.B.4 — assigning to ``instance.visibility`` routes
        # through the model's deprecation setter (DeprecationWarning +
        # ASSET_VISIBILITY_WRITE_DEPRECATED audit) and is a no-op for
        # the persisted state. We still call the setter (instead of
        # silently discarding) so the deprecation telemetry captures
        # PATCH-via-API call sites — without this, the dashboards
        # would only see in-process Python writes and miss the
        # caller-side adoption signal.
        if "visibility" in self.validated_data:
            instance.visibility = self.validated_data["visibility"]

        # Save and return
        instance.save()
        return instance


class DataFirstAssetCreateSerializer(serializers.Serializer):
    """Serializer for data-first asset creation (POST /api/v1/assets/data-first/)."""

    file_id = serializers.UUIDField(help_text="ID of the uploaded file")
    key = serializers.CharField(
        max_length=255,
        help_text="Asset key, unique per tenant. Must be lowercase alphanumeric with hyphens.",
        validators=[validate_asset_key],
    )
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    domain = serializers.CharField(
        max_length=100, required=False, allow_blank=True, allow_null=True
    )
    # Phase 250.3.B — visibility is accepted for backwards compat
    # but MUST NOT have a default. A default would inject a legacy
    # value into every create, triggering the deprecation signal on
    # every POST even when the client didn't send it.
    visibility = serializers.ChoiceField(
        choices=AssetVisibility.choices, required=False
    )


class AttachDatasetSerializer(serializers.Serializer):
    """Serializer for attaching dataset to asset"""

    dataset_id = serializers.UUIDField(help_text="ID of the dataset to attach")


class AttachContractSerializer(serializers.Serializer):
    """Serializer for attaching contract to asset"""

    contract_id = serializers.UUIDField(help_text="ID of the contract to attach")


class ExternalResourceSerializer(serializers.Serializer):
    """Serializer for external resource reference"""

    id = serializers.UUIDField(read_only=True)
    resource_id = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    url = serializers.URLField(read_only=True)
    format = serializers.CharField(read_only=True)
    size_bytes = serializers.IntegerField(read_only=True, allow_null=True)
    marketplace_type = serializers.CharField(read_only=True)
    metadata = serializers.DictField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    # Download status fields
    is_downloaded = serializers.BooleanField(
        read_only=True, help_text="Whether resource has been downloaded"
    )
    file_id = serializers.UUIDField(
        read_only=True, allow_null=True, help_text="File ID if downloaded"
    )
    dataset_id = serializers.UUIDField(
        read_only=True, allow_null=True, help_text="Dataset ID if downloaded"
    )


class BatchDownloadSerializer(serializers.Serializer):
    """Serializer for batch download request"""

    resource_ids = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        max_length=100,
        help_text="List of resource IDs to download (max 100)",
    )


class ResourceDownloadResponseSerializer(serializers.Serializer):
    """Serializer for resource download response"""

    resource_id = serializers.CharField()
    status = serializers.CharField(help_text="Download status: success, failed, skipped")
    file_id = serializers.UUIDField(allow_null=True, help_text="File ID if download succeeded")
    dataset_id = serializers.UUIDField(
        allow_null=True, help_text="Dataset ID if download succeeded"
    )
    error = serializers.CharField(
        allow_null=True, allow_blank=True, help_text="Error message if download failed"
    )
    message = serializers.CharField(allow_null=True, allow_blank=True, help_text="Status message")
