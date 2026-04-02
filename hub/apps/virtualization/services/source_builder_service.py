"""Source configuration / builder methods for VirtualizationService.

Currently empty — ``_map_source_type_to_connector_type`` lives in
``QueryServiceMixin`` because it is the only source-builder helper and
is tightly coupled to query-execution validation.  This module is
reserved for future source-configuration helpers (e.g., source template
builders, connection-string generators, source health checkers).
"""


class SourceBuilderServiceMixin:
    """Mixin reserved for source-configuration helpers."""

    pass
