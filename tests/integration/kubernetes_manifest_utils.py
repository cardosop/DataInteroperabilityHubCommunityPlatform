"""
Shared utilities for Kubernetes manifest integration tests.

Uses real kustomize build (subprocess); no mocks or stubs.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

# Project root: tests/integration/kubernetes_manifest_utils.py -> project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_K8S_DIR = _PROJECT_ROOT / "k8s"


def get_k8s_dir() -> Path:
    """Return the k8s manifest directory (project root / k8s)."""
    return _K8S_DIR


def get_project_root() -> Path:
    """Return the project root directory."""
    return _PROJECT_ROOT


def discover_k8s_bases() -> list[tuple[str, Path]]:
    """
    Discover all Kustomize base directories under k8s/.

    Includes: (1) k8s/<name>/base/ when base/kustomization.yaml exists;
    (2) k8s/<name>/<sub>/ when there is no base/ but subdir has kustomization.yaml
    (e.g. api-gateway/traefik, logging/loki, logging/promtail).

    Returns:
        List of (service_name, base_path) for each kustomize root.
    """
    k8s = get_k8s_dir()
    if not k8s.is_dir():
        return []
    result = []
    for child in sorted(k8s.iterdir()):
        if not child.is_dir():
            continue
        base = child / "base"
        base_kustomization = base / "kustomization.yaml"
        if base_kustomization.is_file():
            result.append((child.name, base))
        else:
            for sub in sorted(child.iterdir()):
                if not sub.is_dir():
                    continue
                if (sub / "kustomization.yaml").is_file():
                    result.append((f"{child.name}-{sub.name}", sub))
    return result


def discover_k8s_overlays() -> list[tuple[str, str, Path]]:
    """
    Discover all Kustomize overlay directories under k8s/*/overlays/*.

    Returns:
        List of (service_name, overlay_name, overlay_path) e.g. ('api-service', 'staging', Path(...)).
    """
    k8s = get_k8s_dir()
    if not k8s.is_dir():
        return []
    result = []
    for child in sorted(k8s.iterdir()):
        if not child.is_dir():
            continue
        overlays_dir = child / "overlays"
        if not overlays_dir.is_dir():
            continue
        for overlay in sorted(overlays_dir.iterdir()):
            if not overlay.is_dir():
                continue
            kustomization = overlay / "kustomization.yaml"
            if kustomization.is_file():
                result.append((child.name, overlay.name, overlay))
    return result


def _kustomize_build(base_path: Path) -> str:
    """
    Run kustomize build on base_path. Uses kubectl kustomize or kustomize.

    Raises:
        FileNotFoundError: if base_path or kustomization.yaml missing.
        subprocess.CalledProcessError: if kustomize build fails.
    """
    if not base_path.is_dir():
        raise FileNotFoundError(f"Kustomize base path does not exist: {base_path}")
    if not (base_path / "kustomization.yaml").is_file():
        raise FileNotFoundError(f"kustomization.yaml not found in {base_path}")

    # Prefer standalone kustomize, then kubectl kustomize
    for cmd in (["kustomize", "build", str(base_path)], ["kubectl", "kustomize", str(base_path)]):
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(get_project_root()),
            )
            if result.returncode == 0:
                return result.stdout
            # If command not found, try next
            if result.returncode == 127 or "not found" in (result.stderr or "").lower():
                continue
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )
        except FileNotFoundError:
            continue
    raise FileNotFoundError(
        "Neither 'kustomize' nor 'kubectl' found; install kustomize or kubectl to run Kubernetes manifest tests"
    )


def build_kustomize_raw(base_path: Path) -> str:
    """
    Build with kustomize and return the raw YAML stream (for kubectl apply --dry-run=client).

    Raises:
        FileNotFoundError: if base_path or kustomize not found.
        subprocess.CalledProcessError: if kustomize build fails.
    """
    return _kustomize_build(base_path)


def load_manifests_from_kustomize(base_path: Path) -> list[dict]:
    """
    Build with kustomize and return a list of parsed Kubernetes manifest dicts.

    Each document in the YAML stream becomes one dict. Documents without 'kind' are skipped.

    Raises:
        FileNotFoundError: if base_path or kustomize not found.
        subprocess.CalledProcessError: if kustomize build fails.
    """
    raw = _kustomize_build(base_path)
    docs = []
    for part in yaml.safe_load_all(raw):
        if part is None:
            continue
        if isinstance(part, dict) and part.get("kind"):
            docs.append(part)
    return docs


def get_resources_by_kind(manifests: list[dict]) -> dict[str, list[dict]]:
    """Group manifest dicts by kind. Returns e.g. {'Deployment': [...], 'Service': [...]}."""
    by_kind = {}
    for m in manifests:
        kind = m.get("kind")
        if not kind:
            continue
        by_kind.setdefault(kind, []).append(m)
    return by_kind


def kustomize_available() -> bool:
    """Return True if kustomize build can be run (kustomize or kubectl kustomize)."""
    bases = discover_k8s_bases()
    if not bases:
        return False
    _, first_base = bases[0]
    try:
        _kustomize_build(first_base)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def kubectl_available() -> bool:
    """Return True if kubectl is available for apply --dry-run=client."""
    try:
        result = subprocess.run(
            ["kubectl", "version", "--client"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def validate_manifests_with_kubectl_dry_run(yaml_stream: str) -> bool:
    """
    Run kubectl apply --dry-run=client -f - with the given YAML stream.
    Returns True if validation succeeds, False otherwise. No mocks; requires kubectl.
    """
    try:
        result = subprocess.run(
            ["kubectl", "apply", "--dry-run=client", "-f", "-"],
            check=False,
            input=yaml_stream,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False
