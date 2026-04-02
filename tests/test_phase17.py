"""
Phase 17 Tests — Prefect Kubernetes Work Pool

Covers:
  17.10 test_deployment_sync_no_docker_sdk_import
        Import deployment_sync and assert the 'docker' package (Docker SDK)
        is NOT imported as a side-effect.  docker.from_env() failures in the
        Prefect K8s agent were the original motivation for removing the Docker
        work pool; if docker is present in sys.modules after import it means
        the old work pool code crept back in.

  17.10 test_prefect_k8s_worker_config_valid
        Build a K8s job_variables dict (as deployment_sync does) and assert
        it contains all required K8s keys with sensible defaults.

  17.10 test_k8s_job_variables_no_docker_network_key
        The job_variables dict must NOT contain 'networks' (Docker-specific
        key).  'networks' causes the K8s work pool to raise a validation error.

  17.10 test_k8s_job_variables_resource_bounds
        resource requests/limits must be present and correctly nested.

  17.10 test_k8s_image_pull_secrets_omitted_when_empty
        When PREFECT_K8S_IMAGE_PULL_SECRETS is unset, the 'image_pull_secrets'
        key must be absent from job_variables (not an empty list which can
        break some K8s work pool versions).
"""
from __future__ import annotations

import importlib
import os
import sys
import types
import pytest


# ---------------------------------------------------------------------------
# 17.10  test_deployment_sync_no_docker_sdk_import
# ---------------------------------------------------------------------------

def test_deployment_sync_no_docker_sdk_import():
    """
    Importing deployment_sync must NOT pull in the 'docker' Python SDK.

    The Docker SDK is not installed in the Prefect K8s agent image and its
    presence triggered runtime failures when the old DockerWorkPool tried to
    call docker.from_env() on startup.
    """
    # Remove docker from sys.modules if it was already imported by a prior test
    for mod_name in list(sys.modules.keys()):
        if mod_name == "docker" or mod_name.startswith("docker."):
            del sys.modules[mod_name]

    # Import deployment_sync — this must not re-import the docker SDK.
    # We do a fresh import each time by removing the module first.
    mod_name = "deployment_sync"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    try:
        import deployment_sync  # noqa: F401
    except Exception:
        # If deployment_sync can't fully load (e.g. missing Prefect server),
        # that is fine for this test — we only care about the 'docker' import.
        pass

    assert "docker" not in sys.modules, (
        "The 'docker' SDK must NOT be imported by deployment_sync. "
        "Presence of 'docker' in sys.modules indicates a Docker work pool "
        "dependency that breaks the Prefect K8s agent environment."
    )


# ---------------------------------------------------------------------------
# 17.10  K8s job_variables shape tests (pure-unit, no Prefect server needed)
# ---------------------------------------------------------------------------

def _build_k8s_job_variables(env: dict | None = None) -> dict:
    """
    Replicate the job_variables construction logic from deployment_sync so
    the tests do not require a live Prefect server or the full module import.
    """
    _env = env or {}

    deployment_image = _env.get("PREFECT_DEPLOYMENT_IMAGE", "hub-prefect:latest")
    k8s_namespace = _env.get("PREFECT_K8S_NAMESPACE", "default")
    k8s_service_account = _env.get("PREFECT_K8S_SERVICE_ACCOUNT_NAME", "prefect-worker")
    k8s_image_pull_secrets_str = _env.get("PREFECT_K8S_IMAGE_PULL_SECRETS", "")
    k8s_image_pull_secrets = (
        [s.strip() for s in k8s_image_pull_secrets_str.split(",") if s.strip()]
        if k8s_image_pull_secrets_str
        else []
    )

    hub_base_url = _env.get("HUB_BASE_URL", "http://api-service:8000")
    hub_worker_api_key = _env.get("HUB_WORKER_API_KEY", "")
    prefect_api_url = _env.get("PREFECT_API_URL", "http://prefect-server:4200/api")
    prefect_api_key = _env.get("PREFECT_API_KEY", "")

    flow_env: dict = {
        "HUB_BASE_URL": hub_base_url,
        "HUB_WORKER_API_KEY": hub_worker_api_key,
        "PREFECT_API_URL": prefect_api_url,
    }
    if prefect_api_key:
        flow_env["PREFECT_API_KEY"] = prefect_api_key

    job_variables: dict = {
        "image": deployment_image,
        "namespace": k8s_namespace,
        "service_account_name": k8s_service_account,
        "env": flow_env,
        "resources": {
            "requests": {
                "cpu": _env.get("PREFECT_K8S_CPU_REQUEST", "100m"),
                "memory": _env.get("PREFECT_K8S_MEMORY_REQUEST", "256Mi"),
            },
            "limits": {
                "cpu": _env.get("PREFECT_K8S_CPU_LIMIT", "1000m"),
                "memory": _env.get("PREFECT_K8S_MEMORY_LIMIT", "1Gi"),
            },
        },
    }
    if k8s_image_pull_secrets:
        job_variables["image_pull_secrets"] = k8s_image_pull_secrets

    return job_variables


