"""Phase 313.0 — Secret rotation verification (repo-side acceptance).

Encodes the acceptance criteria of openspec preprod01 tasks 313.0.1/313.0.2:

  1. No real (non-template) env file is git-tracked — the root cause of the
     leak was real secrets living in tracked files.
  2. No secret value present in a local env file appears in git history.
  3. Secret values are unique across env files (the original sin was
     .env.dev and .env.staging sharing one SECRET_KEY).
  4. Postgres TLS material is freshly generated (absent from history),
     syntactically valid, and preserves the expected CN/SAN contract.
  5. gitleaks reports the tracked tree clean (skipped when binary absent,
     per repo convention).

Real tools only — no mocks or stubs: every assertion shells out to the real
git/gitleaks/openssl binaries or parses real files. History-based tests skip
on shallow clones (CI fetch-depth 1 makes them vacuous there); the publish
pipeline re-runs them against full history before every public sync.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Keys whose values are real secrets (rotation scope, Phase 313.0).
# Scoped to credential-shaped keys only — public identifiers such as
# AWS_DATA_EXCHANGE_TEST_DATASET_ID are not secrets and must not be flagged.
SECRET_KEY_RE = re.compile(
    r"^(?:SECRET_KEY|JWT_SECRET_KEY|ENCRYPTION_KEY|"
    r"CKAN_(?:TEST_API_KEY|DADOS_GOV_BR_API_KEY)|DADOS_GOV_BR_API_KEY|"
    r"SNOWFLAKE_TOKEN|AZURE_CLIENT_SECRET|STRIPE_SECRET_KEY|"
    r"AWS_DATA_EXCHANGE_(?:ACCESS_KEY_ID|SECRET_ACCESS_KEY)|DATABRICKS_TOKEN|"
    r"ATHENA_AWS_(?:ACCESS_KEY_ID|SECRET_ACCESS_KEY)|"
    r".*PASSWORD|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY)="
)

# Keys that must be unique per environment file.
UNIQUE_KEYS = (
    "SECRET_KEY",
    "POSTGRES_PASSWORD",
    "FUSEKI_ADMIN_PASSWORD",
    "MINIO_ROOT_PASSWORD",
    "GRAFANA_ADMIN_PASSWORD",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
)

# Files scanned for history-absence (all local env files, incl. compose's
# interpolation source).
LOCAL_ENV_FILES = (".env", ".env.dev", ".env.staging", ".env.test", ".env.e2e")

# Environments compared for cross-environment uniqueness. Root .env is NOT
# included: it is docker-compose's interpolation source and MUST mirror the
# dev environment (asserted separately) — duplication there is by design.
ENV_FILES_BY_ENVIRONMENT = (".env.dev", ".env.staging", ".env.test")

# Infra keys that compose interpolates from root .env and that must therefore
# mirror the .env.dev values (interpolation source ↔ container env_file).
MIRROR_KEYS = (
    "POSTGRES_PASSWORD",
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "FUSEKI_ADMIN_PASSWORD",
    "GRAFANA_ADMIN_PASSWORD",
)

CERTS_DIR = REPO_ROOT / "infrastructure" / "postgres" / "certs"
CERT_FILES = ("ca.crt", "ca.key", "pgbouncer.crt", "pgbouncer.key", "postgres.crt", "postgres.key")

pytestmark = pytest.mark.security


def _run(*args: str, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, cwd=str(cwd), timeout=300)


def _git(*args: str) -> str:
    proc = _run("git", *args)
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc.stdout


def _history_is_shallow() -> bool:
    proc = _run("git", "rev-parse", "--is-shallow-repository")
    return proc.stdout.strip() == "true"


requires_full_history = pytest.mark.skipif(
    _history_is_shallow(), reason="shallow clone — history-based assertions are vacuous"
)


def _extract_secret_values(path: Path) -> dict[str, str]:
    """Return {key: value} for secret-shaped assignments; skip comments/empty.

    DATABASE_URL is special-cased: it embeds credentials, so it is treated as
    a secret only when it targets a non-local host (a deployed database).
    Local development URLs (localhost/127.0.0.1) are documented defaults,
    not secrets.
    """
    from urllib.parse import urlsplit

    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or not SECRET_KEY_RE.match(line):
            continue
        key, _, raw = line.partition("=")
        value = raw.strip().strip('"').strip("'")
        if not value:
            continue
        if key == "DATABASE_URL":
            host = (urlsplit(value).hostname or "").lower()
            if host not in ("localhost", "127.0.0.1"):
                values[key] = value
            continue
        values[key] = value
    return values


def _in_history(value: str) -> bool:
    proc = _run("git", "log", "--all", "--oneline", "-S", value)
    return bool(proc.stdout.strip())


def _existing_env_files() -> list[Path]:
    return [REPO_ROOT / name for name in LOCAL_ENV_FILES if (REPO_ROOT / name).exists()]


def test_no_real_env_file_is_git_tracked():
    """Root cause: real env files must never be tracked again (313.0.1)."""
    tracked = _git("ls-files").splitlines()
    offenders = [
        p
        for p in tracked
        if re.match(r"^\.env($|\..*$)", p) and "template" not in p and "example" not in p
    ]
    assert not offenders, (
        "real env files are git-tracked — rotation is incomplete; "
        f"untrack them and rely on templates: {offenders}"
    )


@requires_full_history
def test_local_env_secret_values_absent_from_git_history():
    """Acceptance: current secret values must not appear anywhere in history."""
    offenders = set()
    for path in _existing_env_files():
        for key in _extract_secret_values(path):
            value = _extract_secret_values(path)[key]
            if _in_history(value):
                offenders.add(path.name)
    assert not offenders, (
        f"secret values from local env files are still present in git history: "
        f"{sorted(offenders)} — rotate these values (313.0.1)"
    )


@requires_full_history
def test_secret_values_unique_across_env_files():
    """The original leak shared one SECRET_KEY across dev/staging — never again.

    Uniqueness is enforced ACROSS environments (.env.dev vs .env.staging vs
    .env.test). Root .env is excluded: it is compose's interpolation source
    and mirrors the dev environment by design (see test_root_env_mirrors_dev).
    """
    per_key: dict[str, list[str]] = {}
    for name in ENV_FILES_BY_ENVIRONMENT:
        path = REPO_ROOT / name
        if not path.exists():
            continue
        for key, value in _extract_secret_values(path).items():
            if key in UNIQUE_KEYS:
                per_key.setdefault(key, []).append(value)
    duplicates = {key for key, values in per_key.items() if len(set(values)) != len(values)}
    assert not duplicates, (
        f"secret values shared across environments (unique values required per environment): "
        f"{sorted(duplicates)}"
    )


def test_root_env_mirrors_dev_environment():
    """Root .env is docker-compose's interpolation source (${VAR:?...}).

    It MUST carry the same infra credentials as .env.dev — otherwise the
    postgres/minio/fuseki containers (interpolated from root .env) and the
    api-service container (env_file .env.dev) disagree and the stack breaks.
    """
    root_path = REPO_ROOT / ".env"
    dev_path = REPO_ROOT / ".env.dev"
    if not root_path.exists() or not dev_path.exists():
        pytest.skip("root .env or .env.dev absent — mirror assertion not applicable")
    root_values = _extract_secret_values(root_path)
    dev_values = _extract_secret_values(dev_path)
    drift = [
        key
        for key in MIRROR_KEYS
        if key in dev_values and root_values.get(key) != dev_values[key]
    ]
    assert not drift, (
        "root .env (compose interpolation source) drifted from .env.dev (container env_file) — "
        f"the dev stack would use mismatched credentials: {sorted(drift)}"
    )


@requires_full_history
def test_postgres_tls_material_absent_from_history_and_valid():
    """Regenerated TLS material must be new (not in history) and keep the CN/SAN contract."""
    missing = [f for f in CERT_FILES if not (CERTS_DIR / f).exists()]
    assert not missing, f"missing TLS material: {missing}"

    in_history = []
    for name in CERT_FILES:
        body_lines = (CERTS_DIR / name).read_text().splitlines()
        # Pick a base64 body line as a distinctive fragment for -S matching.
        fragment = next(
            (ln for ln in body_lines if len(ln) >= 40 and "BEGIN" not in ln and "END" not in ln),
            None,
        )
        assert fragment, f"{name}: no usable body fragment"
        if _in_history(fragment):
            in_history.append(name)
    assert not in_history, (
        f"TLS material still present in git history — regenerate certs (313.0.1): {in_history}"
    )

    # Validity + contract: CN/SANs preserved, leaves signed by the new CA,
    # keys match certs (real openssl, no mocks).
    for name in ("ca", "pgbouncer", "postgres"):
        cert = CERTS_DIR / f"{name}.crt"
        proc = _run("openssl", "x509", "-in", str(cert), "-noout", "-checkend", "86400")
        assert proc.returncode == 0, f"{name}.crt not yet valid or expired: {proc.stderr}"
    ca_subject = _run("openssl", "x509", "-in", str(CERTS_DIR / "ca.crt"), "-noout", "-subject")
    assert "DataInteroperabilityHub Internal CA" in ca_subject.stdout
    for name, expected_dns in (("pgbouncer", "pgbouncer"), ("postgres", "postgres")):
        sans = _run(
            "openssl", "x509", "-in", str(CERTS_DIR / f"{name}.crt"), "-noout", "-ext", "subjectAltName"
        ).stdout
        assert expected_dns in sans, f"{name}.crt lost expected SAN {expected_dns}: {sans}"
        verify = _run(
            "openssl", "verify", "-CAfile", str(CERTS_DIR / "ca.crt"), str(CERTS_DIR / f"{name}.crt")
        )
        assert verify.returncode == 0, f"{name}.crt not signed by new CA: {verify.stdout}{verify.stderr}"
        mod_cert = _run("openssl", "x509", "-in", str(CERTS_DIR / f"{name}.crt"), "-noout", "-modulus").stdout
        mod_key = _run("openssl", "rsa", "-in", str(CERTS_DIR / f"{name}.key"), "-noout", "-modulus").stdout
        assert mod_cert == mod_key, f"{name}: cert and key modulus mismatch"


def test_gitleaks_reports_tree_clean():
    """313.0.2: gitleaks clean on the tracked tree (skipped when CLI absent — repo convention)."""
    gitleaks = shutil.which("gitleaks")
    if gitleaks is None:
        pytest.skip("gitleaks CLI not installed — CI runs gitleaks/gitleaks-action@v2")
    proc = _run(
        gitleaks,
        "detect",
        "--source",
        str(REPO_ROOT),
        "--config",
        str(REPO_ROOT / ".gitleaks.toml"),
        "--redact",
        "--no-banner",
        "--log-level=warn",
    )
    assert proc.returncode == 0, (
        f"gitleaks found findings on the tracked tree (values redacted):\n{proc.stdout}"
    )


# ---------------------------------------------------------------------------
# Compose credential consistency — rotation must never break the local stacks.
# Root cause of the 313.0 regression: compose interpolates ${VAR:?...} from
# root .env while api containers read .env.dev via env_file; rotating one
# without the other breaks the stack.
# ---------------------------------------------------------------------------

requires_docker = pytest.mark.skipif(shutil.which("docker") is None, reason="docker CLI not available")
compose_tests = pytest.mark.docker_compose_runtime


def _compose(*files: str, env_file: str | None = None) -> subprocess.CompletedProcess:
    args = ["docker", "compose"]
    for f in files:
        args += ["-f", str(REPO_ROOT / f)]
    if env_file:
        args += ["--env-file", str(REPO_ROOT / env_file)]
    args += ["config"]
    return _run(*args)


@requires_docker
@compose_tests
def test_dev_compose_resolves_after_rotation():
    """docker-compose.yml interpolates required vars from root .env."""
    proc = _compose("docker-compose.yml")
    assert proc.returncode == 0, f"dev compose no longer resolves: {proc.stderr.strip()[:500]}"


@requires_docker
@compose_tests
def test_test_compose_resolves_after_rotation():
    """The test stack interpolates from .env.test (Makefile uses --env-file .env.test)."""
    proc = _compose("docker-compose.test.yml", env_file=".env.test")
    assert proc.returncode == 0, f"test compose no longer resolves: {proc.stderr.strip()[:500]}"


@requires_docker
@compose_tests
def test_dev_compose_credentials_consistent_with_env_dev():
    """Postgres container (interpolated from root .env) must match api DATABASE_URL (.env.dev)."""
    try:
        import yaml
    except ImportError:  # pragma: no cover — env without pyyaml
        pytest.skip("pyyaml not available — cannot parse compose config output")

    proc = _compose("docker-compose.yml")
    assert proc.returncode == 0, f"dev compose does not resolve: {proc.stderr.strip()[:500]}"
    config = yaml.safe_load(proc.stdout)
    postgres_pw = config["services"]["postgres"]["environment"]["POSTGRES_PASSWORD"]
    minio_pw = config["services"]["minio"]["environment"]["MINIO_ROOT_PASSWORD"]

    dev_values = _extract_secret_values(REPO_ROOT / ".env.dev")
    from urllib.parse import urlsplit

    db_url = next(
        ln.split("=", 1)[1].strip().strip('"')
        for ln in (REPO_ROOT / ".env.dev").read_text().splitlines()
        if ln.startswith("DATABASE_URL=")
    )
    db_pw = urlsplit(db_url).password
    assert postgres_pw == db_pw, "postgres container password diverges from .env.dev DATABASE_URL"
    assert minio_pw == dev_values["AWS_SECRET_ACCESS_KEY"], (
        "minio container password diverges from .env.dev S3 credentials"
    )
