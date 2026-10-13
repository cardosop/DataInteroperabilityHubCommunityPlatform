"""
Contract tests for the Postgres/PgBouncer TLS material
(oss-release-remediation W0.5 — regenerate infrastructure/postgres/certs).

The generation script is infrastructure/postgres/ssl-setup.sh. These pins
run the REAL script (copied into a tmp dir — the script generates next to
itself) with real openssl — no mocks or stubs — and validate the output:

- all 6 artifacts exist (ca / postgres / pgbouncer — cert + key each);
- keys are RSA-4096 and the certs carry the 3650-day validity the
  script's contract declares;
- both server certs chain to the generated CA (`openssl verify`);
- each key matches its cert (modulus equality);
- key files are 0600;
- the script is idempotent (a re-run without --force leaves the
  artifacts untouched).

Falsifiability: the same validators run against a tampered fixture
(swapped key) and MUST detect the mismatch — the pin is not vacuous.
"""

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
SSL_SETUP = Path(scripts_dir).parent / "infrastructure" / "postgres" / "ssl-setup.sh"

ARTIFACTS = ("ca", "postgres", "pgbouncer")


@pytest.fixture(scope="module")
def generated_certs(tmp_path_factory):
    """A real ssl-setup.sh run in a tmp dir (the script builds next to itself)."""
    if not SSL_SETUP.is_file():
        pytest.skip("infrastructure/postgres/ssl-setup.sh not present")
    if shutil.which("openssl") is None:
        pytest.skip("openssl not available")
    target = tmp_path_factory.mktemp("postgres-gen")
    shutil.copy2(SSL_SETUP, target / "ssl-setup.sh")
    result = subprocess.run(
        ["bash", str(target / "ssl-setup.sh"), "--force"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    certs_dir = target / "certs"
    return certs_dir


def _openssl(*args: str) -> str:
    return subprocess.run(["openssl", *args], capture_output=True, text=True, check=True).stdout


class TestArtifactsExist:
    def test_all_six_files_are_generated(self, generated_certs):
        for name in ARTIFACTS:
            assert (generated_certs / f"{name}.key").is_file(), f"{name}.key missing"
            assert (generated_certs / f"{name}.crt").is_file(), f"{name}.crt missing"

    def test_key_files_are_0600(self, generated_certs):
        for name in ARTIFACTS:
            mode = (generated_certs / f"{name}.key").stat().st_mode & 0o777
            assert mode == 0o600, f"{name}.key mode is {oct(mode)}"


class TestKeyStrength:
    def test_keys_are_rsa_4096(self, generated_certs):
        for name in ARTIFACTS:
            text = _openssl("rsa", "-in", str(generated_certs / f"{name}.key"), "-text", "-noout")
            assert "Private-Key: (4096 bit" in text, f"{name}.key is not RSA-4096"


class TestValidity:
    def test_certs_are_valid_for_3650_days(self, generated_certs):
        # -checkend prints "will (not) expire" — the exit code is NOT
        # reliable on OpenSSL 3.6.0 (verified: always 0), so the verdict
        # text is the oracle.
        for name in ARTIFACTS:
            cert = generated_certs / f"{name}.crt"
            within = subprocess.run(
                ["openssl", "x509", "-in", str(cert), "-noout", "-checkend", str(3649 * 86400)],
                capture_output=True,
                text=True,
                check=False,
            )
            assert "will not expire" in within.stdout, f"{name}.crt is NOT valid >= 3649 days"
            beyond = subprocess.run(
                ["openssl", "x509", "-in", str(cert), "-noout", "-checkend", str(3651 * 86400)],
                capture_output=True,
                text=True,
                check=False,
            )
            assert "will expire" in beyond.stdout, (
                f"{name}.crt outlives the 3650-day contract "
                "(-checkend 3651d printed 'will not expire')"
            )


class TestChainAndMatching:
    def test_server_certs_chain_to_the_generated_ca(self, generated_certs):
        for name in ("postgres", "pgbouncer"):
            output = _openssl(
                "verify",
                "-CAfile",
                str(generated_certs / "ca.crt"),
                str(generated_certs / f"{name}.crt"),
            ).strip()
            assert f"{name}.crt: OK" in output, output

    def test_each_key_matches_its_cert(self, generated_certs):
        for name in ARTIFACTS:
            key_modulus = _openssl(
                "rsa", "-in", str(generated_certs / f"{name}.key"), "-noout", "-modulus"
            ).strip()
            cert_modulus = _openssl(
                "x509", "-in", str(generated_certs / f"{name}.crt"), "-noout", "-modulus"
            ).strip()
            assert key_modulus == cert_modulus, f"{name} key/cert modulus mismatch"


class TestIdempotency:
    def test_rerun_without_force_leaves_artifacts_untouched(self, generated_certs):
        before = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in generated_certs.iterdir()
        }
        setup_script = generated_certs.parent / "ssl-setup.sh"
        result = subprocess.run(
            ["bash", str(setup_script)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        after = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in generated_certs.iterdir()
        }
        assert before == after, "idempotent re-run changed the artifacts"


class TestTamperDetection:
    """The validators themselves are falsifiable — a swapped key MUST fail."""

    def test_swapped_key_breaks_the_matching_check(self, generated_certs, tmp_path):
        tampered = tmp_path / "tampered"
        shutil.copytree(generated_certs, tampered)
        # Swap postgres.key for the CA key — same RSA family, wrong pair.
        shutil.copy2(tampered / "ca.key", tampered / "postgres.key")
        key_modulus = _openssl(
            "rsa", "-in", str(tampered / "postgres.key"), "-noout", "-modulus"
        ).strip()
        cert_modulus = _openssl(
            "x509", "-in", str(tampered / "postgres.crt"), "-noout", "-modulus"
        ).strip()
        assert key_modulus != cert_modulus, (
            "the tampered fixture no longer differs — the pin is vacuous"
        )
