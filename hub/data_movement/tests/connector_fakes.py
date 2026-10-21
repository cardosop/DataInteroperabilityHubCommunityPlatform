"""Real in-memory source connectors for data_movement tests.

No mocks: real classes with configurable behavior, mirroring the sibling
convention in ``hub/apps/scheduled_ingestion/tests/connector_fakes.py``.
The dlt spine downloads source file CONTENT through the connector for
catalog-record creation (W3.8 — R2-P7/D6 parity), so the suites that run
the spine inject one of these at the sanctioned
``_get_source_connector_or_fail`` seam instead of dialing a warehouse.
"""


class _FakeConnectorResult:
    """Result type for connector.download_file (real object, not a mock)."""

    def __init__(self, status_value="SUCCESS", message="OK"):
        self.status = type("_Status", (), {"value": status_value})()
        self.message = message


class FakeSourceConnector:
    """Real in-memory source connector for tests. No mocks; configurable
    behavior. Implements discover_files, get_file_metadata,
    download_file, test_connection."""

    def __init__(
        self,
        contents=None,
        discover_files_result=None,
        download_status="SUCCESS",
        download_raises=None,
        download_fail_message="Download failed",
        default_content=b"id,name\n1,alpha\n2,beta\n",
    ):
        # per-key content bytes: ``download_file`` serves the fixture
        # payload for the requested key; a key missing from ``contents``
        # falls back to ``default_content`` (the spine suites mostly pin
        # the COUNT contract, not per-file bytes).
        self.contents = contents if contents is not None else {}
        self.default_content = default_content
        self.discover_files_result = discover_files_result
        self.download_status = download_status
        self.download_raises = download_raises
        self.download_fail_message = download_fail_message
        self.download_calls: list[str] = []

    def discover_files(self, config, pattern):
        if self.discover_files_result is not None:
            return list(self.discover_files_result)
        return []

    def get_file_metadata(self, config, file_path):
        return {}

    def download_file(self, config, file_path, dest_path):
        self.download_calls.append(file_path)
        if self.download_raises:
            raise self.download_raises
        if self.download_status != "SUCCESS":
            return _FakeConnectorResult(self.download_status, self.download_fail_message)
        payload = self.contents.get(file_path, self.default_content)
        with open(dest_path, "wb") as f:
            f.write(payload)
        return _FakeConnectorResult("SUCCESS", "OK")

    def test_connection(self, config):
        return True
