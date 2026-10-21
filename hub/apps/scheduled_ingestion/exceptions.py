"""
Scheduled ingestion/export connector exceptions.

Raised when the source (or destination) connector factory is unavailable
or the configured source/destination type has no registered connector.
"""


class ConnectorNotAvailableError(Exception):
    """
    Raised when a connector cannot be obtained for the configured source or destination type.

    Use when _get_source_connector_factory() (or equivalent) returns None, or when
    get_connector(source_type) fails because the type is not registered (e.g. ValueError
    from SourceConnectorFactory/DestinationConnectorFactory). Ensures immediate,
    clear failure at job start instead of late failure during processing.
    """

    def __init__(
        self, connector_type: str, role: str = "source", message: str = "connector not registered"
    ):
        self.connector_type = connector_type
        self.role = role  # "source" or "destination"
        self.message = message
        super().__init__(f"{role} type {connector_type!r}: {message}")
