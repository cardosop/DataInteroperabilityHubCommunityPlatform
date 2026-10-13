"""Phase 10 (openspec add-databricks-dlt-pipelines task 10.5) — the
Hub-config → DLT-spec mapping compiler (design D5: the compile, never
executes).

Hub movement configs compile into DLT pipeline spec DRAFTS — the
settings-level pieces the 10.4 create chain will allowlist: the target
catalog/schema, the target tables/views (the ingestion's source table,
the transformation's output-node targets), the source structure, and
the source contract's ODCS quality rules as DLT `expect` clauses
(severity error → action fail, warn → warn, absent severity → warn —
DLT's documented default; any OTHER severity refuses).

The refusal discipline is the 6.5 pre-flight's:

- a source whose contract fails validation REFUSES with ZERO spec
  emitted — the SAME ``ExportContractValidationError`` the movement
  pre-flight raises (``validate_export_contracts`` is REUSED for the
  export scope, never reimplemented),
- a config bit the mapping cannot represent REFUSES with
  ``DltSpecCompileError`` NAMING the bit (a key outside the mappable
  set, a wrong source/destination type, a missing target) — never a
  spec with the setting silently absent,
- an ODCS rule the mapping cannot turn into an expect clause (no name,
  no expression, an unknown severity, a duplicate clause name) REFUSES
  naming the rule — never a silently dropped expectation.

The emitted document is review-first: the caller stores it on the
pipeline row's ``settings`` before the 10.4 chain creates anything (the
clusters/libraries the operator attaches at review ride the chain's
gate, not this compiler). The P6 movement spine keeps its contracts
untouched — this module consumes the movement CONFIGS and the preflight
validation, never the movement executor.

PURE: reads only, zero side effects by construction (the preflight's
discipline).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hub.apps.contracts.models import Contract
    from hub.apps.scheduled_export.models import ScheduledExport
    from hub.apps.scheduled_ingestion.models import ScheduledIngestion
    from hub.apps.transformation.models import TransformationPipeline

# The destination-config keys the export mapping can represent — every
# other key REFUSES (a staging_volume override is the movement spine's
# mechanics, never a DLT spec setting).
_EXPORT_MAPPABLE_KEYS = frozenset({"host", "http_path", "catalog", "schema"})
# The source-config keys the ingestion mapping can represent.
_INGESTION_MAPPABLE_KEYS = frozenset(
    {"host", "http_path", "catalog", "schema", "warehouse_connection_id", "table", "cursor_field"}
)
# ODCS rule severity → DLT expect action. An absent severity takes the
# DLT documented default (warn); any OTHER severity refuses (never a
# silently mapped action).
_SEVERITY_ACTIONS = {"error": "fail", "warn": "warn"}

_SPEC_KIND = "dlt_pipeline_spec_draft"
_SPEC_SCHEMA_VERSION = 1


class DltSpecCompileError(Exception):
    """A config bit the mapping cannot represent — the refusal NAMES the
    bit (never a silently dropped setting)."""

    code = "DATABRICKS_DLT_SPEC_UNMAPPABLE"

    def __init__(self, bit: str, detail: str):
        self.bit = bit
        super().__init__(f"unmappable DLT-spec config bit {bit!r}: {detail}")


def _require_mappable_keys(config: dict, allowed: frozenset, *, label: str) -> None:
    for key in config:
        if key not in allowed:
            raise DltSpecCompileError(
                bit=f"{label}.{key}",
                detail=f"the key is outside the DLT spec mapping's mappable set {sorted(allowed)}",
            )


def _expectations_from_contract(contract: Contract, seen_names: set[str]) -> list[dict[str, str]]:
    """The contract's ODCS quality rules → DLT expect clauses."""
    hub = contract.hub_contract_json if isinstance(contract.hub_contract_json, dict) else {}
    quality = hub.get("quality")
    if not isinstance(quality, dict):
        return []
    rules = quality.get("rules")
    if rules is None:
        return []
    if not isinstance(rules, list):
        raise DltSpecCompileError(
            bit=f"contract:{contract.id}.quality.rules",
            detail="the rules section is not a list",
        )
    clauses: list[dict[str, str]] = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise DltSpecCompileError(
                bit=f"contract:{contract.id}.quality.rules[{index}]",
                detail="the rule is not an object",
            )
        name = rule.get("name")
        if not isinstance(name, str) or not name.strip():
            raise DltSpecCompileError(
                bit=f"contract:{contract.id}.quality.rules[{index}]",
                detail="the rule has no name — a DLT expectation requires one",
            )
        expression = rule.get("expression")
        if not isinstance(expression, str) or not expression.strip():
            raise DltSpecCompileError(
                bit=f"contract:{contract.id}.quality.rules[{index}].name={name}",
                detail="the rule has no expression — it cannot become an expect clause",
            )
        severity = rule.get("severity")
        if severity is None:
            action = "warn"  # the DLT documented default action
        elif severity not in _SEVERITY_ACTIONS:
            raise DltSpecCompileError(
                bit=f"contract:{contract.id}.quality.rules[{index}].name={name}.severity",
                detail=f"severity {severity!r} has no DLT expect-action mapping",
            )
        else:
            action = _SEVERITY_ACTIONS[severity]
        if name in seen_names:
            raise DltSpecCompileError(
                bit=f"contract:{contract.id}.quality.rules[{index}].name={name}",
                detail="the expectation name collides with an already-mapped rule",
            )
        seen_names.add(name)
        clauses.append({"name": name, "expression": expression, "action": action})
    return clauses


