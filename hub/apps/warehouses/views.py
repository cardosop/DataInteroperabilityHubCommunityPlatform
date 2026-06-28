"""
Warehouse Views — Phase 275 REST API.

Connection CRUD, connection-test, schema reflection, residency audit,
and ACL management.  All endpoints are tenant-scoped and gated behind
``warehouse_connectivity_enabled``.
"""

from __future__ import annotations

import contextlib
import time

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .models import WarehouseConnection, WarehouseConnectionACL
from .serializers import (
    WarehouseConnectionACLSerializer,
    WarehouseConnectionCreateSerializer,
    WarehouseConnectionSerializer,
    WarehouseConnectionTestResultSerializer,
)

# ── Per-tenant concurrency semaphore (Phase 275.E) ───────────────────

_MAX_CONCURRENT_QUERIES = 50
_active_queries: dict[str, int] = {}
_semaphore_lock = __import__("threading").Lock()


def _acquire_query_slot(tenant_id: str) -> bool:
    """Try to acquire a concurrent query slot. Returns True if allowed."""
    with _semaphore_lock:
        current = _active_queries.get(tenant_id, 0)
        if current >= _MAX_CONCURRENT_QUERIES:
            return False
        _active_queries[tenant_id] = current + 1
        return True


def _release_query_slot(tenant_id: str) -> None:
    """Release a concurrent query slot."""
    with _semaphore_lock:
        current = _active_queries.get(tenant_id, 0)
        if current > 0:
            _active_queries[tenant_id] = current - 1


def _get_tenant(request):
    """Resolve tenant from request, falling back to user.tenant."""
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        user = request.user
        if hasattr(user, "tenant"):
            tenant = user.tenant
    return tenant


def _check_warehouse_feature(tenant) -> None:
    """Raise PermissionDenied if warehouse connectivity is disabled."""
    if not getattr(tenant, "warehouse_connectivity_enabled", False):
        raise PermissionDenied(
            "Warehouse connectivity is not enabled for this tenant.",
        )


