"""
Kubernetes service discovery integration tests.

Validates Service creation, selectors, and alignment with workloads and Ingress
from real k8s manifests via kustomize build. No mocks.
"""

from __future__ import annotations

import pytest

from tests.integration.kubernetes_manifest_utils import (
    discover_k8s_bases,
    get_resources_by_kind,
    kustomize_available,
    load_manifests_from_kustomize,
)

_K8S_BASES = discover_k8s_bases()
_K8S_BASE_IDS = [name for name, _ in _K8S_BASES]


@pytest.fixture(scope="module")
def kustomize_available_check():
    """Skip entire module if kustomize/kubectl is not available."""
    if not kustomize_available():
        pytest.skip(
            "kustomize or kubectl kustomize not available; "
            "install to run Kubernetes manifest tests"
        )


def _workload_selector(workload: dict) -> dict | None:
    """Return spec.selector for Deployment or StatefulSet."""
    spec = workload.get("spec") or {}
    return spec.get("selector") if spec else None


def _workload_labels(workload: dict) -> dict:
    """Return template.spec labels used for selector matching (matchLabels)."""
    spec = workload.get("spec") or {}
    template = spec.get("template", {})
    return template.get("metadata", {}).get("labels", {})


class TestKubernetesServiceDiscovery:
    """Validate Service resources and their alignment with workloads and Ingress."""

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_services_have_required_spec(self, service_name, base_path, kustomize_available_check):
        """Every Service has spec.ports, spec.selector, and valid type."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for svc in by_kind.get("Service", []):
            spec = svc.get("spec") or {}
            assert spec.get("ports"), (
                f"{service_name} Service {svc.get('metadata', {}).get('name')} missing spec.ports"
            )
            assert spec.get("selector") is not None, (
                f"{service_name} Service should have spec.selector (can be empty for headless)"
            )
            # ClusterIP, NodePort, LoadBalancer are valid
            stype = spec.get("type", "ClusterIP")
            assert stype in ("ClusterIP", "NodePort", "LoadBalancer", "ExternalName"), (
                f"{service_name} Service has invalid type: {stype}"
            )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_services_have_port_names_or_numbers(self, service_name, base_path, kustomize_available_check):
        """Service ports have port number and preferably name."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for svc in by_kind.get("Service", []):
            for p in (svc.get("spec") or {}).get("ports", []):
                assert "port" in p, f"{service_name} Service port entry missing 'port': {p}"
                assert isinstance(p["port"], (int, str)), f"{service_name} Service port should be number or string"

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_deployment_has_matching_service(self, service_name, base_path, kustomize_available_check):
        """For each Deployment there is a Service whose selector matches the Deployment's template labels."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        deployments = by_kind.get("Deployment", [])
        services = by_kind.get("Service", [])
        if not deployments:
            return
        for d in deployments:
            name = d.get("metadata", {}).get("name")
            ns = d.get("metadata", {}).get("namespace", "")
            labels = _workload_labels(d)
            if not labels:
                continue
            selector = (d.get("spec") or {}).get("selector", {}).get("matchLabels") or (d.get("spec") or {}).get("selector") or {}
            if not selector:
                continue
            found = False
            for svc in services:
                svc_sel = (svc.get("spec") or {}).get("selector") or {}
                if not svc_sel:
                    continue
                if all(svc_sel.get(k) == v for k, v in selector.items()):
                    found = True
                    break
            assert found, (
                f"{service_name} Deployment {name} (ns={ns}) has no Service with matching selector {selector}"
            )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_statefulset_has_matching_service(self, service_name, base_path, kustomize_available_check):
        """For each StatefulSet there is a Service (headless or normal) with matching selector."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        statefulsets = by_kind.get("StatefulSet", [])
        services = by_kind.get("Service", [])
        if not statefulsets:
            return
        for s in statefulsets:
            name = s.get("metadata", {}).get("name")
            spec = s.get("spec") or {}
            service_name_ref = spec.get("serviceName")
            selector = spec.get("selector") or {}
            match_labels = selector.get("matchLabels") or selector or {}
            if not match_labels and not service_name_ref:
                continue
            found = False
            for svc in services:
                svc_name = svc.get("metadata", {}).get("name")
                if service_name_ref and svc_name == service_name_ref:
                    found = True
                    break
                svc_sel = (svc.get("spec") or {}).get("selector") or {}
                if svc_sel and all(svc_sel.get(k) == v for k, v in match_labels.items()):
                    found = True
                    break
            assert found, (
                f"{service_name} StatefulSet {name} references serviceName={service_name_ref} or selector {match_labels}; "
                "no matching Service found"
            )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_ingress_backend_services_exist(self, service_name, base_path, kustomize_available_check):
        """Ingress rules reference Services that exist in the same manifest set."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        ingresses = by_kind.get("Ingress", [])
        service_names = {
            (s.get("metadata", {}).get("name"), s.get("metadata", {}).get("namespace", ""))
            for s in by_kind.get("Service", [])
        }
        if not ingresses:
            return
        for ing in ingresses:
            spec = ing.get("spec") or {}
            # Default backend (networking.k8s.io/v1: spec.defaultBackend; older: spec.backend)
            for backend_key in ("defaultBackend", "backend"):
                backend = spec.get(backend_key)
                if backend and isinstance(backend, dict) and "service" in backend:
                    svc_ref = backend["service"]
                    ref_name = svc_ref.get("name")
                    ref_ns = ing.get("metadata", {}).get("namespace", "default")
                    if ref_name:
                        assert (ref_name, ref_ns) in service_names, (
                            f"{service_name} Ingress {backend_key} references Service {ref_name} in ns {ref_ns} which is not in build"
                        )
            for rule in spec.get("rules", []):
                for path in rule.get("http", {}).get("paths", []):
                    backend = path.get("backend", {})
                    svc_ref = backend.get("service") if isinstance(backend, dict) else None
                    if not svc_ref:
                        continue
                    ref_name = svc_ref.get("name")
                    ref_ns = ing.get("metadata", {}).get("namespace", "default")
                    assert (ref_name, ref_ns) in service_names, (
                        f"{service_name} Ingress path backend references Service {ref_name} in ns {ref_ns} which is not in build"
                    )
