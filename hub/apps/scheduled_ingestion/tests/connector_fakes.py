"""
Real in-memory connector implementations for scheduled_ingestion tests.

No mocks: these are real classes with configurable behavior, used so tests
can exercise view/processor code without external connector services.
"""


class _DownloadResult:
    """Result type for connector.download_file (real object, not a mock)."""

    def __init__(self, status_value="SUCCESS", message="OK"):
        self.status = type("_Status", (), {"value": status_value})()
        self.message = message


class InMemoryConnector:
    """
    Real in-memory connector for tests. No mocks; configurable behavior.
    Implements discover_files, get_file_metadata, download_file,
    test_connection.
    """

    def __init__(
        self,
        files=None,
        file_content=None,
        metadata=None,
        download_status="SUCCESS",
        discover_raises=None,
        test_connection_result=True,
    ):
        self.files = files if files is not None else []
        self.file_content = file_content or b""
        self.metadata = metadata or {}
        self.download_status = download_status
        self.discover_raises = discover_raises
        self.test_connection_result = test_connection_result

    def discover_files(self, config, pattern):
        if self.discover_raises:
            raise self.discover_raises
        return self.files

    def get_file_metadata(self, config, file_path):
        return dict(self.metadata)

    def download_file(self, config, file_path, dest_path):
        if self.download_status != "SUCCESS":
            return _DownloadResult(self.download_status, "Download failed")
        with open(dest_path, "wb") as f:
            f.write(self.file_content)
        return _DownloadResult("SUCCESS", "OK")

    def test_connection(self, config):
        """Return configured success/failure for connection test (no mocks)."""
        return self.test_connection_result


class InMemoryConnectorFactory:
    """Factory that returns a real in-memory connector (no mocks)."""

    def __init__(self, connector):
        self.connector = connector

    def get_connector(self, source_type):
        return self.connector
