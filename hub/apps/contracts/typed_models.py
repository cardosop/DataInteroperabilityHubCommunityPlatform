"""
Typed HubContract models using Pydantic for validation and normalization.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class HubContractOwner(BaseModel):
    """Owner/contact entry."""

    name: str | None = None
    email: str | None = None

    model_config = ConfigDict(extra="allow")


class HubContractInfo(BaseModel):
    """Info section of the HubContract."""

    name: str
    description: str | None = None
    version: str | None = None
    status: str | None = None
    domain: str | None = None
    tenant: str | None = None
    dataProduct: str | None = None
    links: Any | None = None
    authoritativeDefinitions: Any | None = None
    owners: list[HubContractOwner] | None = None
    tags: list[str] | None = None

    model_config = ConfigDict(extra="allow")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("info.name must be provided")
        return value


class HubContractRelationship(BaseModel):
    """Relationship between schema objects/fields (ODCS v3.1.0)."""

    id: str | None = None
    name: str | None = Field(default=None, max_length=255)
    type: str | None = Field(default=None, max_length=100)
    source: list[str] = Field(default_factory=list)
    target_contract: str | None = None
    target_model: str | None = None
    target_properties: list[str] = Field(default_factory=list)
    description: str | None = None
    custom_properties: list[dict[str, Any]] | None = None

    model_config = ConfigDict(extra="allow")


class HubContractField(BaseModel):
    """Schema field definition.

    Phase 227 Wave 1 (227.L2.2) — self-referential ``fields`` and ``items``
    enable nested ``object``/``array`` types to be represented in the
    canonical HubContract shape (``customer.address.street``,
    ``orders[].items[].sku``). The recursive walker in
    :mod:`hub.apps.contracts.normalization_engine` populates these.

    Validators enforce the structural floor invariant Wave 1 ships:

    * ``data_type == "object"`` MUST have a non-empty ``fields[]`` list —
      structureless object shapes are exactly the failure mode Wave 0
      identified in production.
    * ``data_type == "array"`` MUST have an ``items`` field — an array
      with no element schema is meaningless to consumers.
    """

    name: str
    data_type: str = Field(default="string", alias="type")
    element_id: str | None = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9_\-\.]{1,128}$",
    )
    nullable: bool = True
    description: str | None = None
    semantic_type: str | None = None
    format: str | None = None
    pattern: str | None = None
    enum: list[Any] | None = None
    default: Any | None = None
    min_length: int | None = Field(default=None, alias="minLength")
    max_length: int | None = Field(default=None, alias="maxLength")
    minimum: float | None = None
    maximum: float | None = None
    exclusiveMinimum: Any | None = None
    exclusiveMaximum: Any | None = None
    logicalType: str | None = None
    logicalTypeOptions: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    is_primary_key: bool | None = False
    is_unique: bool | None = None
    is_indexed: bool | None = None
    lineage: LineageEntry | None = None
    relationships: list[HubContractRelationship] | None = None
    # Phase 227 Wave 1 (227.L2.2) — recursive nesting.
    fields: list[HubContractField] | None = None
    items: HubContractField | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("schema.fields[].name must be provided")
        return value

    @field_validator("data_type")
    @classmethod
    def validate_data_type(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("schema.fields[].data_type must be provided")
        return value

    @model_validator(mode="after")
    def validate_nested_shape(self) -> HubContractField:
        """Phase 227 Wave 1 structural floor invariants.

        We deliberately allow ``data_type == "object"`` with no
        ``fields[]`` to be REJECTED (raise) but allow ``items``-less
        arrays through with a nullable hint — some legacy contracts
        emit ``type: array`` without an explicit element schema and we
        treat those as warnings during normalisation rather than
        hard-fail (Wave 0 would have caught the same cases).
        """
        if self.data_type == "object" and not self.fields:
            raise ValueError(
                f"schema.fields[].name={self.name!r} has data_type='object' "
                f"but no fields[] — object types must declare nested fields "
                f"(see Phase 227 structural floor invariant)"
            )
        return self

    # Forward-ref resolution for the self-referential ``fields``/``items``
    # annotations is performed at the END of the module, AFTER
    # ``LineageEntry`` and the other forward-referenced classes are
    # defined. See ``HubContractField.model_rebuild(...)`` near EOF.


class HubContractSchema(BaseModel):
    """Schema section of the HubContract."""

    fields: list[HubContractField]
    primary_key: list[str] | None = None
    unique_constraints: list[Any] | None = None
    indexes: list[Any] | None = None
    relationships: list[HubContractRelationship] | None = None

    model_config = ConfigDict(extra="allow")

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: list[HubContractField]) -> list[HubContractField]:
        if not value:
            raise ValueError("schema.fields must contain at least one field")
        return value


class HubContractModelEntry(BaseModel):
    """Canonical model entry within models[]."""

    name: str
    element_id: str | None = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9_\-\.]{1,128}$",
    )
    description: str | None = None
    fields: list[HubContractField]
    primary_key: list[str] | None = None
    unique_constraints: list[Any] | None = None
    indexes: list[Any] | None = None
    logical_type: str | None = None
    physical_type: str | None = None
    physical_name: str | None = None
    data_granularity_description: str | None = None
    tags: list[str] | None = None
    lineage: LineageSection | None = None
    relationships: list[HubContractRelationship] | None = None

    model_config = ConfigDict(extra="allow")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("models[].name must be provided")
        return value

    @field_validator("fields")
    @classmethod
    def validate_model_fields(cls, value: list[HubContractField]) -> list[HubContractField]:
        if not value:
            raise ValueError("models[].fields must contain at least one field")
        return value


class ServiceLevel(BaseModel):
    """Canonical service level entry."""

    id: str | None = None
    name: str | None = None
    description: str | None = None
    property: str | None = None
    metric: str | None = None
    objective: str | None = None
    target: Any | None = None
    unit: str | None = None
    operator: str | None = None
    threshold: Any | None = None
    window: str | None = None
    schedule: str | None = None
    tags: list[str] | None = None
    priority: str | None = None

    model_config = ConfigDict(extra="allow")


class QualityRule(BaseModel):
    """Canonical quality rule structure."""

    id: str | None = None
    name: str | None = None
    dimension: str | None = None
    type: str | None = None
    rule: Any | None = None
    unit: str | None = None
    operator: str | None = None
    threshold: Any | None = None
    valid_values: list[Any] | None = None
    sql_query: str | None = None
    target: str | None = None
    engine: str | None = None
    implementation: str | None = None
    method: str | None = None
    severity: str | None = None
    business_impact: str | None = None
    scheduler: str | None = None
    schedule: str | None = None
    tags: list[str] | None = None

    model_config = ConfigDict(extra="allow")


class ContactChannel(BaseModel):
    """Canonical contact channel extracted from support[]."""

    name: str | None = None
    email: str | None = None
    url: str | None = None
    description: str | None = None
    tool: str | None = None
    scope: str | None = None

    model_config = ConfigDict(extra="allow")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value and "@" not in value:
            raise ValueError("contact.email must be a valid email address")
        return value


class ServerEntry(BaseModel):
    """Canonical server entry."""

    type: str | None = None
    url: str | None = None
    description: str | None = None
    variables: dict[str, Any] | None = None
    host: str | None = None
    port: Any | None = None
    database: str | None = None
    catalog: str | None = None
    schema_: str | None = Field(default=None, alias="schema")
    warehouse: str | None = None
    account: str | None = None
    region: str | None = None
    bucket: str | None = None
    path: str | None = None
    topic: str | None = None
    queue: str | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class TermsSection(BaseModel):
    """Canonical terms of use."""

    usage: Any | None = None
    limitations: Any | None = None
    billing: Any | None = None
    support: Any | None = None
    sla: Any | None = None
    pricing: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")


class RoleEntry(BaseModel):
    """ODCS roles[] entry."""

    roleName: str | None = None
    accessType: str | None = None
    approvers: list[Any] | None = None

    model_config = ConfigDict(extra="allow")


class DefinitionEntry(BaseModel):
    """Canonical definition entry for reusable field definitions."""

    name: str
    description: str | None = None
    type: str | None = None
    nullable: bool | None = None
    format: str | None = None
    pattern: str | None = None
    enum: list[Any] | None = None
    default: Any | None = None
    min_length: int | None = None
    max_length: int | None = None
    minimum: float | None = None
    maximum: float | None = None
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("definitions[].name must be provided")
        return value


class SupportChannel(BaseModel):
    """ODCS support[] channel entry (separate from contact info)."""

    tool: str | None = None
    url: str | None = None
    description: str | None = None
    scope: str | None = None

    model_config = ConfigDict(extra="allow")


class TeamEntry(BaseModel):
    """ODCS team[] entry."""

    member: str | None = None
    role: str | None = None
    dateIn: str | None = None
    dateOut: str | None = None

    model_config = ConfigDict(extra="allow")


class PricingEntry(BaseModel):
    """ODCS price object."""

    priceAmount: Any | None = None
    priceCurrency: str | None = None
    priceUnit: str | None = None

    model_config = ConfigDict(extra="allow")


class InputField(BaseModel):
    """Lineage input field reference."""

    namespace: str | None = None
    name: str | None = None
    model_name: str | None = None
    field: str | None = None

    model_config = ConfigDict(extra="allow")


class Transformation(BaseModel):
    """Lineage transformation."""

    logic: Any | None = None
    description: str | None = None
    type: str | None = None
    subtype: str | None = None
    masking: Any | None = None

    model_config = ConfigDict(extra="allow")


class LineageEntry(BaseModel):
    """Canonical lineage entry (used at contract, model, and field levels)."""

    input_fields: list[InputField] | None = Field(default=None, alias="inputFields")
    transformations: list[Transformation] | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ContractLineageReference(BaseModel):
    """Contract-level lineage reference to another contract."""

    namespace: str | None = None
    name: str | None = None
    version: str | None = None
    description: str | None = None

    model_config = ConfigDict(extra="allow")


class ModelLineageReference(BaseModel):
    """Model-level lineage reference to another model."""

    namespace: str | None = None
    name: str | None = None
    model_name: str | None = None
    description: str | None = None

    model_config = ConfigDict(extra="allow")


class LineageSection(BaseModel):
    """Multi-level lineage section for HubContract."""

    contracts: list[ContractLineageReference] | None = None
    models: list[ModelLineageReference] | None = None
    entries: list[LineageEntry] | None = None

    model_config = ConfigDict(extra="allow")


class QualitySection(BaseModel):
    """Quality section."""

    default_profile_key: str | None = None
    rules: list[QualityRule] | None = None
    type: str | None = None
    specification: str | None = None

    model_config = ConfigDict(extra="allow")


class PrivacyComplianceSection(BaseModel):
    """Privacy and compliance section."""

    contains_personal_data: bool | None = None
    personal_data_categories: list[Any] | None = None
    jurisdictions: list[str] | None = None
    legal_bases: list[str] | None = None
    retention_policy: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")


class LifecycleSection(BaseModel):
    """Lifecycle section."""

    data_source: str | None = None
    refresh_cadence: str | None = None
    slas: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")


class MarketplaceSection(BaseModel):
    """Marketplace section."""

    license_summary: str | None = None
    intended_use: list[str] | None = None
    restricted_use: list[str] | None = None

    model_config = ConfigDict(extra="allow")


class OriginalSpecMetadata(BaseModel):
    """Original spec metadata captured during normalization."""

    type: str
    version: str
    conforms_to: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")

    @field_validator("type", "version")
    @classmethod
    def validate_required(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("original_spec.type and original_spec.version must be provided")
        return value


class NormalizationMetadata(BaseModel):
    """Normalization metadata container."""

    coverage: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")


class HubContractModel(BaseModel):
    """
    Canonical HubContract with strict validation.
    Extra fields are preserved for forward compatibility.
    """

    hub_contract_version: str
    id: str
    info: HubContractInfo
    schema_: HubContractSchema = Field(alias="schema")
    models: list[HubContractModelEntry] | None = None
    definitions: list[DefinitionEntry] | None = None
    quality: QualitySection | None = None
    servicelevels: list[ServiceLevel] | None = None
    contact: list[ContactChannel] | None = None
    support: list[SupportChannel] | None = None
    servers: list[ServerEntry] | None = None
    terms: TermsSection | None = None
    roles: list[RoleEntry] | None = None
    team: list[TeamEntry] | None = None
    pricing: PricingEntry | None = None
    lineage: LineageSection | None = None
    privacy_compliance: PrivacyComplianceSection | None = None
    lifecycle: LifecycleSection | None = None
    marketplace: MarketplaceSection | None = None
    original_spec: OriginalSpecMetadata | None = None
    normalization: NormalizationMetadata | None = None
    extensions: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    @field_validator("hub_contract_version", "id")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("hub_contract_version and id must be provided")
        return value

    @model_validator(mode="after")
    def check_required_sections(self) -> HubContractModel:
        if not self.info or not self.schema_:
            raise ValueError("info and schema sections are required")
        return self


def validate_hub_contract_dict(
    hub_contract: dict[str, Any],
) -> tuple[HubContractModel | None, list[str]]:
    """
    Validate HubContract dictionary using Pydantic models.

    Args:
        hub_contract: HubContract dictionary

    Returns:
        Tuple of (validated_model, error_messages)
    """
    try:
        model = HubContractModel.model_validate(hub_contract)
        return model, []
    except ValidationError as exc:
        errors: list[str] = []
        for error in exc.errors():
            location = " -> ".join(str(item) for item in error.get("loc", []))
            message = error.get("msg", "Invalid value")
            errors.append(f"{location}: {message}" if location else message)
        return None, errors


# Phase 227 Wave 1 (227.L2.2) — resolve forward refs.
#
# `HubContractField` references itself via ``fields``/``items`` AND
# references ``LineageEntry`` / ``HubContractRelationship`` (defined
# later in the module). Pydantic v2 needs an explicit
# ``model_rebuild`` once all forward-referenced names are in scope; this
# is the canonical pattern for self-referential models that also
# reference siblings declared further down the file. Calling rebuild
# inline at the class body would fail because ``LineageEntry`` is not
# yet defined.
HubContractField.model_rebuild()
