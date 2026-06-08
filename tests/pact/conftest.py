"""Pact shared fixtures (280.B.5.1)."""
import pytest

PACT_DIR = "tests/pact/pacts"


@pytest.fixture(scope="session")
def pact_broker_url():
    """Pact Broker URL. When not set, local file-based verification is used."""
    import os
    return os.environ.get("PACT_BROKER_URL", "")


@pytest.fixture(scope="session")
def pact_dir():
    return PACT_DIR
