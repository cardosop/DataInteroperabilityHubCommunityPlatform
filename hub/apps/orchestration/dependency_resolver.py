"""
285.11.1.9 — PipelineDependencyResolver.

Resolves upstream/downstream dependencies, validates no cycles,
and builds an execution graph ordered by priority (DESC).
Results are cached per pipeline in Redis with a 5-min TTL;
cache is skipped for fewer than 20 pipeline dependencies per
tenant (the Redis round-trip costs more than a direct query).
"""

from __future__ import annotations

import contextlib
import json
import uuid
from collections import defaultdict, deque
from typing import Any

import structlog
from django.core.cache import cache

from .models import (
    PipelineDependency,
)

logger = structlog.get_logger(__name__)

# 285.11.1.9 — cache constants
_CACHE_TTL_SECONDS = 300  # 5 minutes
_CACHE_SKIP_THRESHOLD = 20  # skip cache for fewer than this many deps


class CycleDetectedError(ValueError):
    """Raised when a dependency cycle is found during validation."""


class PipelineDependencyResolver:
    """Resolves pipeline dependency graphs with cycle detection.

    All methods are tenant-scoped.  Callers MUST establish
    ``tenant_context(tenant_id)`` before invoking.
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = str(tenant_id)

    # ── Public API ──────────────────────────────────────────────────

    def resolve_upstream(
        self,
        pipeline_type: str,
        pipeline_id: str,
    ) -> list[PipelineDependency]:
        """Return all ACTIVE upstream dependencies for *pipeline*.

        An upstream dependency is any row where
        ``downstream_pipeline_type`` / ``downstream_pipeline_id``
        matches *pipeline*.
        """
        return list(
            PipelineDependency.objects.filter(
                tenant_id=self.tenant_id,
                downstream_pipeline_type=pipeline_type,
                downstream_pipeline_id=pipeline_id,
                is_active=True,
            ).order_by("-priority", "-created_at")
        )

    def resolve_downstream(
        self,
        pipeline_type: str,
        pipeline_id: str,
    ) -> list[PipelineDependency]:
        """Return all ACTIVE downstream dependencies for *pipeline*.

        A downstream dependency is any row where
        ``pipeline_type`` / ``pipeline_id`` matches *pipeline*.
        """
        return list(
            PipelineDependency.objects.filter(
                tenant_id=self.tenant_id,
                pipeline_type=pipeline_type,
                pipeline_id=pipeline_id,
                is_active=True,
            ).order_by("-priority", "-created_at")
        )

    def are_dependencies_met(
        self,
        pipeline_type: str,
        pipeline_id: str,
        upstream_run_statuses: dict[tuple[str, str], str],
    ) -> bool:
        """Return True iff every ACTIVE upstream dependency has a
        terminal, successful upstream run status.

        *upstream_run_statuses* is a dict keyed by
        ``(pipeline_type, pipeline_id)`` whose values are the
        terminal status of the upstream run (e.g. ``"SUCCEEDED"``).
        """
        upstream = self.resolve_upstream(pipeline_type, pipeline_id)
        if not upstream:
            return True  # no deps → always met
        for dep in upstream:
            key = (dep.pipeline_type, dep.pipeline_id)
            status = upstream_run_statuses.get(key)
            if status is None:
                return False
            if status.upper() not in _TERMINAL_SUCCESS_STATUSES:
                return False
        return True

    def validate_no_cycles(self) -> None:
        """Raise ``CycleDetectedError`` if any cycle exists in the
        dependency graph for this tenant.

        Uses Kahn's algorithm (topological sort on in-degree) to
        detect cycles in O(V + E).
        """
        deps = PipelineDependency.objects.filter(
            tenant_id=self.tenant_id,
            is_active=True,
        )
        # Build adjacency list and in-degree count.
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = defaultdict(int)
        nodes: set[str] = set()

        for dep in deps:
            u = _node_key(dep.pipeline_type, dep.pipeline_id)
            v = _node_key(
                dep.downstream_pipeline_type,
                dep.downstream_pipeline_id,
            )
            nodes.add(u)
            nodes.add(v)
            adj[u].append(v)
            in_degree[v] += 1
            if u not in in_degree:
                in_degree[u] = 0

        # Kahn's algorithm — O(V+E) with deque for O(1) popleft
        queue = deque(n for n in nodes if in_degree.get(n, 0) == 0)
        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            for neighbor in adj.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited != len(nodes):
            raise CycleDetectedError(
                f"Cycle detected in pipeline dependency graph "
                f"for tenant {self.tenant_id}. "
                f"Visited {visited}/{len(nodes)} nodes."
            )

    def build_execution_graph(
        self,
        pipeline_type: str,
        pipeline_id: str,
        max_depth: int = 10,
    ) -> dict[str, Any]:
        """Return a topologically-sorted execution graph rooted at
        *pipeline*, walking upstream dependencies recursively.

        The result is a dict::

            {
                "pipeline": {"type": str, "id": str},
                "dependencies": [
                    {
                        "pipeline": {"type": str, "id": str},
                        "dependency_type": str,
                        "priority": int,
                        "is_active": bool,
                        "dependencies": [...],
                    },
                    ...
                ],
                "cycle_free": bool,
                "depth": int,
            }

        Nodes are sorted by ``priority`` DESC then ``created_at``
        DESC at each level.
        """
        result = self._build_graph_cached(
            pipeline_type,
            pipeline_id,
            max_depth,
        )
        if result is not None:
            return result

        graph = self._build_graph_recursive(
            pipeline_type,
            pipeline_id,
            max_depth,
            visited=set(),
        )
        # Propagate cycle state from subtrees.
        graph["cycle_free"] = self._all_subtrees_cycle_free(graph)
        graph["depth"] = max_depth

        self._cache_graph(pipeline_type, pipeline_id, graph)
        return graph

    @staticmethod
    def _all_subtrees_cycle_free(graph: dict[str, Any]) -> bool:
        """Recursively check every subtree for cycle-free status."""
        for child in graph.get("dependencies", []):
            if not child.get("cycle_free", True):
                return False
            # Check grandchildren
            if not PipelineDependencyResolver._all_subtrees_cycle_free(child):
                return False
        return True

    # ── Caching helpers ─────────────────────────────────────────────

    def _cache_key(self, pipeline_type: str, pipeline_id: str) -> str:
        return f"pipeline_dep:{self.tenant_id}:{pipeline_type}:{pipeline_id}"

    def _build_graph_cached(
        self,
        pipeline_type: str,
        pipeline_id: str,
        max_depth: int,
    ) -> dict[str, Any] | None:
        # Skip cache when the dependency set is small.
        count = PipelineDependency.objects.filter(
            tenant_id=self.tenant_id,
            is_active=True,
        ).count()
        if count < _CACHE_SKIP_THRESHOLD:
            return None
        key = self._cache_key(pipeline_type, pipeline_id)
        try:
            raw = cache.get(key)
            if raw is not None:
                return json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            pass
        return None

    def _cache_graph(
        self,
        pipeline_type: str,
        pipeline_id: str,
        graph: dict[str, Any],
    ) -> None:
        key = self._cache_key(pipeline_type, pipeline_id)
        try:
            cache.set(key, json.dumps(graph, default=str), timeout=_CACHE_TTL_SECONDS)
        except Exception:
            pass  # cache is best-effort

    def _build_graph_recursive(
        self,
        pipeline_type: str,
        pipeline_id: str,
        max_depth: int,
        visited: set,
    ) -> dict[str, Any]:
        node_key = _node_key(pipeline_type, pipeline_id)
        if node_key in visited:
            return {
                "pipeline": {"type": pipeline_type, "id": pipeline_id},
                "dependencies": [],
                "cycle_free": False,
            }
        visited.add(node_key)

        upstream = self.resolve_upstream(pipeline_type, pipeline_id)
        children: list[dict[str, Any]] = []
        for dep in upstream:
            if max_depth > 0:
                child = self._build_graph_recursive(
                    dep.pipeline_type,
                    str(dep.pipeline_id),
                    max_depth - 1,
                    visited.copy(),
                )
            else:
                child = {
                    "pipeline": {
                        "type": dep.pipeline_type,
                        "id": str(dep.pipeline_id),
                    },
                    "dependencies": [],
                    "cycle_free": True,
                }
            children.append(
                {
                    "pipeline": {
                        "type": dep.pipeline_type,
                        "id": str(dep.pipeline_id),
                    },
                    "dependency_type": dep.dependency_type,
                    "priority": dep.priority,
                    "is_active": dep.is_active,
                    "dependencies": child.get("dependencies", []),
                }
            )

        # Sort children: priority DESC, then by is_active (active first)
        children.sort(
            key=lambda c: (c["priority"], c["is_active"]),
            reverse=True,
        )
        return {
            "pipeline": {"type": pipeline_type, "id": pipeline_id},
            "dependencies": children,
            "cycle_free": True,
        }


# ── Internal helpers ──────────────────────────────────────────────────


def _node_key(pipeline_type: str, pipeline_id: uuid.UUID | str) -> str:
    return f"{pipeline_type}:{pipeline_id}"


_TERMINAL_SUCCESS_STATUSES: frozenset[str] = frozenset(
    {
        "SUCCEEDED",
        "COMPLETED",
        "SUCCESS",
    }
)


def invalidate_pipeline_dependency_cache(
    tenant_id: str,
    pipeline_type: str | None = None,
    pipeline_id: str | None = None,
) -> None:
    """Invalidate cached execution graphs when a PipelineDependency
    is created, updated, or deleted.  Call from signal handlers.

    If *pipeline_type* and *pipeline_id* are provided, only the
    cache entries for that specific node are invalidated.  Otherwise,
    all entries matching the ``pipeline_dep:{tenant_id}:*`` prefix
    are deleted (wildcard invalidation).
    """
    if pipeline_type and pipeline_id:
        key = f"pipeline_dep:{tenant_id}:{pipeline_type}:{pipeline_id}"
        with contextlib.suppress(Exception):
            cache.delete(key)
        return

    # Wildcard invalidation — iterate keys matching prefix.
    # NOTE: django-redis supports ``cache.keys(pattern)`` but
    # Django's BaseCache does not.  We use a try/except and fall
    # back to doing nothing — the 5-min TTL handles eventual
    # consistency.
    try:
        pattern = f"pipeline_dep:{tenant_id}:*"
        if hasattr(cache, "keys"):
            for key in cache.keys(pattern):  # type: ignore[attr-defined]
                cache.delete(key)
    except Exception:
        pass  # wildcard invalidation is best-effort
