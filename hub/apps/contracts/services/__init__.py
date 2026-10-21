"""Contract services subpackage (Phase 250.2.B).

Historically this was a single-file module
``hub/apps/contracts/services.py`` containing :class:`ContractService`
and :class:`ODPSService`. Phase 250.2.B introduces additional
service modules (starting with :mod:`schema_compare`) so the surface
was promoted to a package; the legacy ``services.py`` content lives
on at :mod:`.contract_service` and is re-exported here so the
existing ``from hub.apps.contracts.services import ContractService``
call sites stay binary-compatible.
"""

from .contract_service import ContractService, ODPSService
from .schema_compare import (
    SchemaCompareService,
    SchemaDriftResult,
)

__all__ = [
    "ContractService",
    "ODPSService",
    "SchemaCompareService",
    "SchemaDriftResult",
]