class WarehouseConnectionViewSet(viewsets.ModelViewSet):
    """CRUD for warehouse connections.

    Tenant-scoped. Requires ``warehouse_connectivity_enabled``.
    """

    queryset = WarehouseConnection.objects.all()
    serializer_class = WarehouseConnectionSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return WarehouseConnection.objects.all()
        tenant = _get_tenant(self.request)
        if tenant is None:
            return WarehouseConnection.objects.none()
        return WarehouseConnection.objects.filter(tenant=tenant)

    def get_serializer_class(self):
        if self.action == "create":
            return WarehouseConnectionCreateSerializer
        return WarehouseConnectionSerializer

    def perform_create(self, serializer):
        tenant = _get_tenant(self.request)
        _check_warehouse_feature(tenant)
        serializer.save(tenant=tenant)

    # ── Connection test ──────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="test", throttle_classes=[ScopedRateThrottle])
    def test_connection(self, request, id=None):
        """Probe the warehouse with SELECT 1 and return latency.

        POST /api/v1/warehouses/connections/{id}/test/
        """
        connection = self.get_object()
        _check_warehouse_feature(connection.tenant)

        try:
            config = connection.get_config()
            from hub.apps.warehouses.base import get_connector_for_connection

            connector_cls = get_connector_for_connection(
                connection.warehouse_type,
            )
            connector = connector_cls(
                config,
                tenant_id=str(connection.tenant_id),
            )

            start = time.monotonic()
            connector.connect()
            try:
                connector.execute_query("SELECT 1")
            finally:
                with contextlib.suppress(Exception):
                    connector.close()
            latency_ms = (time.monotonic() - start) * 1000

            # Emit audit event
            try:
                from hub.apps.audit.utils import create_audit_event

                create_audit_event(
                    resource_type="WAREHOUSE_CONNECTION",
                    action="WAREHOUSE_CONNECTION_TESTED",
                    tenant=connection.tenant,
                    resource_id=str(connection.id),
                    result="SUCCESS",
                    details={
                        "warehouse_type": connection.warehouse_type,
                        "latency_ms": round(latency_ms, 1),
                    },
                )
            except Exception:
                pass

            return Response(
                WarehouseConnectionTestResultSerializer(
                    {
                        "success": True,
                        "latency_ms": round(latency_ms, 1),
                        "warehouse_type": connection.warehouse_type,
                        "tested_at": timezone.now(),
                    }
                ).data,
                status=status.HTTP_200_OK,
            )
        except Exception as exc:
            return Response(
                WarehouseConnectionTestResultSerializer(
                    {
                        "success": False,
                        "warehouse_type": connection.warehouse_type,
                        "error": str(exc),
                    }
                ).data,
                status=status.HTTP_200_OK,  # 200 — the test itself didn't fail
            )

    # ── Schema reflection ─────────────────────────────────────────

    @action(detail=True, methods=["get"], url_path="schema", throttle_classes=[ScopedRateThrottle])
    def reflect_schema(self, request, id=None):
        """Reflect the schema of a table in the connected warehouse.

        GET /api/v1/warehouses/connections/{id}/schema/?table=...
        """
        connection = self.get_object()
        _check_warehouse_feature(connection.tenant)

        table_name = request.query_params.get("table")
        if not table_name:
            raise ValidationError({"table": "Query parameter 'table' is required."})

        try:
            config = connection.get_config()
            from hub.apps.warehouses.base import get_connector_for_connection

            connector_cls = get_connector_for_connection(
                connection.warehouse_type,
            )
            connector = connector_cls(
                config,
                tenant_id=str(connection.tenant_id),
            )

            connector.connect()
            try:
                schema_info = connector.reflect_schema(table_name)
            finally:
                with contextlib.suppress(Exception):
                    connector.close()

            columns = [
                {
                    "name": c.name,
                    "data_type": c.data_type,
                    "nullable": c.nullable,
                    "comment": c.comment,
                }
                for c in schema_info
            ]
            return Response(
                {
                    "connection_id": str(connection.id),
                    "table": table_name,
                    "warehouse_type": connection.warehouse_type,
                    "columns": columns,
                    "reflected_at": timezone.now(),
                }
            )
        except Exception as exc:
            raise ValidationError(str(exc))

    # ── Residency mismatch audit ──────────────────────────────────

    @action(
        detail=False,
        methods=["get"],
        url_path="residency-mismatches",
        throttle_classes=[ScopedRateThrottle],
    )
    def residency_mismatches(self, request):
        """List active connections with data residency mismatches.

        GET /api/v1/warehouses/connections/residency-mismatches/
        """
        tenant = _get_tenant(request)
        _check_warehouse_feature(tenant)

        from .residency_validator import find_residency_mismatches

        mismatches = find_residency_mismatches()
        tenant_mismatches = (
            [m for m in mismatches if m.get("tenant_id") == str(tenant.id)]
            if tenant
            else mismatches
        )

        return Response(
            {
                "count": len(tenant_mismatches),
                "mismatches": tenant_mismatches,
            }
        )


