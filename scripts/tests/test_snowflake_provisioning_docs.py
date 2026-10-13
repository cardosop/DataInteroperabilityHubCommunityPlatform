"""Pins for the Snowflake provisioning recipe (close-test-coverage-gaps task 7.1).

The recipe documentation must stay in sync with the CODE contract
(hub/apps/integrations/tests/test_snowflake_connector.py's env-var contract +
the connector's PAT-as-password semantics) and the runbook INDEX mirror
discipline (byte-identical canonical/mirror pair). No Django, no services —
plain file reads against the live repo tree.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

RUNBOOK = (
    REPO / "docs" / "docs" / "runbooks" / "RB-INTEGRATIONS-002-snowflake-sandbox-provisioning.md"
)
INDEX_CANONICAL = REPO / "docs" / "runbooks" / "INDEX.md"
INDEX_MIRROR = REPO / "docs" / "docs" / "runbooks" / "INDEX.md"
HOST_ENV_DOC = REPO / "docs" / "runbooks" / "HOST_SIDE_VERIFICATION.md"
ENV_MATRIX_DOC = REPO / "docs" / "test-infrastructure" / "host-env-matrix.md"
CONNECTOR_TEST = REPO / "hub" / "apps" / "integrations" / "tests" / "test_snowflake_connector.py"
CONNECTORS_E2E_TEST = REPO / "hub" / "apps" / "integrations" / "tests" / "test_connectors_e2e.py"

REQUIRED_ENV = ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_TOKEN")
OPTIONAL_ENV = ("SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_ROLE", "SNOWFLAKE_DATABASE")


def test_runbook_exists():
    assert RUNBOOK.is_file(), "the Snowflake provisioning runbook must exist"


def test_runbook_documents_the_env_contract():
    text = RUNBOOK.read_text()
    for var in (*REQUIRED_ENV, *OPTIONAL_ENV):
        assert f"`{var}`" in text, f"runbook must document {var}"
    # PAT semantics: password-equivalent credential, NOT an OAuth bearer token
    assert "password" in text.lower()
    assert "oauth" in text.lower()


def test_runbook_documents_the_w16_behavior():
    text = RUNBOOK.read_text()
    assert "W16" in text
    assert "EnvironmentFailureError" in text
    assert "skip" in text.lower()


def test_index_pair_byte_identical_and_lists_runbook():
    canonical = INDEX_CANONICAL.read_bytes()
    mirror = INDEX_MIRROR.read_bytes()
    assert canonical == mirror, "runbook INDEX mirror must stay byte-identical"
    name = "RB-INTEGRATIONS-002-snowflake-sandbox-provisioning.md"
    assert name in INDEX_CANONICAL.read_text()


def test_host_env_docs_carry_the_snowflake_lines():
    host_text = HOST_ENV_DOC.read_text()
    for var in (*REQUIRED_ENV, *OPTIONAL_ENV):
        assert f"{var}=" in host_text, f"HOST_SIDE_VERIFICATION.md must carry {var}"
    assert RUNBOOK.name in host_text
    matrix_text = ENV_MATRIX_DOC.read_text()
    assert "SNOWFLAKE_ACCOUNT" in matrix_text
    assert "SNOWFLAKE_TOKEN" in matrix_text
    assert "EnvironmentFailureError" in matrix_text


def test_snowflake_env_branches_are_w16_governed():
    """The Snowflake credential branches must use the envpolicy helpers.

    A raw ``unittest.SkipTest`` on the missing-credentials branch would
    silently skip under CI=true — the exact failure class W16 retired.
    """
    for module in (CONNECTOR_TEST, CONNECTORS_E2E_TEST):
        text = module.read_text()
        assert "from envpolicy import" in text, f"{module.name} must import envpolicy"
        marker = "SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER"
        idx = text.find(marker)
        assert idx != -1, f"{module.name} must carry the missing-creds message"
        # The skip_or_fail(...) call precedes its message argument — look both ways.
        window = text[max(0, idx - 200) : idx + 400]
        assert "skip_or_fail" in window, f"{module.name}: the branch must use skip_or_fail"
        assert "unittest.SkipTest" not in window, (
            f"{module.name}: the Snowflake branch must not use raw unittest.SkipTest"
        )