def _build_spec(
    *,
    name: str,
    catalog: str | None,
    target: str | None,
    tables: list[dict[str, str]],
    sources: list[dict[str, str]],
    expectations: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "kind": _SPEC_KIND,
        "schema_version": _SPEC_SCHEMA_VERSION,
        "name": name,
        "catalog": catalog,
        "target": target,
        "continuous": False,  # the schedule stays the movement spine's
        "development": False,
        "channel": "CURRENT",
        "tables": tables,
        "sources": sources,
        "expectations": expectations,
    }


def compile_export_to_dlt_spec(export: ScheduledExport) -> dict[str, Any]:
    """Compile a DATABRICKS_TABLE export into a DLT spec draft."""
    from hub.data_movement.export_preflight import validate_export_contracts

    if export.destination_type != "DATABRICKS_TABLE":
        raise DltSpecCompileError(
            bit=f"destination_type={export.destination_type}",
            detail="only DATABRICKS_TABLE exports map onto a DLT pipeline",
        )
    # The DECRYPTED config — the movement spine's own seam (the raw
    # field is the {"_encrypted": ...} envelope at rest; reading it raw
    # would refuse every persisted config).
    config = export.get_destination_config()
    _require_mappable_keys(config, _EXPORT_MAPPABLE_KEYS, label="destination_config")
    catalog = str(config.get("catalog") or "").strip()
    if not catalog:
        raise DltSpecCompileError(
            bit="destination_config.catalog", detail="the target catalog is required"
        )
    target = str(config.get("schema") or "").strip()
    if not target:
        raise DltSpecCompileError(
            bit="destination_config.schema", detail="the target schema is required"
        )

    # The 6.5 pre-flight, REUSED: every contract-bearing source must
    # carry an ACTIVE + validated ODCS contract — violations refuse the
    # compile with ZERO spec emitted.
    contracts = validate_export_contracts(export)

    scope = export.source_scope or {}
    sources: list[dict[str, str]] = []
    for asset_id in scope.get("asset_ids", []) or []:
        sources.append({"asset_id": str(asset_id)})
    for dataset_id in scope.get("dataset_ids", []) or []:
        sources.append({"dataset_id": str(dataset_id)})
    if scope.get("contract_id"):
        sources.append({"contract_id": str(scope["contract_id"])})

    seen_names: set[str] = set()
    expectations: list[dict[str, str]] = []
    for contract in contracts:
        expectations.extend(_expectations_from_contract(contract, seen_names))

    return _build_spec(
        name=export.name,
        catalog=catalog,
        target=target,
        tables=[],
        sources=sources,
        expectations=expectations,
    )


def _ingestion_contract(ingestion: ScheduledIngestion) -> Contract | None:
    """The ingestion's contract: the explicit FK, else its asset's ACTIVE
    contract (the preflight's resolution order)."""
    from hub.apps.contracts.models import Contract

    if ingestion.contract is not None:
        return ingestion.contract
    if ingestion.asset is not None:
        return (
            Contract.objects.filter(asset=ingestion.asset, status="ACTIVE")
            .order_by("-version")
            .first()
        )
    return None


def _refuse_unvalidated_contract(contract: Contract | None, *, source: str) -> Contract:
    """The ingestion/transformation contract check — the SAME accepted
    set as the 6.5 pre-flight (reused as the shared classification,
    since the pre-flight only walks export scopes)."""
    from hub.data_movement.export_preflight import ExportContractValidationError

    violation: dict[str, Any] | None = None
    if contract is None:
        violation = {"source": source, "reason": "no ACTIVE contract"}
    elif contract.original_spec_type != "ODCS":
        violation = {
            "source": source,
            "contract_id": str(contract.id),
            "reason": f"the ACTIVE contract is {contract.original_spec_type}, not ODCS",
        }
    elif contract.validation_status not in {"VALID", "WARNING_ONLY"}:
        violation = {
            "source": source,
            "contract_id": str(contract.id),
            "reason": (
                f"validation_status={contract.validation_status or 'unvalidated'} "
                "— VALID or WARNING_ONLY required"
            ),
        }
    if violation:
        raise ExportContractValidationError([violation])
    assert contract is not None  # guarded by the violation raise above
    return contract