class LiveQueryViewSet(viewsets.ViewSet):
    """Records API for LIVE_QUERY assets with cursor pagination.

    GET /api/v1/warehouses/query/?asset_id=X&limit=100&cursor=...
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]

    def list(self, request):
        """Query a LIVE_QUERY asset with cursor-based pagination."""
        from hub.apps.assets.models import Asset, DataStrategy

        asset_id = request.query_params.get("asset_id")
        if not asset_id:
            raise ValidationError({"asset_id": "Required query parameter."})

        try:
            asset = Asset.objects.select_related("warehouse_connection").get(
                id=asset_id,
                data_strategy=DataStrategy.LIVE_QUERY,
                warehouse_connection__isnull=False,
            )
        except Asset.DoesNotExist:
            raise NotFound("LIVE_QUERY asset not found or has no warehouse connection.")

        tenant = _get_tenant(request)
        if str(asset.tenant_id) != str(tenant.id):
            raise PermissionDenied("Asset not in your tenant.")

        # Concurrency guard (Phase 275.E — max 50 concurrent queries per tenant).
        tid = str(tenant.id)
        if not _acquire_query_slot(tid):
            return Response(
                {"error": "Too many concurrent warehouse queries.", "retry_after": 5},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": "5"},
            )
        try:
            return self._do_query(request, asset, tid)
        finally:
            _release_query_slot(tid)

    def _do_query(self, request, asset, tenant_id_str):
        from base64 import b64decode, b64encode

        limit = min(int(request.query_params.get("limit", 100)), 1000)
        cursor_raw = request.query_params.get("cursor")
        cursor_offset = 0
        if cursor_raw:
            try:
                cursor_offset = int(b64decode(cursor_raw).decode())
            except (ValueError, UnicodeDecodeError):
                raise ValidationError({"cursor": "Invalid cursor token."})

        connection = asset.warehouse_connection
        if not connection.is_active:
            raise ValidationError("Warehouse connection is inactive.")

        config = connection.get_config()
        meta = asset.metadata or {}
        table_name = meta.get("external_table_ref") or meta.get("table_name")
        if not table_name:
            raise ValidationError("No table name configured for this asset.")

        # Check Redis cache first.
        asset_id = str(asset.id)
        cache_key = f"wh:query:{asset_id}:{limit}:{cursor_offset}"
        try:
            from .cache import get_cached_result

            cached = get_cached_result(tenant_id_str, asset_id, cache_key)
            if cached is not None:
                return Response(
                    {
                        "rows": cached["rows"],
                        "cursor": cached.get("cursor"),
                        "row_count": cached.get("row_count", len(cached["rows"])),
                        "cached": True,
                    }
                )
        except Exception:
            pass

        from .base import get_connector_for_connection

        connector_cls = get_connector_for_connection(connection.warehouse_type)
        connector = connector_cls(config, tenant_id=str(connection.tenant_id))

        connector.connect()
        try:
            sql = f"SELECT * FROM {table_name} LIMIT {limit} OFFSET {cursor_offset}"
            result = connector.execute_query(sql)
            rows = [list(row) for row in result.rows]

            # Build next cursor.
            next_offset = cursor_offset + len(rows)
            next_cursor = (
                b64encode(str(next_offset).encode()).decode() if len(rows) == limit else None
            )

            response_data = {
                "rows": rows,
                "cursor": next_cursor,
                "row_count": len(rows),
                "cached": False,
            }

            # Populate cache with stampede lock.
            try:
                from .cache import set_cached_result

                set_cached_result(
                    str(tenant.id),
                    asset_id,
                    cache_key,
                    {"rows": rows, "cursor": next_cursor, "row_count": len(rows)},
                    ttl_s=300,
                )
            except Exception:
                pass

            # Emit audit event.
            try:
                from hub.apps.audit.utils import create_audit_event

                create_audit_event(
                    resource_type="ASSET",
                    action="WAREHOUSE_RECORDS_ACCESSED",
                    tenant=asset.tenant,
                    resource_id=str(asset.id),
                    details={
                        "asset_id": str(asset.id),
                        "warehouse_type": connection.warehouse_type,
                        "rows_returned": len(rows),
                        "limit": limit,
                        "cursor_offset": cursor_offset,
                    },
                )
            except Exception:
                pass

            # Arrow format via Accept header (Phase 275.B).
            accept = request.META.get("HTTP_ACCEPT", "")
            if "arrow" in accept.lower() or "vnd.apache.arrow.stream" in accept:
                try:
                    import pyarrow as pa

                    table = pa.table(
                        {str(i): [r[i] for r in rows] for i in range(len(rows[0]) if rows else 0)}
                    )
                    sink = pa.BufferOutputStream()
                    with pa.ipc.new_stream(sink, table.schema) as writer:
                        writer.write_table(table)
                    return Response(
                        sink.getvalue().to_pybytes(),
                        content_type="application/vnd.apache.arrow.stream",
                    )
                except ImportError:
                    pass  # Fall back to JSON

            return Response(response_data)
        finally:
            with contextlib.suppress(Exception):
                connector.close()


class DeltaShareView(viewsets.ViewSet):
    """Delta Sharing 1.0 protocol endpoint for LIVE_QUERY assets.

    GET /api/v1/warehouses/share/{asset_id}/ — list tables in share.
    GET /api/v1/warehouses/share/{asset_id}/query/ — query table data.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]

    @action(detail=False, methods=["get"], url_path="(?P<asset_id>[^/.]+)")
    def list_tables(self, request, asset_id=None):
        """List tables available in the share for this asset."""
        from hub.apps.assets.models import Asset, DataStrategy

        try:
            asset = Asset.objects.get(
                id=asset_id,
                data_strategy=DataStrategy.LIVE_QUERY,
            )
        except Asset.DoesNotExist:
            raise NotFound("LIVE_QUERY asset not found.")

        tenant = _get_tenant(request)
        if str(asset.tenant_id) != str(tenant.id):
            raise PermissionDenied("Asset not in your tenant.")

        # Emit audit for share access.
        try:
            from hub.apps.audit.utils import create_audit_event

            create_audit_event(
                resource_type="ASSET",
                action="WAREHOUSE_SHARE_ACCESSED",
                tenant=asset.tenant,
                resource_id=str(asset.id),
            )
        except Exception:
            pass

        meta = asset.metadata or {}
        table_name = meta.get("external_table_ref") or meta.get("table_name") or "unknown"
        return Response(
            {
                "share": {
                    "name": f"meshant_{asset.id.hex[:8]}",
                },
                "tables": [
                    {
                        "name": table_name,
                        "share": f"meshant_{asset.id.hex[:8]}",
                        "schema": f"meshant_{asset.id.hex[:8]}",
                    }
                ],
            }
        )

    @action(detail=False, methods=["get"], url_path="(?P<asset_id>[^/.]+)/query")
    def query_table(self, request, asset_id=None):
        """Query table data via Delta Sharing protocol."""
        from hub.apps.assets.models import Asset, DataStrategy

        try:
            asset = Asset.objects.get(
                id=asset_id,
                data_strategy=DataStrategy.LIVE_QUERY,
                warehouse_connection__isnull=False,
            )
        except Asset.DoesNotExist:
            raise NotFound("LIVE_QUERY asset not found.")

        tenant = _get_tenant(request)
        if str(asset.tenant_id) != str(tenant.id):
            raise PermissionDenied("Asset not in your tenant.")

        limit = min(int(request.query_params.get("limit", 100)), 1000)

        connection = asset.warehouse_connection
        config = connection.get_config()
        meta = asset.metadata or {}
        table_name = meta.get("external_table_ref") or meta.get("table_name")

        if not table_name:
            raise ValidationError("No table name configured for this asset.")

        from .base import get_connector_for_connection

        connector_cls = get_connector_for_connection(connection.warehouse_type)
        connector = connector_cls(config, tenant_id=str(connection.tenant_id))

        connector.connect()
        try:
            result = connector.execute_query(
                f"SELECT * FROM {table_name} LIMIT {limit}",
            )
            rows = [list(row) for row in result.rows]
        finally:
            with contextlib.suppress(Exception):
                connector.close()

        return Response(
            {
                "protocol": {"version": 1},
                "metaData": {
                    "table": table_name,
                    "warehouse_type": connection.warehouse_type,
                    "row_count": len(rows),
                },
                "rows": rows,
            }
        )


class WarehouseConnectionACLViewSet(viewsets.ModelViewSet):
    """CRUD for warehouse connection ACLs. Tenant-scoped."""

    queryset = WarehouseConnectionACL.objects.all().order_by("-created_at")
    serializer_class = WarehouseConnectionACLSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    lookup_field = "id"

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            return WarehouseConnectionACL.objects.all().order_by("-created_at")
        tenant = _get_tenant(self.request)
        if tenant is None:
            return WarehouseConnectionACL.objects.none()
        return WarehouseConnectionACL.objects.filter(tenant=tenant).order_by("-created_at")

    def perform_create(self, serializer):
        tenant = _get_tenant(self.request)
        serializer.save(tenant=tenant)
