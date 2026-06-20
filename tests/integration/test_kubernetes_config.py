"""
Kubernetes ConfigMap and Secret integration tests.

Validates ConfigMap/Secret management, PVC references, and that workloads
reference existing config/secret resources. No mocks.
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


def _referenced_configmaps_and_secrets(
    manifests: list[dict],
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Extract (name, namespace) of ConfigMaps and Secrets referenced by Pod templates (containers + initContainers)."""
    configmaps = set()
    secrets = set()

    def collect_from_container(container: dict, ns: str) -> None:
        for env in container.get("env", []):
            ref = env.get("valueFrom") or {}
            if ref.get("configMapKeyRef"):
                cm = ref["configMapKeyRef"]
                configmaps.add((cm.get("name"), ns))
            if ref.get("secretKeyRef"):
                sec = ref["secretKeyRef"]
                secrets.add((sec.get("name"), ns))

    for m in manifests:
        kind = m.get("kind")
        if kind not in ("Deployment", "StatefulSet", "DaemonSet", "Pod"):
            continue
        spec = m.get("spec") or {}
        template = spec.get("template", {}) if kind != "Pod" else spec
        pod_spec = template.get("spec", {})
        ns = (m.get("metadata") or {}).get("namespace", "default")
        for container in pod_spec.get("containers", []):
            collect_from_container(container, ns)
        for container in pod_spec.get("initContainers", []):
            collect_from_container(container, ns)
        for vol in pod_spec.get("volumes", []):
            cm_vol = vol.get("configMap") or {}
            if cm_vol.get("name"):
                configmaps.add((cm_vol["name"], ns))
            sec_vol = vol.get("secret") or {}
            if sec_vol.get("secretName"):
                secrets.add((sec_vol["secretName"], ns))
    return configmaps, secrets


@pytest.fixture(scope="module")
def kustomize_available_check():
    """Skip entire module if kustomize/kubectl is not available."""
    if not kustomize_available():
        pytest.skip(
            "kustomize or kubectl kustomize not available; install to run Kubernetes manifest tests"
        )


class TestKubernetesConfig:
    """Validate ConfigMap and Secret resources and their usage."""

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_referenced_configmaps_exist(self, service_name, base_path, kustomize_available_check):
        """ConfigMaps referenced by workloads exist in the same kustomize build."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        cm_refs, _ = _referenced_configmaps_and_secrets(manifests)
        existing = {
            (c.get("metadata", {}).get("name"), c.get("metadata", {}).get("namespace", "default"))
            for c in by_kind.get("ConfigMap", [])
        }
        for name, ns in cm_refs:
            assert (name, ns) in existing, (
                f"{service_name} references ConfigMap {name} in ns {ns} but it is not in build"
            )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_referenced_secrets_exist(self, service_name, base_path, kustomize_available_check):
        """Secrets referenced by workloads exist in the same kustomize build."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        _, sec_refs = _referenced_configmaps_and_secrets(manifests)
        existing = {
            (s.get("metadata", {}).get("name"), s.get("metadata", {}).get("namespace", "default"))
            for s in by_kind.get("Secret", [])
        }
        for name, ns in sec_refs:
            assert (name, ns) in existing, (
                f"{service_name} references Secret {name} in ns {ns} but it is not in build"
            )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_configmaps_have_data_or_binary_data(
        self, service_name, base_path, kustomize_available_check
    ):
        """ConfigMaps have data or binaryData (or are used only as optional)."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for cm in by_kind.get("ConfigMap", []):
            has_data = "data" in cm or "binaryData" in cm
            assert has_data, (
                f"{service_name} ConfigMap {cm.get('metadata', {}).get('name')} should have data or binaryData"
            )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_secrets_have_data_or_string_data_or_external(
        self, service_name, base_path, kustomize_available_check
    ):
        """Secrets have data, stringData, or are external (no assertion for external)."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for sec in by_kind.get("Secret", []):
            has_data = "data" in sec or "stringData" in sec
            # Opaque or kubernetes.io/service-account-token; external types may have no data
            stype = (sec.get("type") or "Opaque").strip()
            if "external" in stype.lower() or "helm" in stype.lower():
                continue
            assert has_data, (
                f"{service_name} Secret {sec.get('metadata', {}).get('name')} (type={stype}) should have data or stringData"
            )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_pvc_referenced_by_workloads_exist(
        self, service_name, base_path, kustomize_available_check
    ):
        """PersistentVolumeClaims referenced by workload volumes exist in the same build."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        pvc_refs = set()
        for m in manifests:
            kind = m.get("kind")
            if kind not in ("Deployment", "StatefulSet", "DaemonSet", "Pod"):
                continue
            spec = m.get("spec") or {}
            template = spec.get("template", {}) if kind != "Pod" else spec
            pod_spec = template.get("spec", {})
            ns = (m.get("metadata") or {}).get("namespace", "default")
            for vol in pod_spec.get("volumes", []):
                pvc = vol.get("persistentVolumeClaim") or {}
                if pvc.get("claimName"):
                    pvc_refs.add((pvc["claimName"], ns))
        existing = {
            (p.get("metadata", {}).get("name"), p.get("metadata", {}).get("namespace", "default"))
            for p in by_kind.get("PersistentVolumeClaim", [])
        }
        for name, ns in pvc_refs:
            assert (name, ns) in existing, (
                f"{service_name} references PVC {name} in ns {ns} but it is not in build"
            )

    @pytest.mark.parametrize("service_name,base_path", _K8S_BASES, ids=_K8S_BASE_IDS)
    def test_pvcs_have_storage_request(self, service_name, base_path, kustomize_available_check):
        """PersistentVolumeClaims have spec.resources.requests.storage."""
        manifests = load_manifests_from_kustomize(base_path)
        by_kind = get_resources_by_kind(manifests)
        for pvc in by_kind.get("PersistentVolumeClaim", []):
            spec = pvc.get("spec") or {}
            requests = spec.get("resources", {}).get("requests", {})
            assert "storage" in requests, (
                f"{service_name} PVC {pvc.get('metadata', {}).get('name')} missing spec.resources.requests.storage"
            )
            assert spec.get("accessModes"), (
                f"{service_name} PVC {pvc.get('metadata', {}).get('name')} should have accessModes"
            )
