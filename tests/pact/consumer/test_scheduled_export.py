"""
Pact consumer test: Scheduled Export → /api/v1/scheduled-exports/ (281.A.2.2).

Consumer #5 of 5 critical API consumers.
"""
import atexit
import pytest
from pact import Pact
from pact.matchers import Like, Term

PACT_DIR = "tests/pact/pacts"


@pytest.fixture(scope="module")
def export_pact():
    pact = Pact("ScheduledExport", "MeshantAPI")
    pact.with_specification("V4").with_pact_dir(PACT_DIR)
    with pact.start_mocking(port=1238):
        yield pact


class TestScheduledExportContract:
    """Scheduled Export consumer expectations."""

    def test_list_exports(self, export_pact):
        export_pact.given("scheduled exports exist").upon_receiving(
            "list scheduled exports"
        ).with_request("GET", "/api/v1/scheduled-exports/",
                       query="limit=50&offset=0").will_respond_with(200, body={
            "count": 1,
            "results": [{
                "id": Term(r"^[0-9a-f-]+$", "export-uuid"),
                "name": Like("Daily Sales Export"),
                "status": Like("ACTIVE"),
                "schedule": Like("0 6 * * *"),
                "format": Like("CSV"),
            }],
        })

        import requests
        result = requests.get("http://localhost:1238/api/v1/scheduled-exports/",
                              params={"limit": 50, "offset": 0})
        assert result.status_code == 200

    def test_trigger_export(self, export_pact):
        export_pact.given("export is active").upon_receiving(
            "trigger scheduled export"
        ).with_request("POST", "/api/v1/scheduled-exports/export-uuid/trigger/"
                       ).will_respond_with(200, body={
            "id": Like("run-uuid"),
            "status": Like("QUEUED"),
            "triggered_at": Like("2026-05-15T00:00:00Z"),
        })

        import requests
        result = requests.post(
            "http://localhost:1238/api/v1/scheduled-exports/export-uuid/trigger/"
        )
        assert result.status_code == 200

    def test_get_run_history(self, export_pact):
        export_pact.given("export has run history").upon_receiving(
            "get export run history"
        ).with_request("GET", "/api/v1/scheduled-exports/export-uuid/runs/",
                       query="limit=20&offset=0").will_respond_with(200, body={
            "results": [{
                "id": Like("run-uuid"),
                "status": Like("COMPLETED"),
                "row_count": Like(1000),
                "started_at": Like("2026-05-15T00:00:00Z"),
                "completed_at": Like("2026-05-15T00:05:00Z"),
            }],
        })

        import requests
        result = requests.get(
            "http://localhost:1238/api/v1/scheduled-exports/export-uuid/runs/",
            params={"limit": 20, "offset": 0},
        )
        assert result.status_code == 200
