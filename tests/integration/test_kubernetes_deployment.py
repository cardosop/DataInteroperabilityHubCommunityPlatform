"""
Kubernetes deployment integration tests.

Validates Pod deployment (Deployment/StatefulSet), rolling update strategy,
and health checks from real k8s manifests via kustomize build. No mocks.
"""

from __future__ import annotations

import pytest

from tests.integration.kubernetes_manifest_utils import (
    build_kustomize_raw,
    discover_k8s_bases,
    discover_k8s_overlays,
    get_resources_by_kind,
    kubectl_available,
    kustomize_available,
    load_manifests_from_kustomize,
    validate_manifests_with_kubectl_dry_run,
)

# Services that must have liveness and readiness probes.
# Covers Deployments, StatefulSets, and DaemonSets — probe tests below
# iterate over all three resource kinds so infra StatefulSets (postgres,
# redis*, minio) and DaemonSets (logging-promtail) are included.
SERVICES_REQUIRING_PROBES = frozenset(
    {
        # Application services
        "api-service",
        "worker-service",
        "prefect-server",
        "prefect-integration",
        "prefect-workers",
        "search-service",
        "observability-service",
        "webhook-service",
        "compliance-service",
        "datacontract-service",
        "semantic-service",
        # Infra Deployments with probes
        "grafana",
        "jaeger",
        "fuseki",
        "api-gateway-traefik",
        "logging-loki",
        # Infra DaemonSets with probes
        "logging-promtail",
        # Infra StatefulSets with probes (exec/httpGet)
        "postgres",
        "redis",
        "redis-cache",
        "redis-channels",
        "redis-events",
        "redis-queue",
        "minio",
        "prometheus",
        "alertmanager",
    }
)


_K8S_BASES = discover_k8s_bases()
_K8S_BASE_IDS = [name for name, _ in _K8S_BASES]
_K8S_OVERLAYS = discover_k8s_overlays()
_K8S_OVERLAY_IDS = [f"{s}-{o}" for s, o, _ in _K8S_OVERLAYS]


@pytest.fixture(scope="module")
def k8s_bases():
    """Discover all k8s Kustomize bases."""
    if not _K8S_BASES:
        pytest.skip("No k8s base directories found under k8s/")
    return _K8S_BASES


@pytest.fixture(scope="module")
def kustomize_available_check():
    """Skip entire module if kustomize/kubectl is not available."""
    if not kustomize_available():
        pytest.skip(
            "kustomize or kubectl kustomize not available; install to run Kubernetes manifest tests"
        )