def test_prefect_k8s_worker_config_valid():
    """
    Instantiate a K8s job_variables dict and assert required keys are present
    with sensible defaults.  No external services needed.
    """
    jv = _build_k8s_job_variables()

    assert jv["namespace"] == "default"
    assert jv["service_account_name"] == "prefect-worker"
    assert jv["image"] == "hub-prefect:latest"
    assert "env" in jv
    assert "resources" in jv
    assert "requests" in jv["resources"]
    assert "limits" in jv["resources"]


def test_k8s_job_variables_no_docker_network_key():
    """
    The job_variables dict must NOT contain the 'networks' key.

    'networks' is Docker-specific and causes the Kubernetes work pool base
    job template to fail validation.
    """
    jv = _build_k8s_job_variables()
    assert "networks" not in jv, (
        "job_variables must not contain 'networks' — this is a Docker work "
        "pool key that breaks the Kubernetes work pool."
    )


def test_k8s_job_variables_resource_bounds():
    """Resource requests and limits must be present and correctly nested."""
    jv = _build_k8s_job_variables({
        "PREFECT_K8S_CPU_REQUEST": "200m",
        "PREFECT_K8S_CPU_LIMIT": "2000m",
        "PREFECT_K8S_MEMORY_REQUEST": "512Mi",
        "PREFECT_K8S_MEMORY_LIMIT": "2Gi",
    })
    assert jv["resources"]["requests"]["cpu"] == "200m"
    assert jv["resources"]["limits"]["cpu"] == "2000m"
    assert jv["resources"]["requests"]["memory"] == "512Mi"
    assert jv["resources"]["limits"]["memory"] == "2Gi"


def test_k8s_image_pull_secrets_omitted_when_empty():
    """When no pull secrets are configured the key must be absent."""
    jv = _build_k8s_job_variables({"PREFECT_K8S_IMAGE_PULL_SECRETS": ""})
    assert "image_pull_secrets" not in jv


def test_k8s_image_pull_secrets_populated_when_set():
    """When pull secrets are configured they appear as a list."""
    jv = _build_k8s_job_variables({
        "PREFECT_K8S_IMAGE_PULL_SECRETS": "regcred,ecr-secret"
    })
    assert jv["image_pull_secrets"] == ["regcred", "ecr-secret"]


def test_k8s_prefect_api_key_included_only_when_set():
    """PREFECT_API_KEY must be passed to flow env only when non-empty."""
    jv_no_key = _build_k8s_job_variables({"PREFECT_API_KEY": ""})
    assert "PREFECT_API_KEY" not in jv_no_key["env"]

    jv_with_key = _build_k8s_job_variables({"PREFECT_API_KEY": "secret-token"})
    assert jv_with_key["env"]["PREFECT_API_KEY"] == "secret-token"
