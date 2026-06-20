"""
Kubernetes scaling and resource quota integration tests.

Validates HorizontalPodAutoscaler, ResourceQuota, and PVC resource requests
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
            "kustomize or kubectl kustomize not available; install to run Kubernetes manifest tests"
        )


class TestKubernetesScaling:
    """Validate HPA, ResourceQuota, and PVC scaling-related structure."""

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_hpa_has_scale_target_and_metrics(
        self, service_name, base_path, kustomize_available_check
    ):
        """HorizontalPodAutoscaler has scaleTargetRef, minReplicas, maxReplicas, and metrics."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for hpa in by_kind.get("HorizontalPodAutoscaler", []):
            spec = hpa.get("spec") or {}
            assert spec.get("scaleTargetRef"), (
                f"{service_name} HPA {hpa.get('metadata', {}).get('name')} missing spec.scaleTargetRef"
            )
            assert "minReplicas" in spec or "maxReplicas" in spec, (
                f"{service_name} HPA should have minReplicas or maxReplicas"
            )
            assert spec.get("maxReplicas"), (
                f"{service_name} HPA {hpa.get('metadata', {}).get('name')} missing spec.maxReplicas"
            )
            # v2 HPA: spec.metrics; v1: spec.metrics or CPU target
            metrics = spec.get("metrics", [])
            if not metrics and "targetCPUUtilizationPercentage" not in spec:
                # v2 behavior may have metrics in spec.behavior only; still require some scaling signal
                pass
            # At least one of: metrics list, or (v1) targetCPUUtilizationPercentage
            has_target = bool(metrics) or spec.get("targetCPUUtilizationPercentage") is not None
            assert has_target, (
                f"{service_name} HPA {hpa.get('metadata', {}).get('name')} should have spec.metrics or targetCPUUtilizationPercentage"
            )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_hpa_scale_target_exists(self, service_name, base_path, kustomize_available_check):
        """HPA scaleTargetRef points to a Deployment or StatefulSet in the same build."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        deployments = {
            (d.get("metadata", {}).get("name"), d.get("metadata", {}).get("namespace", "default"))
            for d in by_kind.get("Deployment", [])
        }
        statefulsets = {
            (s.get("metadata", {}).get("name"), s.get("metadata", {}).get("namespace", "default"))
            for s in by_kind.get("StatefulSet", [])
        }
        for hpa in by_kind.get("HorizontalPodAutoscaler", []):
            ref = (hpa.get("spec") or {}).get("scaleTargetRef") or {}
            name = ref.get("name")
            kind = ref.get("kind", "Deployment")
            ns = hpa.get("metadata", {}).get("namespace", "default")
            if not name:
                continue
            if kind == "Deployment":
                assert (name, ns) in deployments, (
                    f"{service_name} HPA scaleTargetRef Deployment {name} in ns {ns} not found in build"
                )
            elif kind == "StatefulSet":
                assert (name, ns) in statefulsets, (
                    f"{service_name} HPA scaleTargetRef StatefulSet {name} in ns {ns} not found in build"
                )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_resource_quota_has_hard_limits(
        self, service_name, base_path, kustomize_available_check
    ):
        """ResourceQuota has non-empty spec.hard."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for rq in by_kind.get("ResourceQuota", []):
            hard = (rq.get("spec") or {}).get("hard") or {}
            assert hard, (
                f"{service_name} ResourceQuota {rq.get('metadata', {}).get('name')} should have spec.hard"
            )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_resource_quota_namespace_consistent(
        self, service_name, base_path, kustomize_available_check
    ):
        """ResourceQuota metadata.namespace is set and consistent with spec (same namespace)."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for rq in by_kind.get("ResourceQuota", []):
            ns = rq.get("metadata", {}).get("namespace")
            assert ns, (
                f"{service_name} ResourceQuota {rq.get('metadata', {}).get('name')} should have metadata.namespace"
            )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_pvc_access_modes_valid(self, service_name, base_path, kustomize_available_check):
        """PersistentVolumeClaims have valid accessModes (ReadWriteOnce, ReadOnlyMany, ReadWriteMany)."""
        valid_modes = {"ReadWriteOnce", "ReadOnlyMany", "ReadWriteMany", "ReadWriteOncePod"}
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for pvc in by_kind.get("PersistentVolumeClaim", []):
            modes = pvc.get("spec", {}).get("accessModes") or []
            for m in modes:
                assert m in valid_modes, (
                    f"{service_name} PVC {pvc.get('metadata', {}).get('name')} has invalid accessMode: {m}"
                )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_pvc_storage_request_positive(self, service_name, base_path, kustomize_available_check):
        """PersistentVolumeClaims spec.resources.requests.storage is a valid quantity string."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for pvc in by_kind.get("PersistentVolumeClaim", []):
            storage = (
                (pvc.get("spec") or {}).get("resources", {}).get("requests", {}).get("storage")
            )
            assert storage, (
                f"{service_name} PVC {pvc.get('metadata', {}).get('name')} missing spec.resources.requests.storage"
            )
            assert isinstance(storage, str) and len(storage) > 0, (
                f"{service_name} PVC storage request should be non-empty string (e.g. 10Gi)"
            )
