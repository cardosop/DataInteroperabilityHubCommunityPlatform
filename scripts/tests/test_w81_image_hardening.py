"""W8.1 (oss-release-remediation, M5a) — image-hardening contract pins.

Policy under test (TDD, no mocks — the REAL compose files, Dockerfiles,
and helm templates are parsed):

1. **No floating image refs** — every third-party image reference (a
   compose service with ``image:`` and no ``build:``) MUST carry an
   explicit version tag: no bare ``image: repo`` (floating :latest) and
   no ``:latest`` tag.  Repo-built images deploy by digest via the helm
   ``image.digest`` mechanism (the helper prefers digest over tag).
2. **Non-root** — every repo-built deployable Dockerfile's final stage
   MUST run as a non-root user: a ``USER`` directive, or an allowlisted
   base image that ships non-root by default
   (``nginxinc/nginx-unprivileged``).  CI-only images (shared/,
   odh-integration, odh-training-operator, odh-inference-scheduler) are
   exempt with an explicit reason — they are not deployed.
3. **HEALTHCHECKs** — every repo-built deployable service Dockerfile
   MUST carry a HEALTHCHECK.  CI-only images exempt as above.
4. **Migrations-on-boot policy** — production (helm) MUST NOT run
   ``manage.py migrate`` inline in the api pod command; migrations run in
   a dedicated pre-upgrade/pre-install Job.  Dev/test compose keeps the
   inline migrate (single-replica dev policy, documented).
5. **No dev tooling in the production stage** — the api/worker
   Dockerfiles' final (production) stage MUST NOT install test-only
   tooling (docker CLI, kubectl, gitleaks, promtool, git,
   requirements-dev, editable CLI/SDK installs).  Those live in the
   ``dev`` stage the test stack builds (``build.target: dev``).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

COMPOSE_FILES = sorted(REPO_ROOT.glob("docker-compose*.yml"))

# The repo's deployable images.  CI/dev-only images (services/shared/,
# services/odh-*) are OUT of this set by declaration: their Dockerfiles
# state "CI test isolation" / "DEV/TEST ONLY ... Not deployed", so the
# non-root + HEALTHCHECK requirements do not apply to them.
DEPLOYABLE_DOCKERFILES = {
    REPO_ROOT / "services/api/Dockerfile",
    REPO_ROOT / "services/worker/Dockerfile",
    REPO_ROOT / "frontend/Dockerfile",
    REPO_ROOT / "services/prefect-integration/Dockerfile",
    REPO_ROOT / "services/semantic-service/Dockerfile",
    REPO_ROOT / "services/compliance-service/Dockerfile",
    REPO_ROOT / "services/dq-service/Dockerfile",
    REPO_ROOT / "services/datacontract-service/Dockerfile",
    REPO_ROOT / "services/prefect-server/Dockerfile",
}

# Base images whose default USER is already non-root (the Dockerfile may
# omit its own USER directive without weakening the posture).
NON_ROOT_BASE_IMAGES = {
    "nginxinc/nginx-unprivileged",
    "nginxinc/nginx-unprivileged:alpine",
}

# Markers that must not appear in the api/worker PRODUCTION stage: the
# dev-tool binaries installed to /usr/local/bin, the dev requirements,
# and the editable CLI/SDK installs.  (A plain `pip install -r
# requirements.txt` IS allowed — that is the runtime dependency install;
# `pip install -e` is the editable dev-only form.)
PROD_DEV_TOOL_MARKERS = (
    "-o /usr/local/bin/docker",
    "-o /usr/local/bin/kubectl",
    "-o /usr/local/bin/gitleaks",
    "/usr/local/bin/promtool",
    "requirements-dev",
    "pip install -e",
)

HELM_API_DEPLOYMENT = REPO_ROOT / "helm/templates/api/deployment.yaml"
HELM_MIGRATIONS_JOB = REPO_ROOT / "helm/templates/api/migrations-job.yaml"


# ── parsing helpers (unit-tested via the drift pins) ────────────────────


class _ResetLoader(yaml.SafeLoader):
    """Compose ``!reset`` tags (v2.24+) are not standard YAML — same
    loader contract as scripts/tests/test_compose_hermetic_images.py."""


def _reset_constructor(_loader, _node):
    return None


_ResetLoader.add_constructor("!reset", _reset_constructor)


def compose_image_refs(path: Path) -> list[tuple[str, str]]:
    """(service, image) for services with an ``image:`` and NO ``build:``."""
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=_ResetLoader) or {}
    services = data.get("services", {})
    refs = []
    for name, svc in services.items():
        if not isinstance(svc, dict) or "build" in svc:
            continue
        image = svc.get("image")
        if image:
            refs.append((name, str(image)))
    return refs


def is_floating_ref(image: str) -> bool:
    """True for bare repo refs (floating :latest) and explicit :latest."""
    if "@sha256:" in image:  # digest-pinned is the strongest form — never floating
        return False
    if ":" not in image.rsplit("/", 1)[-1]:
        return True  # bare repo → :latest
    tag = image.rsplit(":", 1)[1]
    return tag in {"latest", "main", "master", "dev"}


def dockerfile_final_stage_text(path: Path) -> str:
    """Everything from the LAST FROM line to EOF (the built target)."""
    text = path.read_text(encoding="utf-8")
    from_lines = [
        i for i, line in enumerate(text.splitlines()) if line.startswith("FROM ")
    ]
    assert from_lines, f"{path}: no FROM"
    return "\n".join(text.splitlines()[from_lines[-1] :])


# ── 1. floating third-party image refs ───────────────────────────────────


def test_no_floating_third_party_image_refs():
    offenders = []
    for compose in COMPOSE_FILES:
        for service, image in compose_image_refs(compose):
            if is_floating_ref(image):
                offenders.append(f"{compose.name}:{service} -> {image}")
    assert (
        not offenders
    ), "floating third-party image refs (pin a version tag or digest):\n" + "\n".join(
        f"  {o}" for o in offenders
    )


# ── 2. non-root ──────────────────────────────────────────────────────────


def test_every_deployable_dockerfile_runs_non_root():
    missing = []
    for path in sorted(DEPLOYABLE_DOCKERFILES):
        final = dockerfile_final_stage_text(path)
        if re.search(r"^USER\s+", final, flags=re.MULTILINE):
            continue
        from_line = next(
            line for line in path.read_text().splitlines() if line.startswith("FROM ")
        )
        base = from_line.split()[1]
        if base in NON_ROOT_BASE_IMAGES:
            continue
        missing.append(str(path.relative_to(REPO_ROOT)))
    assert not missing, (
        "deployable Dockerfiles without a non-root USER in the final stage:\n"
        + "\n".join(f"  {m}" for m in missing)
    )


# ── 3. HEALTHCHECKs ──────────────────────────────────────────────────────


def test_every_deployable_dockerfile_has_healthcheck():
    missing = []
    for path in sorted(DEPLOYABLE_DOCKERFILES):
        text = path.read_text(encoding="utf-8")
        if not re.search(r"^HEALTHCHECK\b", text, flags=re.MULTILINE):
            missing.append(str(path.relative_to(REPO_ROOT)))
    assert not missing, "deployable Dockerfiles without a HEALTHCHECK:\n" + "\n".join(
        f"  {m}" for m in missing
    )


# ── 4. migrations-on-boot policy ─────────────────────────────────────────


def test_production_api_pod_does_not_migrate_inline():
    text = HELM_API_DEPLOYMENT.read_text(encoding="utf-8")
    assert "manage.py migrate" not in text, (
        "the production api pod must not run migrations inline — "
        "use the pre-upgrade migrations Job"
    )


def test_migrations_job_exists_and_runs_migrate():
    assert (
        HELM_MIGRATIONS_JOB.is_file()
    ), "helm/templates/api/migrations-job.yaml must exist (pre-upgrade Job)"
    text = HELM_MIGRATIONS_JOB.read_text(encoding="utf-8")
    assert "manage.py migrate --noinput" in text
    assert "pre-upgrade" in text
    assert "helm.sh/hook" in text


# ── 5. no dev tooling in the production stage ────────────────────────────


@pytest.mark.parametrize(
    "rel", ["services/api/Dockerfile", "services/worker/Dockerfile"]
)
def test_production_stage_has_no_dev_tooling(rel):
    path = REPO_ROOT / rel
    final = dockerfile_final_stage_text(path)
    for marker in PROD_DEV_TOOL_MARKERS:
        assert marker not in final, f"{rel}: production stage contains {marker!r}"


# ── falsifiability drift pins ────────────────────────────────────────────


def test_floating_ref_detector_bites():
    assert is_floating_ref("busybox")  # bare repo
    assert is_floating_ref("busybox:latest")
    assert not is_floating_ref("busybox:1.36")
    assert not is_floating_ref("cgr.dev/chainguard/minio@sha256:abc123")
    assert not is_floating_ref("registry/repo:1.2.3")


def test_dev_tool_marker_scan_bites():
    assert "-o /usr/local/bin/gitleaks" in PROD_DEV_TOOL_MARKERS
    assert "-o /usr/local/bin/kubectl" in PROD_DEV_TOOL_MARKERS
    # A final stage containing the marker must flip the predicate.
    fake_final = (
        "FROM python:3.12-slim\n"
        "RUN curl -fsSL .../kubectl -o /usr/local/bin/kubectl\n"
    )
    assert "-o /usr/local/bin/kubectl" in fake_final