def compile_ingestion_to_dlt_spec(ingestion: ScheduledIngestion) -> dict[str, Any]:
    """Compile a DATABRICKS_SOURCE ingestion into a DLT spec draft."""
    if ingestion.source_type != "DATABRICKS_SOURCE":
        raise DltSpecCompileError(
            bit=f"source_type={ingestion.source_type}",
            detail="only DATABRICKS_SOURCE ingestions map onto a DLT pipeline",
        )
    # The DECRYPTED config (the same seam as the export path).
    config = ingestion.get_source_config()
    _require_mappable_keys(config, _INGESTION_MAPPABLE_KEYS, label="source_config")
    table = str(config.get("table") or "").strip()
    if not table:
        raise DltSpecCompileError(
            bit="source_config.table",
            detail="the source table is required (the 6.7 branch's own requirement)",
        )
    catalog = str(config.get("catalog") or "").strip()
    if not catalog:
        raise DltSpecCompileError(
            bit="source_config.catalog", detail="the source catalog is required"
        )
    target = str(config.get("schema") or "").strip()
    if not target:
        raise DltSpecCompileError(
            bit="source_config.schema", detail="the source schema is required"
        )

    contract = _refuse_unvalidated_contract(
        _ingestion_contract(ingestion), source=f"ingestion:{ingestion.id}"
    )

    expectations = _expectations_from_contract(contract, set())
    sources: list[dict[str, str]] = []
    if ingestion.asset is not None:
        sources.append({"asset_id": str(ingestion.asset_id)})

    return _build_spec(
        name=ingestion.name,
        catalog=catalog,
        target=target,
        tables=[{"name": table, "kind": "table"}],
        sources=sources,
        expectations=expectations,
    )


def compile_transformation_to_dlt_spec(pipeline: TransformationPipeline) -> dict[str, Any]:
    """Compile a transformation pipeline into a DLT spec draft: the
    output nodes' targets become the pipeline's tables/views; the
    source assets' contracts become the expectations. The
    transformation LOGIC rides the movement spine's executor — it is
    not a spec setting, so it is neither mapped nor dropped."""
    from hub.apps.contracts.models import Contract
    from hub.apps.transformation.models import NodeType, TransformationNode

    nodes = list(TransformationNode.objects.filter(pipeline=pipeline).order_by("order"))
    if not nodes:
        raise DltSpecCompileError(
            bit="transformation_nodes", detail="the pipeline has no nodes to map"
        )

    tables: list[dict[str, str]] = []
    target: str | None = None
    for node in nodes:
        if node.node_type not in NodeType.values:
            raise DltSpecCompileError(
                bit=f"node:{node.id}.node_type={node.node_type}",
                detail=f"unknown node kind (valid: {sorted(NodeType.values)})",
            )
        if node.node_type == NodeType.OUTPUT:
            # The DECRYPTED node config (the transformation model's own
            # get_node_config seam — the raw field is the encrypted
            # envelope at rest).
            config = node.get_node_config()
            table_name = str(config.get("target") or "").strip()
            if not table_name:
                raise DltSpecCompileError(
                    bit=f"node:{node.id}.node_config.target",
                    detail="an output node without a target cannot map onto a DLT table",
                )
            tables.append({"name": table_name, "kind": "table"})
            node_schema = str(config.get("target_schema") or "").strip()
            if node_schema:
                if target is not None and target != node_schema:
                    raise DltSpecCompileError(
                        bit=f"node:{node.id}.node_config.target_schema",
                        detail=(
                            f"the pipeline maps onto TWO target schemas ({target!r} "
                            f"and {node_schema!r}) — one spec cannot represent both"
                        ),
                    )
                target = node_schema
    if not tables:
        raise DltSpecCompileError(
            bit="transformation_nodes", detail="the pipeline has no output node to map"
        )

    metadata = pipeline.metadata if isinstance(pipeline.metadata, dict) else {}
    catalog = metadata.get("catalog")
    catalog = str(catalog).strip() if catalog else None
    sources: list[dict[str, str]] = []
    seen_names: set[str] = set()
    expectations: list[dict[str, str]] = []
    for asset_id in metadata.get("source_assets", []) or []:
        sources.append({"asset_id": str(asset_id)})
        contract = (
            Contract.objects.filter(asset_id=asset_id, status="ACTIVE").order_by("-version").first()
        )
        if contract is not None:
            contract = _refuse_unvalidated_contract(contract, source=f"asset:{asset_id}")
            expectations.extend(_expectations_from_contract(contract, seen_names))

    return _build_spec(
        name=pipeline.name,
        catalog=catalog,
        target=target,
        tables=tables,
        sources=sources,
        expectations=expectations,
    )
