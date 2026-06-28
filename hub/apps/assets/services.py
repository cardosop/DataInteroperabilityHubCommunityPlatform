"""
Asset Service

Business logic for asset operations.
"""

from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError, IntegrityError, transaction

from hub.apps.assets.business_rules import AssetsBusinessRules
from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility, ComplianceStatus, DQStatus
from hub.apps.audit.utils import create_audit_event
from hub.apps.core.events.publisher import EventBusError
from hub.apps.core.events.service_publishers import AssetEventPublisher
from hub.apps.core.services.base import BaseService, ConflictError, NotFoundError, ValidationError
from hub.apps.core.transaction_safe import run_side_effect


class AssetService(BaseService, AssetEventPublisher):
    """
    Service for asset operations.

    Provides business logic for creating, retrieving, updating, and managing assets.
    """

    service_name = "asset_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize AssetService.

        Args:
            tenant_id: Tenant ID
            user_id: User ID
        """
        # Set attributes directly (BaseService doesn't have __init__)
        self.tenant_id = tenant_id
        self.user_id = user_id
        # Initialize event publisher
        AssetEventPublisher.__init__(self)

    def get_asset(self, asset_id: str, tenant_id: Optional[str] = None) -> Asset:
        """
        Get asset by ID.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            Asset instance

        Raises:
            NotFoundError: If asset not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        # Normalize to str so both UUID and str inputs work (e.g. from serializer validated_data)
        asset_id_str = str(asset_id) if not isinstance(asset_id, str) else asset_id
        tenant_id_str = str(effective_tenant_id) if not isinstance(effective_tenant_id, str) else effective_tenant_id

        # Validate UUID format before querying
        try:
            import uuid
            uuid.UUID(asset_id_str)
            uuid.UUID(tenant_id_str)
        except (ValueError, TypeError) as e:
            raise NotFoundError(
                f"Invalid UUID format: {str(e)}",
                code="NOT_FOUND",
                details={"asset_id": asset_id_str, "tenant_id": tenant_id_str}
            )

        return self.execute_with_metrics(
            operation="get_asset",
            tenant_id=tenant_id_str,
            func=lambda: self.get_resource_or_raise(Asset, asset_id_str, tenant_id=tenant_id_str),
        )

    def get_assets_by_status(
        self, status: AssetStatus, tenant_id: Optional[str] = None, limit: Optional[int] = None
    ) -> List[Asset]:
        """
        Get assets by status.

        Args:
            status: Asset status
            tenant_id: Tenant ID
            limit: Optional limit on results

        Returns:
            List of Asset instances
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _get_assets():
            queryset = Asset.objects.filter(tenant_id=effective_tenant_id, status=status)
            if limit:
                queryset = queryset[:limit]
            return list(queryset)

        return self.execute_with_metrics(
            operation="get_assets_by_status", tenant_id=effective_tenant_id, func=_get_assets
        )

    def is_asset_active(self, asset_id: str, tenant_id: Optional[str] = None) -> bool:
        """
        Check if asset is active.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID

        Returns:
            True if asset is active, False otherwise

        Raises:
            NotFoundError: If asset not found
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _check():
            asset = self.get_resource_or_raise(Asset, asset_id, tenant_id=effective_tenant_id)
            return asset.status == AssetStatus.ACTIVE

        return self.execute_with_metrics(
            operation="is_asset_active", tenant_id=effective_tenant_id, func=_check
        )

    def validate_asset_eligibility(
        self, asset_id: str, tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate asset eligibility for operations (e.g., marketplace publication).

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID

        Returns:
            Dictionary with validation results

        Raises:
            NotFoundError: If asset not found
            ValidationError: If asset is not eligible
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _validate():
            asset = self.get_resource_or_raise(Asset, asset_id, tenant_id=effective_tenant_id)

            validation_results = {"asset_id": str(asset.id), "eligible": True, "blockers": []}

            # Check asset status
            if asset.status != AssetStatus.ACTIVE:
                validation_results["blockers"].append(
                    f"Asset status must be ACTIVE (current: {asset.status})"
                )
                validation_results["eligible"] = False

            # Check DQ status
            if asset.dq_status != DQStatus.PASS:
                validation_results["blockers"].append(
                    f"Asset DQ status must be PASS (current: {asset.dq_status})"
                )
                validation_results["eligible"] = False

            # Check compliance status
            if asset.compliance_status != ComplianceStatus.PASS:
                validation_results["blockers"].append(
                    f"Asset compliance status must be PASS (current: {asset.compliance_status})"
                )
                validation_results["eligible"] = False

            if not validation_results["eligible"]:
                raise ValidationError(
                    f"Asset {asset_id} is not eligible", details=validation_results
                )

            return validation_results

        return self.execute_with_metrics(
            operation="validate_asset_eligibility", tenant_id=effective_tenant_id, func=_validate
        )

    @transaction.atomic
    def create_asset(
        self,
        *,
        key: str,
        name: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        description: Optional[str] = None,
        domain: Optional[str] = None,
        visibility: Optional[str] = None,
        created_by: Optional[Any] = None,
    ) -> Asset:
        """
        Create a new asset.

        Phase 250.1.G.2 — the signature is now **kwarg-only** (the
        ``*`` after ``self`` forces every parameter to be passed by
        keyword). This closes the B2-13 audit finding that callers
        were silently passing positional ``key`` / ``name`` /
        ``tenant_id`` in arbitrary orders, which made adding /
        removing parameters a silent breaking change. Strict typing
        on every parameter lets ``mypy --strict`` catch missing-
        required-arg bugs at the call site rather than at runtime.

        Args:
            key: Asset key (unique per tenant). REQUIRED.
            name: Asset name. REQUIRED.
            tenant_id: Tenant UUID; falls back to ``self.tenant_id``
                if omitted.
            user_id: User UUID; falls back to ``self.user_id``.
            description: Optional human-readable description.
            domain: Optional logical domain (e.g. ``"finance"``).
            visibility: Optional asset visibility
                (default ``AssetVisibility.INTERNAL``).
            created_by: Optional pre-resolved User instance for
                ``Asset.created_by`` — when set, takes precedence
                over the FK that ``user_id`` would resolve.

        Returns:
            Created asset instance

        Raises:
            ValidationError: If validation fails
            ConflictError: If asset with same key already exists
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")
        if not key:
            raise ValidationError("key is required")
        if not name:
            raise ValidationError("name is required")

        # Phase 250.3.B.3 — service callers passing the legacy
        # ``visibility=`` kwarg get the deprecation signals. The
        # value is otherwise discarded; the asset's derived
        # visibility comes from its (always DRAFT-on-create) status.
        if visibility is not None:
            import warnings as _warnings

            _warnings.warn(
                (
                    f"AssetService.create_asset() received the legacy "
                    f"visibility='{visibility}' kwarg. Visibility now "
                    f"derives from status (D250.4); the value is "
                    f"silently ignored. Update callers to omit the "
                    f"kwarg — it ships for removal in phase-2."
                ),
                DeprecationWarning,
                stacklevel=3,
            )
            try:
                from hub.apps.audit import event_types as _audit_event_types
                from hub.apps.audit.utils import (
                    create_audit_event as _create_audit_event,
                )
                from hub.apps.tenants.models import Tenant as _Tenant

                # ``create_audit_event`` accepts ``tenant=<Tenant>``,
                # not ``tenant_id=<uuid>``. Resolve the FK once so the
                # audit row carries the correct tenant association
                # (and so audit-replay queries that JOIN on
                # ``audit.tenant_id = tenants.id`` see the row). Falls
                # back to ``tenant=None`` when the lookup misses; the
                # ``details_json["tenant_id"]`` copy still carries the
                # raw UUID for warehouse-side analytics.
                _tenant_obj = None
                try:
                    _tenant_obj = _Tenant.objects.get(id=effective_tenant_id)
                except _Tenant.DoesNotExist:
                    pass

                _create_audit_event(
                    resource_type=_audit_event_types.ASSET_RESOURCE_TYPE,
                    action=_audit_event_types.ASSET_VISIBILITY_WRITE_DEPRECATED,
                    actor_user=created_by,
                    tenant=_tenant_obj,
                    resource_id=None,  # asset_id not yet assigned
                    result="WARNING",
                    details={
                        "tenant_id": str(effective_tenant_id)
                        if effective_tenant_id
                        else None,
                        "asset_id": None,
                        "attempted_value": str(visibility),
                        "call_site": "service.create_asset",
                        "current_status": str(AssetStatus.DRAFT),
                        "derived_visibility": str(AssetVisibility.INTERNAL),
                    },
                )
            except (ConnectionError, TimeoutError, OSError) as audit_exc:
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "asset_visibility_deprecation_audit_emit_failed",
                    extra={
                        "call_site": "service.create_asset",
                        "error": str(audit_exc),
                    },
                )
            except DatabaseError as audit_exc:
                import logging as _logging

                _logging.getLogger(__name__).error(
                    "asset_visibility_deprecation_audit_emit_db_error",
                    extra={
                        "call_site": "service.create_asset",
                        "error": str(audit_exc),
                    },
                    exc_info=True,
                )

        def _create():
            # Build validation payload (unsaved asset) and run business rules.
            # Phase 250.3.B.1 — visibility is no longer a constructor
            # kwarg; the model's ``__init__`` would absorb it via the
            # deprecation setter (which would double-emit the audit
            # row), so we deliberately omit it here.
            payload_asset = Asset(
                tenant_id=effective_tenant_id,
                key=key,
                name=name,
                description=description or "",
                domain=domain or "",
                status=AssetStatus.DRAFT,
            )
            rules = AssetsBusinessRules(
                tenant_id=effective_tenant_id,
                user_id=effective_user_id,
            )
            result = rules.validate(
                asset=payload_asset,
                validation_type="structure",
            )
            if not result.is_valid:
                raise ValidationError(
                    "; ".join(result.errors),
                    code="BUSINESS_RULES_VALIDATION",
                    details=result.details,
                )

            # Check plan limit (Phase 25.1.2, hardened Phase 113.B)
            from hub.apps.tenants.services import PlanLimitService

            plan_limit_service = PlanLimitService(
                tenant_id=effective_tenant_id,
                user_id=effective_user_id,
            )
            plan_limit_service.check_limit(
                tenant_id=effective_tenant_id,
                limit_key="max_assets",
                delta=1,
            )

            try:
                with transaction.atomic():
                    # Phase 250.3.B.1 — no ``visibility`` in the
                    # persistence kwargs; derived from status.
                    asset_kwargs: Dict[str, Any] = {
                        "tenant_id": effective_tenant_id,
                        "key": key,
                        "name": name,
                        "description": description,
                        "domain": domain,
                        "status": AssetStatus.DRAFT,
                    }
                    if created_by is not None:
                        asset_kwargs["created_by"] = created_by
                    asset = Asset(**asset_kwargs)
                    asset.full_clean()
                    asset.save()
            except IntegrityError:
                raise ConflictError(
                    f"Asset with key '{key}' already exists",
                    code="ASSET_KEY_EXISTS",
                    details={"key": key, "tenant_id": str(effective_tenant_id)},
                )
            except DjangoValidationError as e:
                if "already exists" in str(e):
                    raise ConflictError(
                        f"Asset with key '{key}' already exists",
                        code="ASSET_KEY_EXISTS",
                        details={"key": key, "tenant_id": str(effective_tenant_id)},
                    )
                raise ValidationError(
                    str(e),
                    code="VALIDATION_ERROR",
                    details={"errors": e.message_dict if hasattr(e, "message_dict") else {"__all__": e.messages}},
                )

            # Phase 250.1.G review-pass — fire ``asset.created``
            # webhook event on commit. Without this the simple
            # ``POST /assets/`` API path (which bypasses the
            # data-first workflow) never published the event;
            # webhook subscribers had to poll to detect those
            # assets. Deferred via ``transaction.on_commit`` so
            # the publish runs AFTER the @transaction.atomic block
            # commits — subscribers that GET the asset on receipt
            # always see the row.
            self._enqueue_asset_event_on_commit(
                event_type="asset.created",
                asset=asset,
                data_extra={
                    "name": asset.name,
                    "domain": asset.domain or None,
                    "status": asset.status,
                },
            )

            return asset

        return self.execute_with_metrics(
            operation="create_asset", tenant_id=effective_tenant_id, func=_create
        )

    # ------------------------------------------------------------------
    # Phase 250.2.C.1 (closes Gap 4 / B2-9) — idempotent get-or-create
    # ------------------------------------------------------------------

    def create_or_get_idempotent(
        self,
        *,
        key: str,
        name: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        description: Optional[str] = None,
        domain: Optional[str] = None,
        visibility: Optional[str] = None,
        created_by: Optional[Any] = None,
    ) -> Asset:
        """Phase 250.2.C.1 — canonical idempotent get-or-create entry.

        Returns the existing Asset row when one exists for
        ``(tenant_id, key)`` AND its status is ``DRAFT`` /
        ``ACTIVE`` / ``PUBLIC``. The retried call is a pure read —
        no business-rules re-validation, no plan-limit delta, no
        ``ASSET_CREATED`` audit row, no ``asset.created`` webhook.
        That makes a retried scheduled-ingestion run side-effect-
        free in the audit / webhook trail (Gap 4 closure).

        When the existing Asset has status ``RETIRED`` (B2-9),
        raises ``ConflictError(code="ASSET_KEY_RETIRED",
        http_status=409)`` carrying ``details={"key", "tenant_id",
        "asset_id", "current_status", "remediation"}``. The retired
        key holds an audit-history that the operator may need to
        preserve, so the resolution is operator action — not silent
        re-creation that would resurrect the retired identity.

        When no Asset exists for the (tenant, key) pair, delegates
        to :meth:`create_asset` so the structured error contract
        for the slow path is byte-identical to the
        ``POST /assets/`` API path: business-rules validation
        failures raise ``ValidationError(code="VALIDATION_ERROR")``,
        plan-limit exhaustion raises ``ValidationError(code=
        "PLAN_LIMIT_EXCEEDED")``, etc. This is the load-bearing
        claim of Phase 250.2.C.4.

        Race-safe: if a concurrent caller creates the row between
        our existence check and our save, ``create_asset`` raises
        ``ConflictError(code="ASSET_KEY_EXISTS")``. We catch that,
        re-fetch, and either return the now-existing row OR (if
        the racer's row landed as RETIRED somehow — a path that's
        not currently reachable but defensively handled) raise
        ``ASSET_KEY_RETIRED`` for consistency.

        Args:
            key: Asset key (unique per tenant). REQUIRED.
            name: Asset name. REQUIRED. Used only on the slow path
                for a brand-new row; ignored on the fast path
                (existing rows preserve their pre-existing name).
            tenant_id: Tenant UUID; falls back to ``self.tenant_id``.
            user_id: User UUID; falls back to ``self.user_id``.
            description: Slow-path description (ignored on fast path).
            domain: Slow-path domain (ignored on fast path).
            visibility: Slow-path visibility (ignored on fast path).
            created_by: Pre-resolved User instance for slow-path
                ``Asset.created_by`` FK.

        Returns:
            The existing or newly-created Asset row.

        Raises:
            ValidationError: when the inputs are malformed or the
                slow-path business-rules / plan-limit gate rejects.
                Same shape as :meth:`create_asset`.
            ConflictError: ``ASSET_KEY_RETIRED`` (409) when a
                RETIRED row holds the key, OR ``ASSET_KEY_EXISTS``
                bubbled from a non-recoverable race.
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValidationError(
                "tenant_id is required",
                code="VALIDATION_ERROR",
            )
        if not key:
            raise ValidationError("key is required")
        if not name:
            raise ValidationError("name is required")

        existing = self._lookup_existing_or_raise_if_retired(
            tenant_id=effective_tenant_id,
            key=key,
        )
        if existing is not None:
            return existing

        # Slow path — delegate to the canonical pipeline.
        try:
            return self.create_asset(
                tenant_id=effective_tenant_id,
                user_id=user_id,
                key=key,
                name=name,
                description=description,
                domain=domain,
                visibility=visibility,
                created_by=created_by,
            )
        except ConflictError as exc:
            # Race: another caller created the row between our
            # lookup and our create. Re-fetch and treat as fast-
            # path. If the racer's row is RETIRED, surface the
            # canonical RETIRED rejection rather than the
            # ``ASSET_KEY_EXISTS`` shape (the operator-facing
            # rejection is identical regardless of whether the
            # RETIRED row was already there or appeared during the
            # race).
            if exc.code != "ASSET_KEY_EXISTS":
                raise
            existing = self._lookup_existing_or_raise_if_retired(
                tenant_id=effective_tenant_id,
                key=key,
            )
            if existing is None:
                # The race resolved to "no row" (e.g., racer
                # rolled back); re-raise the original conflict
                # so the caller has actionable context.
                raise
            return existing

    def _lookup_existing_or_raise_if_retired(
        self,
        *,
        tenant_id: str,
        key: str,
    ) -> Optional[Asset]:
        """Internal helper for :meth:`create_or_get_idempotent`.

        Returns the matching Asset row when status is non-RETIRED,
        ``None`` when no row matches, and raises ``ConflictError(
        code="ASSET_KEY_RETIRED")`` when a RETIRED row holds the
        key.
        """
        try:
            existing = Asset.objects.get(tenant_id=tenant_id, key=key)
        except Asset.DoesNotExist:
            return None

        if existing.status == AssetStatus.RETIRED:
            raise ConflictError(
                f"Asset key '{key}' is held by a RETIRED asset; "
                f"operator must transition it or use a new key.",
                code="ASSET_KEY_RETIRED",
                details={
                    "key": key,
                    "tenant_id": str(tenant_id),
                    "asset_id": str(existing.id),
                    "current_status": existing.status,
                    "remediation": (
                        "Either issue a new asset key OR run an "
                        "admin transition to a non-RETIRED status "
                        "before re-attempting auto-create. The "
                        "RETIRED row is preserved for audit "
                        "history; silent resurrection is refused."
                    ),
                },
            )
        return existing

    def _enqueue_asset_event_on_commit(
        self,
        *,
        event_type: str,
        asset: Asset,
        data_extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Defer an ``asset.*`` event publish to the next outer commit.

        Phase 250.1.G review-pass — both the workflow path
        (``AssetCreationWorkflow._enqueue_asset_event``) and the
        AssetService path use the same on-commit deferral pattern
        so subscribers see exactly one event per actual asset state
        change, never one per nested savepoint that might be rolled
        back.

        Failures of the publish are logged at WARNING; we never
        want a webhook outage to fail an asset operation. The
        EventPublisher itself dedupes via the deduplication-key
        cache, so a same-event re-publish in a retry window is a
        no-op.
        """
        from hub.apps.core.events.publisher import EventPublisher

        publisher = EventPublisher(
            service_name="asset_service",
            tenant_id=str(asset.tenant_id) if asset.tenant_id else None,
            user_id=self.user_id,
        )
        payload: Dict[str, Any] = {"asset_id": str(asset.id)}
        if data_extra:
            payload.update({k: v for k, v in data_extra.items() if v is not None})

        def _publish() -> None:
            import logging as _logging
            try:
                publisher.publish(event_type=event_type, data=payload)
            except EventBusError as exc:  # event-bus failure — best-effort
                _logging.getLogger(__name__).warning(
                    "asset_webhook_publish_failed",
                    extra={
                        "event_type": event_type,
                        "asset_id": str(asset.id),
                        "error": str(exc),
                    },
                )

        transaction.on_commit(_publish)

    @transaction.atomic
    def update_asset(
        self,
        asset_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        version: Optional[int] = None,
        status: Optional[str] = None,
        **kwargs,
    ) -> Asset:
        """
        Update an asset.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID
            user_id: User ID
            version: Expected version (for optimistic locking)
            status: Updated status (optional)
            **kwargs: Additional fields to update

        Returns:
            Updated asset instance

        Raises:
            NotFoundError: If asset not found
            ConflictError: If version mismatch
            ValidationError: If validation fails (e.g., activation blocked)
        """
        effective_tenant_id = tenant_id or self.tenant_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _update():
            try:
                # Lock the row while checking/applying optimistic version so
                # concurrent PATCH requests cannot both pass the same version.
                asset = Asset.objects.select_for_update().get(
                    id=asset_id,
                    tenant_id=effective_tenant_id,
                )
            except Asset.DoesNotExist:
                raise NotFoundError(
                    f"Asset with id {asset_id} not found",
                    details={"resource_type": "Asset", "resource_id": asset_id},
                )

            # Capture pre-update status snapshot so the post-commit
            # ``asset.updated`` event can carry the lifecycle
            # transition (Phase 250.1.G review-pass).
            previous_status = asset.status

            # Check version if provided (optimistic locking)
            if version is not None and asset.version != version:
                raise ConflictError(
                    f"Asset version mismatch: expected {version}, got {asset.version}",
                    code="ASSET_CONCURRENT_MODIFICATION",
                    details={"expected_version": version, "current_version": asset.version},
                )

            # Run business rules for status/lifecycle when status is being updated
            if status is not None:
                valid_statuses = [s[0] for s in AssetStatus.choices]
                if status not in valid_statuses:
                    raise ValidationError(
                        f"Invalid status: {status}", details={"valid_statuses": valid_statuses}
                    )
                rules = AssetsBusinessRules(
                    tenant_id=effective_tenant_id,
                    user_id=user_id or self.user_id,
                )
                result = rules.validate(
                    asset=asset,
                    validation_type="lifecycle",
                    old_status=asset.status,
                    new_status=status,
                )
                if not result.is_valid:
                    raise ValidationError(
                        "; ".join(result.errors),
                        code="BUSINESS_RULES_VALIDATION",
                        details=result.details,
                    )
                asset.status = status

            # Update other fields
            for field, value in kwargs.items():
                if hasattr(asset, field):
                    setattr(asset, field, value)

            # Increment version
            asset.version += 1
            try:
                asset.full_clean()
            except DjangoValidationError as e:
                raise ValidationError(
                    str(e),
                    code="VALIDATION_ERROR",
                    details={"errors": e.message_dict if hasattr(e, "message_dict") else {"__all__": e.messages}},
                )
            asset.save()

            # Phase 250.1.G review-pass — fire ``asset.updated``
            # (or ``asset.activated`` when status moved to ACTIVE)
            # webhook event on commit. ``previous_status`` and
            # ``new_status`` reflect the lifecycle transition; the
            # ``changes`` dict carries the field-level diff so
            # subscribers can fast-path "was the X field touched?"
            # without diffing themselves.
            self._enqueue_asset_event_on_commit(
                event_type="asset.updated",
                asset=asset,
                data_extra={
                    "changes": {
                        "fields": list(kwargs.keys()),
                        "version": asset.version,
                    },
                    "previous_status": (
                        previous_status if previous_status else None
                    ),
                    "new_status": asset.status,
                },
            )
            # When a status update transitions to ACTIVE, ALSO emit
            # ``asset.activated`` so subscribers that filter on
            # ``asset.activated`` (rather than the generic
            # ``asset.updated``) catch the activation. The two
            # events fire as separate on_commit callbacks in
            # registration order: ``asset.updated`` first, then
            # ``asset.activated``.
            if (
                status is not None
                and status == AssetStatus.ACTIVE
                and previous_status != AssetStatus.ACTIVE
            ):
                self._enqueue_asset_event_on_commit(
                    event_type="asset.activated",
                    asset=asset,
                    data_extra={
                        "activation_reason": "explicit_api_update",
                        "dq_status": getattr(asset, "dq_status", None),
                        "compliance_status": getattr(
                            asset, "compliance_status", None
                        ),
                    },
                )

            return asset

        return self.execute_with_metrics(
            operation="update_asset", tenant_id=effective_tenant_id, func=_update
        )

    @transaction.atomic
    def delete_asset(
        self, asset_id: str, tenant_id: Optional[str] = None, user_id: Optional[str] = None
    ) -> None:
        """
        Delete an asset (soft delete: set status to RETIRED).

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID
            user_id: User ID

        Raises:
            NotFoundError: If asset not found
        """
        effective_tenant_id = tenant_id or self.tenant_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _delete():
            # ``get_resource_or_raise`` returns ``models.Model``; we
            # narrow to ``Asset`` so mypy / pyright can verify the
            # ``.status`` / ``.updated_at`` accesses below.
            asset_obj = self.get_resource_or_raise(Asset, asset_id, tenant_id=effective_tenant_id)
            assert isinstance(asset_obj, Asset)
            asset: Asset = asset_obj

            # Unpublish any marketplace listings BEFORE retirement validation.
            # Retirement validation blocks if there are active listings; unpublishing first
            # allows retirement to proceed and matches expected behavior (retire unpublishes).
            from hub.apps.marketplace.models import Listing, ListingStatus

            Listing.objects.filter(asset=asset, status=ListingStatus.PUBLISHED).update(
                status=ListingStatus.UNLISTED
            )

            # Run business rules for deletion (retirement requirements)
            rules = AssetsBusinessRules(
                tenant_id=effective_tenant_id,
                user_id=user_id or self.user_id,
            )
            result = rules.validate(
                asset=asset,
                validation_type="lifecycle",
                old_status=asset.status,
                new_status=AssetStatus.RETIRED,
            )
            if not result.is_valid:
                raise ValidationError(
                    "; ".join(result.errors),
                    code="BUSINESS_RULES_VALIDATION",
                    details=result.details,
                )

            asset.status = AssetStatus.RETIRED
            asset.save()

            # Phase 250.1.G review-pass — fire ``asset.retired``
            # webhook event on commit. The retirement reason is
            # the explicit-soft-delete API path; subscribers that
            # need to react (cleanup downstream caches, revoke
            # access, archive marketplace listings) get a single
            # canonical event rather than having to diff
            # ``asset.updated`` events for status transitions.
            self._enqueue_asset_event_on_commit(
                event_type="asset.retired",
                asset=asset,
                data_extra={
                    "retirement_reason": "explicit_api_delete",
                    "retired_at": (
                        asset.updated_at.isoformat()
                        if getattr(asset, "updated_at", None)
                        else None
                    ),
                },
            )

        return self.execute_with_metrics(
            operation="delete_asset", tenant_id=effective_tenant_id, func=_delete
        )

    @transaction.atomic
    def link_odps_contract_to_asset(
        self,
        asset_id: str,
        odps_contract_id: Optional[str] = None,
        odps_raw: Optional[str] = None,
        odps_format: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> "Contract":
        """
        Link ODPS contract to asset (Task 8.1.2).

        Uses ODPSService to create or link an ODPS contract to the asset.
        This method coordinates asset-ODPS contract relationships.

        Args:
            asset_id: Asset ID to link ODPS contract to
            odps_contract_id: Optional existing ODPS contract ID to link
            odps_raw: Optional ODPS document content (if creating new ODPS contract)
            odps_format: Optional ODPS document format (required if odps_raw provided)
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: User ID (uses service user_id if not provided)

        Returns:
            Linked ODPS Contract instance

        Raises:
            NotFoundError: If asset or contract not found
            ValidationError: If validation fails
        """
        effective_tenant_id = tenant_id or self.tenant_id
        effective_user_id = user_id or self.user_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _link():
            from hub.apps.contracts.models import Contract, OriginalSpecType
            from hub.apps.contracts.services import ODPSService

            # Get asset
            asset = self.get_resource_or_raise(Asset, asset_id, tenant_id=effective_tenant_id)

            # Use ODPSService to create or link ODPS contract
            odps_service = ODPSService(tenant_id=effective_tenant_id, user_id=effective_user_id)

            if odps_contract_id:
                # Link existing ODPS contract
                contract_service = odps_service  # ODPSService can get contract
                from hub.apps.contracts.services import ContractService

                contract_service = ContractService(
                    tenant_id=effective_tenant_id, user_id=effective_user_id
                )
                odps_contract = contract_service.get_contract(
                    contract_id=odps_contract_id, tenant_id=effective_tenant_id
                )

                # Verify it's an ODPS contract
                if odps_contract.original_spec_type != OriginalSpecType.ODPS:
                    raise ValidationError(
                        f"Contract {odps_contract_id} is not an ODPS contract",
                        code="INVALID_CONTRACT_TYPE",
                    )

                # Link to asset
                odps_contract.asset = asset

                # Calculate version
                latest_contract = (
                    Contract.objects.filter(tenant_id=effective_tenant_id, asset=asset)
                    .order_by("-version")
                    .first()
                )
                odps_contract.version = (latest_contract.version + 1) if latest_contract else 1
                odps_contract.save(update_fields=["asset", "version"])

                return odps_contract
            elif odps_raw:
                # Create new ODPS contract and link to asset
                odps_contract = odps_service.create_odps(
                    odps_raw=odps_raw,
                    odps_format=odps_format or "json",
                    tenant_id=effective_tenant_id,
                    user_id=effective_user_id,
                    asset_id=asset_id,
                )
                # Phase 70.1: Audit event for ODPS contract link
                try:
                    create_audit_event(
                        resource_type="ASSET",
                        action="ASSET_ODPS_LINKED",
                        resource_id=str(asset_id),
                        details={"odps_contract_id": str(odps_contract.id)},
                    )
                except DatabaseError:
                    pass  # best-effort audit — DB outage must not block ODPS linking
                return odps_contract
            else:
                raise ValidationError(
                    "Either odps_contract_id or odps_raw must be provided",
                    code="ODPS_SOURCE_REQUIRED",
                )

        return self.execute_with_metrics(
            operation="link_odps_contract_to_asset", tenant_id=effective_tenant_id, func=_link
        )

    def get_odps_contracts_for_asset(
        self, asset_id: str, tenant_id: Optional[str] = None
    ) -> List["Contract"]:
        """
        Get all ODPS contracts linked to an asset (Task 8.1.2).

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)

        Returns:
            List of ODPS Contract instances linked to the asset

        Raises:
            NotFoundError: If asset not found
        """
        effective_tenant_id = tenant_id or self.tenant_id

        if not effective_tenant_id:
            raise ValidationError("tenant_id is required")

        def _get_contracts():
            from hub.apps.contracts.models import Contract, OriginalSpecType

            # Get asset
            asset = self.get_resource_or_raise(Asset, asset_id, tenant_id=effective_tenant_id)

            # Get all ODPS contracts linked to asset
            odps_contracts = Contract.objects.filter(
                tenant_id=effective_tenant_id, asset=asset, original_spec_type=OriginalSpecType.ODPS
            ).order_by("-version")

            return list(odps_contracts)

        return self.execute_with_metrics(
            operation="get_odps_contracts_for_asset",
            tenant_id=effective_tenant_id,
            func=_get_contracts,
        )
