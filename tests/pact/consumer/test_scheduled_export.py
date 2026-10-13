"""
Pact consumer test: Scheduled Export → /api/v1/scheduled-exports/ (281.A.2.2).

Consumer #5 of 5 critical API consumers.
Written against the pact-python 3.x FFI DSL (``match.like`` / ``match.regex``,
``pact.serve()`` context manager, ``write_file`` on module teardown).
"""

import pytest

try:
    import pact as _pact
    from pact import Pact, match
except ImportError:
    from envpolicy import environment_guard

    environment_guard("pact-python is not installed — install it to run the Pact consumer tests")
    pytest.skip("pact-python is not installed", allow_module_level=True)

PACT_DIR = "tests/pact/pacts"


@pytest.fixture
def export_pact():
    """Per-test Pact for the Scheduled Export consumer.

    The FFI pact handle is finalized by the first ``serve()`` session, so
    each test gets a fresh Pact. ``write_file(overwrite=False)`` MERGES
    the test's interactions into the committed pact file on teardown.
    """
    pact = Pact(consumer="ScheduledExport", provider="MeshantAPI")
    yield pact
    pact.write_file(PACT_DIR, overwrite=False)


class TestScheduledExportContract:
    """Scheduled Export consumer expectations."""

    def test_list_exports(self, export_pact):
        pact = export_pact
        (
            pact.upon_receiving("list scheduled exports")
            .given("scheduled exports exist")
            .with_request("GET", "/api/v1/scheduled-exports/")
            .with_query_parameter("limit", "50")
            .with_query_parameter("offset", "0")
            .will_respond_with(200)
            .with_body(
                {
                    "count": 1,
                    "results": [
                        {
                            "id": match.regex("export-uuid", regex=r"^[0-9a-f-]+$"),
                            "name": match.like("Daily Sales Export"),
                            "status": match.like("ACTIVE"),
                            "schedule": match.like("0 6 * * *"),
                            "format": match.like("CSV"),
                        }
                    ],
                },
                part="Response",
            )
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.get(
                f"{srv.url}/api/v1/scheduled-exports/", params={"limit": 50, "offset": 0}
            )
            assert result.status_code == 200

    def test_trigger_export(self, export_pact):
        pact = export_pact
        (
            pact.upon_receiving("trigger scheduled export")
            .given("export is active")
            .with_request("POST", "/api/v1/scheduled-exports/export-uuid/trigger/")
            .will_respond_with(200)
            .with_body(
                {
                    "id": match.like("run-uuid"),
                    "status": match.like("QUEUED"),
                    "triggered_at": match.like("2026-05-15T00:00:00Z"),
                },
                part="Response",
            )
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.post(f"{srv.url}/api/v1/scheduled-exports/export-uuid/trigger/")
            assert result.status_code == 200

    def test_get_run_history(self, export_pact):
        pact = export_pact
        (
            pact.upon_receiving("get export run history")
            .given("export has run history")
            .with_request("GET", "/api/v1/scheduled-exports/export-uuid/runs/")
            .with_query_parameter("limit", "20")
            .with_query_parameter("offset", "0")
            .will_respond_with(200)
            .with_body(
                {
                    "results": [
                        {
                            "id": match.like("run-uuid"),
                            "status": match.like("COMPLETED"),
                            "row_count": match.like(1000),
                            "started_at": match.like("2026-05-15T00:00:00Z"),
                            "completed_at": match.like("2026-05-15T00:05:00Z"),
                        }
                    ],
                },
                part="Response",
            )
        )

        import requests

        with pact.serve(addr="localhost", port=0, raises=False) as srv:
            result = requests.get(
                f"{srv.url}/api/v1/scheduled-exports/export-uuid/runs/",
                params={"limit": 20, "offset": 0},
            )
            assert result.status_code == 200