class TestKubernetesDeploymentManifests:
    """Validate Deployment and StatefulSet structure from k8s bases."""

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_kustomize_build_succeeds(self, service_name, base_path, kustomize_available_check):
        """Every k8s base builds successfully with kustomize."""
        manifests = load_manifests_from_kustomize(base_path)
        assert len(manifests) >= 1, f"{service_name}: kustomize build produced no resources"

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_deployments_have_required_spec(
        self, service_name, base_path, kustomize_available_check
    ):
        """Deployments have spec.replicas, selector, template, and containers."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for d in by_kind.get("Deployment", []):
            spec = d.get("spec") or {}
            assert "replicas" in spec, (
                f"{service_name} Deployment {d.get('metadata', {}).get('name')} missing spec.replicas"
            )
            assert "selector" in spec, f"{service_name} Deployment missing spec.selector"
            template = spec.get("template", {})
            assert template, f"{service_name} Deployment missing spec.template"
            pod_spec = template.get("spec", {})
            containers = pod_spec.get("containers", [])
            assert containers, f"{service_name} Deployment has no spec.template.spec.containers"
            for c in containers:
                assert "image" in c, f"{service_name} container {c.get('name')} missing image"
                assert "ports" in c or "name" in c, (
                    f"{service_name} container should have name and preferably ports"
                )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_statefulsets_have_required_spec(
        self, service_name, base_path, kustomize_available_check
    ):
        """StatefulSets have serviceName, selector, template, and containers."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for s in by_kind.get("StatefulSet", []):
            spec = s.get("spec") or {}
            assert "serviceName" in spec, (
                f"{service_name} StatefulSet {s.get('metadata', {}).get('name')} missing spec.serviceName"
            )
            assert "selector" in spec, f"{service_name} StatefulSet missing spec.selector"
            template = spec.get("template", {})
            assert template, f"{service_name} StatefulSet missing spec.template"
            containers = template.get("spec", {}).get("containers", [])
            assert containers, f"{service_name} StatefulSet has no containers"
            for c in containers:
                assert "image" in c, (
                    f"{service_name} StatefulSet container {c.get('name')} missing image"
                )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_deployments_rolling_update_strategy(
        self, service_name, base_path, kustomize_available_check
    ):
        """Deployments use RollingUpdate strategy with valid maxSurge/maxUnavailable."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for d in by_kind.get("Deployment", []):
            strategy = (d.get("spec") or {}).get("strategy", {})
            stype = strategy.get("type", "RollingUpdate")
            if stype == "RollingUpdate":
                ru = strategy.get("rollingUpdate") or {}
                assert "maxSurge" in ru or "maxUnavailable" in ru or ru == {}, (
                    f"{service_name} Deployment RollingUpdate should define maxSurge or maxUnavailable"
                )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_application_services_have_health_probes(
        self, service_name, base_path, kustomize_available_check
    ):
        """Application services have livenessProbe and readinessProbe on main containers."""
        if service_name not in SERVICES_REQUIRING_PROBES:
            pytest.skip(f"{service_name} not in set of services requiring probes")  # noqa: skip-in-body — runtime service dependency
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for resource in (
            by_kind.get("Deployment", [])
            + by_kind.get("StatefulSet", [])
            + by_kind.get("DaemonSet", [])
        ):
            for c in (
                (resource.get("spec") or {}).get("template", {}).get("spec", {}).get("containers", [])
            ):
                assert c.get("livenessProbe"), (
                    f"{service_name} container {c.get('name')} missing livenessProbe"
                )
                assert c.get("readinessProbe"), (
                    f"{service_name} container {c.get('name')} missing readinessProbe"
                )

    def test_all_workload_services_are_in_probes_set(self, kustomize_available_check):
        """Every k8s base that has Deployments/StatefulSets/DaemonSets must be in
        SERVICES_REQUIRING_PROBES so no new service silently skips probe validation.
        """
        missing = []
        for service_name, base_path in _K8S_BASES:
            if service_name in SERVICES_REQUIRING_PROBES:
                continue
            manifests = load_manifests_from_kustomize(base_path)
            by_kind = get_resources_by_kind(manifests)
            has_workload = (
                by_kind.get("Deployment")
                or by_kind.get("StatefulSet")
                or by_kind.get("DaemonSet")
            )
            if has_workload:
                missing.append(service_name)
        if missing:
            self.fail(
                f"k8s services with workloads missing from SERVICES_REQUIRING_PROBES: "
                f"{', '.join(missing)}. Add them to the set in test_kubernetes_deployment.py."
            )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_deployment_containers_no_placeholder_images(
        self, service_name, base_path, kustomize_available_check
    ):
        """Deployment container images are not placeholders like 'image: latest' or empty."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for d in by_kind.get("Deployment", []):
            for c in (
                (d.get("spec") or {}).get("template", {}).get("spec", {}).get("containers", [])
            ):
                image = (c.get("image") or "").strip()
                assert image, f"{service_name} container {c.get('name')} has no image"
                assert ":" in image or "/" in image, (
                    f"{service_name} container image should be a valid reference (repository:tag or path)"
                )

    @pytest.mark.parametrize(
        "service_name,overlay_name,overlay_path", _K8S_OVERLAYS, ids=_K8S_OVERLAY_IDS
    )
    def test_kustomize_overlay_build_succeeds(
        self, service_name, overlay_name, overlay_path, kustomize_available_check
    ):
        """Every k8s overlay (staging/production) builds successfully with kustomize."""
        manifests = load_manifests_from_kustomize(overlay_path)
        assert len(manifests) >= 1, (
            f"{service_name}/{overlay_name}: kustomize build produced no resources"
        )

    def test_kubectl_dry_run_client_succeeds_for_bases_when_kubectl_available(
        self, kustomize_available_check
    ):
        """When kubectl is available, apply --dry-run=client succeeds for each base (client-side validation)."""
        if not kubectl_available():
            pytest.skip("kubectl not available; skip client dry-run validation")  # noqa: skip-in-body — runtime service dependency
        failures = []
        for service_name, base_path in _K8S_BASES:
            raw = build_kustomize_raw(base_path)
            if not validate_manifests_with_kubectl_dry_run(raw):
                failures.append(service_name)
        if failures:
            self.fail(
                f"kubectl dry-run validation FAILED for: {', '.join(failures)}. "
                "These manifests have structural issues that need fixing."
            )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_application_services_probes_have_valid_structure(
        self, service_name, base_path, kustomize_available_check
    ):
        """Application service probes use httpGet, tcpSocket, or exec with valid path/port/command."""
        if service_name not in SERVICES_REQUIRING_PROBES:
            pytest.skip(f"{service_name} not in set of services requiring probes")  # noqa: skip-in-body — runtime service dependency
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for resource in (
            by_kind.get("Deployment", [])
            + by_kind.get("StatefulSet", [])
            + by_kind.get("DaemonSet", [])
        ):
            for c in (
                (resource.get("spec") or {}).get("template", {}).get("spec", {}).get("containers", [])
            ):
                for probe_name in ("livenessProbe", "readinessProbe"):
                    probe = c.get(probe_name)
                    if not probe:
                        continue
                    has_http = "httpGet" in probe
                    has_tcp = "tcpSocket" in probe
                    has_exec = "exec" in probe
                    assert has_http or has_tcp or has_exec, (
                        f"{service_name} container {c.get('name')} {probe_name} must have "
                        "httpGet, tcpSocket, or exec"
                    )
                    if has_http:
                        h = probe["httpGet"]
                        assert "port" in h or "path" in h, (
                            f"{service_name} {probe_name} httpGet must have port or path"
                        )
                    if has_tcp:
                        assert "port" in probe["tcpSocket"], (
                            f"{service_name} {probe_name} tcpSocket must have port"
                        )
                    if has_exec:
                        assert "command" in probe["exec"] and probe["exec"]["command"], (
                            f"{service_name} {probe_name} exec must have non-empty command"
                        )
