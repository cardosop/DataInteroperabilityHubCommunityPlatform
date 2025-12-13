"""
Typed HubContract models using Pydantic for validation and normalization.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class HubContractOwner(BaseModel):
    """Owner/contact entry."""

    name: Optional[str] = None
    email: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class HubContractInfo(BaseModel):
    """Info section of the HubContract."""

    name: str
    description: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None
    domain: Optional[str] = None
    tenant: Optional[str] = None
    dataProduct: Optional[str] = None
    links: Optional[Any] = None
    authoritativeDefinitions: Optional[Any] = None
    owners: Optional[List[HubContractOwner]] = None
    tags: Optional[List[str]] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("info.name must be provided")
        return value


class HubContractField(BaseModel):
    """Schema field definition."""

    name: str
    data_type: str = Field(default="string", alias="type")
    nullable: bool = True
    description: Optional[str] = None
    semantic_type: Optional[str] = None
    format: Optional[str] = None
    pattern: Optional[str] = None
    enum: Optional[List[Any]] = None
    default: Optional[Any] = None
    min_length: Optional[int] = Field(default=None, alias="minLength")
    max_length: Optional[int] = Field(default=None, alias="maxLength")
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    is_primary_key: Optional[bool] = False
    is_unique: Optional[bool] = None
    is_indexed: Optional[bool] = None
    lineage: Optional[LineageEntry] = None

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


class HubContractSchema(BaseModel):
    """Schema section of the HubContract."""

    fields: List[HubContractField]
    primary_key: Optional[List[str]] = None
    unique_constraints: Optional[List[Any]] = None
    indexes: Optional[List[Any]] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("fields")
    @classmethod
    def validate_fields(cls, value: List[HubContractField]) -> List[HubContractField]:
        if not value:
            raise ValueError("schema.fields must contain at least one field")
        return value


class HubContractModelEntry(BaseModel):
    """Canonical model entry within models[]."""

    name: str
    description: Optional[str] = None
    fields: List[HubContractField]
    primary_key: Optional[List[str]] = None
    unique_constraints: Optional[List[Any]] = None
    indexes: Optional[List[Any]] = None
    logical_type: Optional[str] = None
    physical_type: Optional[str] = None
    physical_name: Optional[str] = None
    data_granularity_description: Optional[str] = None
    tags: Optional[List[str]] = None
    lineage: Optional[LineageSection] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("models[].name must be provided")
        return value

    @field_validator("fields")
    @classmethod
    def validate_model_fields(cls, value: List[HubContractField]) -> List[HubContractField]:
        if not value:
            raise ValueError("models[].fields must contain at least one field")
        return value


class ServiceLevel(BaseModel):
    """Canonical service level entry."""

    id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    property: Optional[str] = None
    metric: Optional[str] = None
    objective: Optional[str] = None
    target: Optional[Any] = None
    unit: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[Any] = None
    window: Optional[str] = None
    schedule: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class QualityRule(BaseModel):
    """Canonical quality rule structure."""

    id: Optional[str] = None
    name: Optional[str] = None
    dimension: Optional[str] = None
    type: Optional[str] = None
    rule: Optional[Any] = None
    unit: Optional[str] = None
    operator: Optional[str] = None
    threshold: Optional[Any] = None
    valid_values: Optional[List[Any]] = None
    sql_query: Optional[str] = None
    target: Optional[str] = None
    engine: Optional[str] = None
    implementation: Optional[str] = None
    method: Optional[str] = None
    severity: Optional[str] = None
    business_impact: Optional[str] = None
    scheduler: Optional[str] = None
    schedule: Optional[str] = None
    tags: Optional[List[str]] = None

    model_config = ConfigDict(extra="allow")


class ContactChannel(BaseModel):
    """Canonical contact channel extracted from support[]."""

    name: Optional[str] = None
    email: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    tool: Optional[str] = None
    scope: Optional[str] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        if value and "@" not in value:
            raise ValueError("contact.email must be a valid email address")
        return value


class ServerEntry(BaseModel):
    """Canonical server entry."""

    type: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    host: Optional[str] = None
    port: Optional[Any] = None
    database: Optional[str] = None
    catalog: Optional[str] = None
    schema: Optional[str] = None
    warehouse: Optional[str] = None
    account: Optional[str] = None
    region: Optional[str] = None
    bucket: Optional[str] = None
    path: Optional[str] = None
    topic: Optional[str] = None
    queue: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class TermsSection(BaseModel):
    """Canonical terms of use."""

    usage: Optional[Any] = None
    limitations: Optional[Any] = None
    billing: Optional[Any] = None
    support: Optional[Any] = None
    sla: Optional[Any] = None
    pricing: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


class RoleEntry(BaseModel):
    """ODCS roles[] entry."""

    roleName: Optional[str] = None
    accessType: Optional[str] = None
    approvers: Optional[List[Any]] = None

    model_config = ConfigDict(extra="allow")


class DefinitionEntry(BaseModel):
    """Canonical definition entry for reusable field definitions."""

    name: str
    description: Optional[str] = None
    type: Optional[str] = None
    nullable: Optional[bool] = None
    format: Optional[str] = None
    pattern: Optional[str] = None
    enum: Optional[List[Any]] = None
    default: Optional[Any] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("definitions[].name must be provided")
        return value


class SupportChannel(BaseModel):
    """ODCS support[] channel entry (separate from contact info)."""

    tool: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    scope: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class TeamEntry(BaseModel):
    """ODCS team[] entry."""

    member: Optional[str] = None
    role: Optional[str] = None
    dateIn: Optional[str] = None
    dateOut: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class PricingEntry(BaseModel):
    """ODCS price object."""

    priceAmount: Optional[Any] = None
    priceCurrency: Optional[str] = None
    priceUnit: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class InputField(BaseModel):
    """Lineage input field reference."""

    namespace: Optional[str] = None
    name: Optional[str] = None
    model_name: Optional[str] = None
    field: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class Transformation(BaseModel):
    """Lineage transformation."""

    logic: Optional[Any] = None
    description: Optional[str] = None
    type: Optional[str] = None
    subtype: Optional[str] = None
    masking: Optional[Any] = None

    model_config = ConfigDict(extra="allow")


class LineageEntry(BaseModel):
    """Canonical lineage entry (used at contract, model, and field levels)."""

    input_fields: Optional[List[InputField]] = Field(default=None, alias="inputFields")
    transformations: Optional[List[Transformation]] = None

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ContractLineageReference(BaseModel):
    """Contract-level lineage reference to another contract."""

    namespace: Optional[str] = None
    name: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ModelLineageReference(BaseModel):
    """Model-level lineage reference to another model."""

    namespace: Optional[str] = None
    name: Optional[str] = None
    model_name: Optional[str] = None
    description: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class LineageSection(BaseModel):
    """Multi-level lineage section for HubContract."""

    contracts: Optional[List[ContractLineageReference]] = None
    models: Optional[List[ModelLineageReference]] = None
    entries: Optional[List[LineageEntry]] = None

    model_config = ConfigDict(extra="allow")


class QualitySection(BaseModel):
    """Quality section."""

    default_profile_key: Optional[str] = None
    rules: Optional[List[QualityRule]] = None
    type: Optional[str] = None
    specification: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class PrivacyComplianceSection(BaseModel):
    """Privacy and compliance section."""

    contains_personal_data: Optional[bool] = None
    personal_data_categories: Optional[List[Any]] = None
    jurisdictions: Optional[List[str]] = None
    legal_bases: Optional[List[str]] = None
    retention_policy: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


class LifecycleSection(BaseModel):
    """Lifecycle section."""

    data_source: Optional[str] = None
    refresh_cadence: Optional[str] = None
    slas: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


class MarketplaceSection(BaseModel):
    """Marketplace section."""

    license_summary: Optional[str] = None
    intended_use: Optional[List[str]] = None
    restricted_use: Optional[List[str]] = None

    model_config = ConfigDict(extra="allow")


class OriginalSpecMetadata(BaseModel):
    """Original spec metadata captured during normalization."""

    type: str
    version: str
    conforms_to: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("type", "version")
    @classmethod
    def validate_required(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("original_spec.type and original_spec.version must be provided")
        return value


class NormalizationMetadata(BaseModel):
    """Normalization metadata container."""

    coverage: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


class HubContractModel(BaseModel):
    """
    Canonical HubContract with strict validation.
    Extra fields are preserved for forward compatibility.
    """

    hub_contract_version: str
    id: str
    info: HubContractInfo
    schema: HubContractSchema
    models: Optional[List[HubContractModelEntry]] = None
    definitions: Optional[List[DefinitionEntry]] = None
    quality: Optional[QualitySection] = None
    servicelevels: Optional[List[ServiceLevel]] = None
    contact: Optional[List[ContactChannel]] = None
    support: Optional[List[SupportChannel]] = None
    servers: Optional[List[ServerEntry]] = None
    terms: Optional[TermsSection] = None
    roles: Optional[List[RoleEntry]] = None
    team: Optional[List[TeamEntry]] = None
    pricing: Optional[PricingEntry] = None
    lineage: Optional[LineageSection] = None
    privacy_compliance: Optional[PrivacyComplianceSection] = None
    lifecycle: Optional[LifecycleSection] = None
    marketplace: Optional[MarketplaceSection] = None
    original_spec: Optional[OriginalSpecMetadata] = None
    normalization: Optional[NormalizationMetadata] = None
    extensions: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")

    @field_validator("hub_contract_version", "id")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        if not value or not str(value).strip():
            raise ValueError("hub_contract_version and id must be provided")
        return value

    @model_validator(mode="after")
    def check_required_sections(self) -> "HubContractModel":
        if not self.info or not self.schema:
            raise ValueError("info and schema sections are required")
        return self


def validate_hub_contract_dict(hub_contract: Dict[str, Any]) -> tuple[Optional[HubContractModel], List[str]]:
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
        errors: List[str] = []
        for error in exc.errors():
            location = " -> ".join(str(item) for item in error.get("loc", []))
            message = error.get("msg", "Invalid value")
            errors.append(f"{location}: {message}" if location else message)
        return None, errors
