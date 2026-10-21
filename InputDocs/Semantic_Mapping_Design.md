# Semantic Mapping Design

This document specifies how the Interoperable Data Hub maps its internal domain model
(**HubContract, Asset, Dataset, DQRun, ComplianceRun, MarketplaceListing, etc.**) into
RDF and JSON-LD, and how semantic mapping failures are handled.

It is a companion to:

- `SystemRequirements.md` (Semantic Layer & Ontologies)
- `Domain_Model.md`
- `API_Spec_v1.md`
- `Security_Design_and_Threat_Model.md`

### Namespace & URI Conventions

The `hub:` namespace and resource URIs are standardized as follows:

- **Ontology base IRI (terms)**
  - Prefix: `hub:`
  - Base IRI:  
    `https://{hub-domain}/ontology#`
  - Used for:
    - classes (e.g. `hub:Asset`, `hub:Contract`, `hub:Dataset`),
    - properties (e.g. `hub:hasContract`, `hub:hasDataset`, `hub:fieldSemanticType`).

- **Resource base URI (instances)**
  - All concrete instances use dereferenceable URIs under `/id`:
    - Assets: `https://{hub-domain}/id/asset/{asset_uuid}`
    - Contracts: `https://{hub-domain}/id/contract/{contract_uuid}`
    - Datasets: `https://{hub-domain}/id/dataset/{dataset_uuid}`
    - Fields: `https://{hub-domain}/id/field/{asset_uuid}/{field_name}`
  - These URIs are used as RDF subjects/objects and SHOULD resolve (via the
    platform API) to JSON/JSON-LD representations of the resource.

- **JSON-LD context**
  - A shared JSON-LD context is exposed at:  
    `https://{hub-domain}/context.jsonld`
  - All JSON-LD responses that use `hub:` terms MUST either:
    - reference this shared context, or
    - inline an equivalent context consistent with these IRIs.

> `{hub-domain}` is the public base domain for the deployment (e.g.
> `hub.example.com`). All environments (dev/staging/prod) MUST follow the same
> pattern, differing only in hostnames.


---

## 1. Purpose & Scope

The semantic mapping layer has three main goals:

1. **Interoperability**  
   Represent assets, contracts, and related artifacts in RDF using an ontology that
   extends established vocabularies like **DCAT** and **Dublin Core (DCT)**.

2. **Discoverability**  
   Enable semantic search, linkage, and reasoning on top of contracts and data assets,
   both inside the hub and from external tools (triple stores, knowledge graphs, catalogs).

3. **Decoupling**  
   Keep a clear separation between:
   - The internal **HubContract** JSON / relational model.
   - The public / semantic representation (RDF/JSON-LD) built on top.

This document focuses on:

- The **ontology model** (`hub:` namespace).
- **Mapping rules** from core entities → RDF.
- The **mapping process & failure handling** (`semantic_status = OK | DEGRADED`).
- **Privacy constraints** for semantic data.

---

## 2. Ontology Overview

The hub uses a lightweight ontology that **extends DCAT** and related vocabularies.

### 2.1 Namespaces

We use the following prefixes:

**Core RDF Namespaces:**
- `rdf:`  `http://www.w3.org/1999/02/22-rdf-syntax-ns#`
- `rdfs:` `http://www.w3.org/2000/01/rdf-schema#`
- `xsd:`  `http://www.w3.org/2001/XMLSchema#`
- `owl:`  `http://www.w3.org/2002/07/owl#`

**Standard Catalog & Metadata Vocabularies:**
- `dct:`  `http://purl.org/dc/terms/`              (Dublin Core Terms)
- `dcat:` `http://www.w3.org/ns/dcat#`             (Data Catalog Vocabulary)
- `foaf:` `http://xmlns.com/foaf/0.1/`            (Friend of a Friend - for owners/agents)

**Data Quality & Compliance Vocabularies:**
- `dqv:`  `https://www.w3.org/ns/dqv#`            (Data Quality Vocabulary)
- `dpv:`  `https://www.w3.org/ns/dpv#`            (Data Privacy Vocabulary)

**Provenance & Lifecycle:**
- `prov:` `http://www.w3.org/ns/prov#`            (PROV-O - Provenance Ontology)

**Rights & Licensing:**
- `odrl:` `https://www.w3.org/ns/odrl/2/`         (Open Digital Rights Language)

**Schema Validation:**
- `shacl:` `http://www.w3.org/ns/shacl#`          (Shapes Constraint Language)

**Structured Data:**
- `schema:` `https://schema.org/`                 (Schema.org vocabulary)

**Platform-Specific:**
- `odcs:` `https://bitol.io/odcs#`                (ODCS-related terms; URI TBD)
- `hub:`  `https://hub.example.com/ontology#`     (platform-specific ontology)

> `hub:` is the main custom ontology namespace for the platform. Standard vocabularies (DQV, DPV, PROV-O, ODRL, SHACL, Schema.org) are used where applicable to maximize interoperability and reuse of established patterns.

### 2.2 Core Classes

The ontology defines the following core classes:

- `hub:DataAsset`
  - Represents a logical data product / asset (maps from **Asset**).
  - `rdfs:subClassOf dcat:Dataset`.

- `hub:DataContract`
  - Represents a data contract as a semantic object (maps from **Contract** / HubContract).
  - Linked to `hub:DataAsset` via `hub:hasContract`.

- `hub:DatasetVersion`
  - Represents a concrete dataset version (maps from **Dataset**).
  - Typically modeled as `dcat:Distribution` linked to `hub:DataAsset`.

- `hub:Field`
  - Represents a schema field / column (maps from HubContract schema fields and Dataset schema).
  - Linked to assets or datasets via `hub:hasField`.

- `hub:DataQualityRun`
  - Represents a single DQ run (maps from **DQRun**).

- `hub:ComplianceRun`
  - Represents a single compliance run (maps from **ComplianceRun**).

- `hub:MarketplaceListing`
  - Represents a marketplace listing for an asset (maps from **Marketplace Listing**).

**Extended Classes (for comprehensive contract representation):**

- `hub:QualityRule`
  - Represents an individual data quality rule (maps from HubContract `quality.rules[]`).
  - Linked to `hub:DataContract` via `hub:hasQualityRule`.
  - Uses DQV vocabulary for quality dimensions.

- `hub:CompliancePolicy`
  - Represents compliance and privacy policy configuration (maps from HubContract `privacy_compliance`).
  - Linked to `hub:DataContract` via `hub:hasCompliancePolicy`.
  - Uses DPV vocabulary for jurisdictions, legal bases, and personal data categories.

- `hub:LifecyclePolicy`
  - Represents data lifecycle and operational policies (maps from HubContract `lifecycle`).
  - Linked to `hub:DataContract` via `hub:hasLifecyclePolicy`.
  - Uses PROV-O for data source provenance.

- `hub:MarketplacePolicy`
  - Represents marketplace licensing and usage policies (maps from HubContract `marketplace`).
  - Linked to `hub:DataContract` via `hub:hasMarketplacePolicy`.
  - Uses ODRL for permissions and prohibitions.

- `hub:Owner`
  - Represents contract owners (maps from HubContract `info.owners[]`).
  - Uses FOAF vocabulary (`foaf:Agent`).
  - Linked to `hub:DataContract` via `hub:hasOwner`.

- `hub:Tag`
  - Represents contract tags (maps from HubContract `info.tags[]`).
  - Also exposed via `dcat:keyword` for DCAT compatibility.
  - Linked to `hub:DataContract` via `hub:hasTag`.

(Additional classes like `hub:AuditEvent` may be introduced later if audit semanticization is needed.)

### 2.3 Core Properties

The ontology introduces several `hub:` properties. Key ones:

**Asset-level**

- `hub:hasContract`  
  - domain: `hub:DataAsset`  
  - range: `hub:DataContract`

- `hub:hasDatasetVersion`  
  - domain: `hub:DataAsset`  
  - range: `hub:DatasetVersion`

- `hub:hasField`  
  - domain: `hub:DataAsset` or `hub:DatasetVersion`  
  - range: `hub:Field`

- `hub:hasDQRun`  
  - domain: `hub:DataAsset`  
  - range: `hub:DataQualityRun`

- `hub:hasComplianceRun`  
  - domain: `hub:DataAsset`  
  - range: `hub:ComplianceRun`

- `hub:hasListing`  
  - domain: `hub:DataAsset`  
  - range: `hub:MarketplaceListing`

**Contract properties**

- `hub:contractSpecType`       (literal; e.g. `"ODCS"`, `"DATACONTRACT_COM"`)
- `hub:contractSpecVersion`    (literal; e.g. `"3.0.2"`)
- `hub:hubContractVersion`     (literal integer; normalized contract version)
- `hub:originalFormat`         (literal; `"JSON"`, `"YAML"`)

**Field properties**

- `hub:fieldName`              (literal)
- `hub:fieldDataType`          (literal; logical data type)
- `hub:fieldNullable`          (literal boolean)
- `hub:fieldDescription`       (alias to `dct:description` where appropriate)
- `hub:fieldPIICategory`       (literal; derived from compliance classifications, e.g. `"PII_EMAIL"`)
- `hub:fieldSemanticType`      (literal; semantic type identifier, may link to Schema.org types)
- `hub:fieldFormat`            (literal; format specification, e.g. `"email"`, `"uri"`, `"date-time"`)
- `hub:fieldPattern`           (literal; regex pattern for validation, also uses `shacl:pattern`)
- `hub:fieldEnum`              (literal; repeated for each enum value)
- `hub:fieldMinLength`         (integer; also uses `shacl:minLength`)
- `hub:fieldMaxLength`         (integer; also uses `shacl:maxLength`)
- `hub:fieldMinimum`           (decimal; also uses `shacl:minInclusive`)
- `hub:fieldMaximum`           (decimal; also uses `shacl:maxInclusive`)
- `hub:fieldDefault`           (literal; default value)
- `hub:isPrimaryKey`           (boolean; indicates field is part of primary key)
- `hub:isUnique`               (boolean; indicates field has unique constraint)
- `hub:isIndexed`              (boolean; indicates field is indexed)

**DQ & Compliance properties**

- `hub:overallDQStatus`        (`"PASS"`, `"WARN"`, `"FAIL"`, `"UNKNOWN"`)
- `hub:qualityScore`           (numeric)
- `hub:overallComplianceStatus` (`"PASS"`, `"WARN"`, `"FAIL"`, `"UNKNOWN"`)
- `hub:riskLevel`              (`"LOW"`, `"MEDIUM"`, `"HIGH"`)
- `hub:allowedToStore`         (boolean)
- `hub:applicableRegime`       (literal; `"GDPR"`, `"LGPD"`, `"CCPA"`, etc.)
- `hub:semanticStatus`         (`"OK"`, `"DEGRADED"`) – on assets/contracts to signal mapping health.

**Marketplace properties**

- `hub:listingStatus`          (`"DRAFT"`, `"PUBLISHED"`, `"SUSPENDED"`)
- `hub:priceModel`             (`"FREE"`, `"ONE_TIME"`, `"SUBSCRIPTION"`, `"CONTACT_SALES"`)
- `hub:priceAmount`            (numeric)
- `hub:currency`               (e.g. `"USD"`)

**Contract metadata properties**

- `hub:hasOwner`               (contract → owner; uses `foaf:Agent`)
- `hub:hasTag`                 (contract → tag; also uses `dcat:keyword`)
- `hub:ownerName`              (literal; owner name)
- `hub:ownerEmail`             (literal; owner email, uses `foaf:mbox`)

**Quality rule properties**

- `hub:hasQualityRule`         (contract → quality rule)
- `hub:ruleId`                 (literal; unique rule identifier)
- `hub:ruleDimension`          (literal; links to DQV dimensions: `completeness`, `accuracy`, `consistency`, `timeliness`, `validity`, `uniqueness`)
- `hub:ruleExpression`         (literal; rule expression/query)
- `hub:ruleSeverity`           (literal; `ERROR`, `WARNING`, `INFO`)
- `hub:defaultQualityProfile`  (literal; default DQ profile key)

**Compliance policy properties**

- `hub:hasCompliancePolicy`    (contract → compliance policy)
- `hub:containsPersonalData`  (boolean; indicates if contract contains personal data)
- `hub:hasPersonalDataCategory` (literal; repeated, links to DPV categories)
- `hub:hasJurisdiction`        (literal; repeated, links to DPV jurisdictions: `GDPR`, `LGPD`, `CCPA`, `HIPAA`, `SOX`)
- `hub:hasLegalBasis`          (literal; repeated, links to DPV legal bases: `CONSENT`, `CONTRACT`, `LEGAL_OBLIGATION`, `VITAL_INTERESTS`, `PUBLIC_TASK`, `LEGITIMATE_INTERESTS`)
- `hub:retentionPeriod`        (literal; ISO 8601 duration, e.g. `"P5Y"`)
- `hub:retentionNotes`         (literal; retention policy notes)

**Lifecycle policy properties**

- `hub:hasLifecyclePolicy`     (contract → lifecycle policy)
- `hub:dataSource`             (URI or literal; data source identifier, uses PROV-O `prov:wasDerivedFrom`)
- `hub:refreshCadence`          (literal; refresh frequency, e.g. `"DAILY"`, `"HOURLY"`, `"WEEKLY"`)
- `hub:availabilitySLA`       (literal; availability percentage, e.g. `"99.0"`)
- `hub:latencySLA`             (integer; P95 latency in milliseconds)

**Marketplace policy properties**

- `hub:hasMarketplacePolicy`   (contract → marketplace policy)
- `hub:licenseSummary`         (literal; license description)
- `hub:intendedUse`            (literal; repeated, links to ODRL actions: `analytics`, `machine_learning`, etc.)
- `hub:restrictedUse`          (literal; repeated, links to ODRL prohibitions: `credit_scoring`, `individual-level_marketing`, etc.)

The full ontology MUST be documented separately (e.g. `Ontology_Spec_v0.1.md`) with RDFS/OWL definitions.

### 2.4 Standard Vocabulary Integration

The hub ontology **maximizes reuse** of established vocabularies to ensure interoperability and alignment with industry standards:

**Data Quality Vocabulary (DQV)**
- Quality rules use DQV dimensions: `dqv:completeness`, `dqv:accuracy`, `dqv:consistency`, `dqv:timeliness`, `dqv:validity`, `dqv:uniqueness`
- Quality measurements use `dqv:QualityMeasurement` and `dqv:isMeasurementOf`
- Example: `hub:QualityRule` links to DQV via `dqv:isMeasurementOf dqv:completeness`

**Data Privacy Vocabulary (DPV)**
- Personal data categories use DPV: `dpv:EmailAddress`, `dpv:PhoneNumber`, `dpv:FinancialCard`, etc.
- Jurisdictions use DPV: `dpv:EU-GDPR`, `dpv:BR-LGPD`, `dpv:US-CCPA`, etc.
- Legal bases use DPV: `dpv:Consent`, `dpv:Contract`, `dpv:LegalObligation`, etc.
- Example: `hub:CompliancePolicy` links to DPV via `dpv:hasPersonalDataCategory dpv:EmailAddress`

**PROV-O (Provenance Ontology)**
- Data source relationships use `prov:wasDerivedFrom`
- Lifecycle events use `prov:wasGeneratedAtTime`, `prov:wasAttributedTo`
- Example: `hub:DataAsset prov:wasDerivedFrom <data-source-uri>`

**Open Digital Rights Language (ODRL)**
- Marketplace permissions use `odrl:Permission` with `odrl:action`
- Marketplace prohibitions use `odrl:Prohibition` with `odrl:action`
- Example: `hub:MarketplacePolicy odrl:permission [ odrl:action odrl:use ]`

**Shapes Constraint Language (SHACL)**
- Field validation rules use SHACL: `shacl:pattern`, `shacl:minLength`, `shacl:maxLength`, `shacl:minInclusive`, `shacl:maxInclusive`
- Example: `hub:Field shacl:pattern "^[A-Z0-9]+$"`

**Schema.org**
- Field semantic types may link to Schema.org types: `schema:EmailAddress`, `schema:PostalAddress`, `schema:PhoneNumber`, etc.
- Example: `hub:Field rdf:type schema:EmailAddress` when `semantic_type = "EMAIL"`

**FOAF (Friend of a Friend)**
- Contract owners use `foaf:Agent` with `foaf:name` and `foaf:mbox`
- Example: `hub:Owner rdf:type foaf:Agent ; foaf:name "Data Team" ; foaf:mbox "mailto:data@example.com"`

**DCAT (Data Catalog Vocabulary)**
- Assets extend `dcat:Dataset`
- Datasets extend `dcat:Distribution`
- Tags use `dcat:keyword`
- Example: `hub:DataAsset rdfs:subClassOf dcat:Dataset`

This vocabulary reuse ensures:
- **Interoperability**: Other systems can understand hub data using standard vocabularies
- **Discoverability**: Hub data appears in standard catalog searches and knowledge graphs
- **Compliance**: Alignment with data governance and privacy standards (GDPR, etc.)
- **Future-proofing**: Easier integration with external tools and platforms

### 2.5 JSON-LD Context

The platform MUST provide a JSON-LD context, e.g.:

- `https://hub.example.com/context.jsonld`

which maps compact JSON keys (e.g. `"title"`, `"description"`, `"theme"`, `"hasContract"`) to the corresponding RDF properties (`dct:title`, `dct:description`, `dcat:theme`, `hub:hasContract`, etc.).

The context MUST include all standard vocabulary prefixes:
- `dqv:` (Data Quality Vocabulary)
- `dpv:` (Data Privacy Vocabulary)
- `prov:` (PROV-O)
- `odrl:` (ODRL)
- `shacl:` (SHACL)
- `schema:` (Schema.org)
- `foaf:` (FOAF)
- `dcat:` (DCAT)
- `dct:` (Dublin Core Terms)

All `/id/...` endpoints return JSON-LD with this context attached.

### 2.6 Normalization Requirements

**Complete HubContract Normalization**

The normalization process MUST extract and preserve **all** sections from source contracts (ODCS, DataContract.com) into the canonical HubContract format:

**Required Normalization Coverage:**

1. **Info Section** (complete):
   - `info.name` (required)
   - `info.description` (optional)
   - `info.version` (optional)
   - `info.owners[]` (optional) - Array of owner objects with `name` and `email`
   - `info.tags[]` (optional) - Array of tag strings

2. **Schema Section** (complete):
   - `schema.fields[]` (required) - Array of field definitions with **all** properties:
     - `name`, `data_type`, `nullable` (required)
     - `description`, `semantic_type`, `format`, `pattern`, `enum`, `default` (optional)
     - `min_length`, `max_length`, `minimum`, `maximum` (optional)
     - `metadata` (optional) - Additional field-level metadata
   - `schema.primary_key[]` (optional) - Array of field names
   - `schema.unique_constraints[]` (optional) - Array of constraint arrays
   - `schema.indexes[]` (optional) - Array of index definitions

3. **Quality Section** (complete):
   - `quality.default_profile_key` (optional) - Default DQ profile identifier
   - `quality.rules[]` (optional) - Array of quality rules with:
     - `rule_id`, `dimension`, `expression`, `severity` (required)

4. **Privacy/Compliance Section** (complete):
   - `privacy_compliance.contains_personal_data` (optional) - Boolean
   - `privacy_compliance.personal_data_categories[]` (optional) - Array of PII category strings
   - `privacy_compliance.jurisdictions[]` (optional) - Array of jurisdiction strings
   - `privacy_compliance.legal_bases[]` (optional) - Array of legal basis strings
   - `privacy_compliance.retention_policy` (optional) - Object with:
     - `period` (ISO 8601 duration)
     - `notes` (string)

5. **Lifecycle Section** (complete):
   - `lifecycle.data_source` (optional) - Data source identifier
   - `lifecycle.refresh_cadence` (optional) - Refresh frequency string
   - `lifecycle.slas` (optional) - Object with:
     - `availability` (string, percentage)
     - `latency_ms_p95` (integer, milliseconds)

6. **Marketplace Section** (complete):
   - `marketplace.license_summary` (optional) - License description
   - `marketplace.intended_use[]` (optional) - Array of use case strings
   - `marketplace.restricted_use[]` (optional) - Array of prohibited use case strings

7. **Extensions Section**:
   - `extensions.odcs` (optional) - Unmappable ODCS fields
   - `extensions.datacontract_com` (optional) - Unmappable DataContract.com fields

**Normalization Status:**

- `NORMALIZED_OK`: All mappable sections successfully extracted
- `NORMALIZED_WITH_WARNINGS`: Some sections extracted, unmappable fields preserved in `extensions`
- `NORMALIZATION_FAILED`: Critical sections missing or invalid, cannot produce valid HubContract

**Information Preservation:**

- **Never lose information**: All fields from source contracts MUST be either:
  - Mapped to HubContract canonical structure, OR
  - Preserved in `extensions.{source_spec}` section
- **No data loss**: Original contract file (`original_raw`) is always preserved verbatim

### 2.7 Ontology Versioning

The `hub:` ontology is versioned independently from the application code and the HubContract schema.

- The current canonical namespace is:

  - `hub:` `https://hub.example.com/ont#`

- Backwards-incompatible ontology changes MUST introduce a new version IRI, e.g.:

  - `https://hub.example.com/ont/v2#`

  linked from the unversioned namespace via standard mechanisms such as `owl:versionIRI` / `owl:versionInfo`.

- JSON-LD contexts exposed by the platform are versioned and backwards compatible where possible:

  - `https://hub.example.com/context.jsonld` – current stable context.
  - Future breaking versions MUST be published under a new URL, e.g. `https://hub.example.com/context-v2.jsonld`.

- RDF emitted by the hub SHOULD include a mapping / ontology version signal that downstream systems can use for compatibility checks. For example:

```turtle
<asset-uri> a hub:DataAsset ;
  hub:hubContractVersion 1 ;
  hub:mappingVersion     "2025-01-15" .


---

## 3. URI Design

### 3.1 Resource URIs

Each primary entity has a stable, dereferenceable URI:

- Asset:  
  `https://hub.example.com/id/asset/{asset_id}` → `hub:DataAsset`

- Contract:  
  `https://hub.example.com/id/contract/{contract_id}` → `hub:DataContract`

- DatasetVersion:  
  `https://hub.example.com/id/dataset/{dataset_id}` → `hub:DatasetVersion`

- Field:  
  `https://hub.example.com/id/field/{asset_id}/{field_name}`  
  or  
  `https://hub.example.com/id/field/{dataset_id}/{field_name}`

- DQRun:  
  `https://hub.example.com/id/dqrun/{dqrun_id}` → `hub:DataQualityRun`

- ComplianceRun:  
  `https://hub.example.com/id/compliancerun/{run_id}` → `hub:ComplianceRun`

- MarketplaceListing:  
  `https://hub.example.com/id/listing/{listing_id}` → `hub:MarketplaceListing`

### 3.2 URI Requirements

- URIs MUST be:
  - Stable over time for a given entity.
  - Dereferenceable via HTTP GET to a JSON-LD representation.
- URIs MUST NOT embed tenant secrets or internal implementation details.
- For multi-tenant, `asset_id` etc. are unique within the platform (UUIDs), so no tenant ID needs to appear in the URI.

---

## 4. Mapping Rules – Entity to RDF

This section defines how internal entities are translated to RDF.

### 4.1 Asset Mapping (Asset → hub:DataAsset / dcat:Dataset)

Given an `Asset` record:

- `id`
- `name`
- `description`
- `domain`
- `status`
- `semantic_status`
- `primary_contract_id`, etc.

We generate triples:

```turtle
<asset-uri> a hub:DataAsset, dcat:Dataset ;
  dct:title          "Customer Orders" ;
  dct:description    "Orders data product for analytics." ;
  dcat:theme         "sales" ;
  hub:status         "ACTIVE" ;
  hub:semanticStatus "OK" ;
  hub:hasContract    <contract-uri> .
```

**Field mappings:**

- `asset.name`            → `dct:title`
- `asset.description`     → `dct:description`
- `asset.domain`          → `dcat:theme` (string or concept URI in future)
- `asset.status`          → `hub:status`
- `asset.semantic_status` → `hub:semanticStatus`
- `asset.primary_contract_id` → `hub:hasContract` → `contract-uri`

If no contract exists yet, `hub:hasContract` is omitted.

### 4.2 Contract Mapping (Contract + HubContract → hub:DataContract)

From `Contract`:

- `id`
- `original_spec_type`
- `original_spec_version`
- `hub_contract_version`
- `original_format`
- `hub_contract_json` (normalized structure)

We generate:

```turtle
<contract-uri> a hub:DataContract ;
  dct:title              "Customer Orders Contract" ;
  dct:description        "Orders data product for analytics." ;
  hub:contractSpecType   "ODCS" ;
  hub:contractSpecVersion "3.0.2" ;
  hub:hubContractVersion  1 ;
  hub:originalFormat     "YAML" ;
  dct:identifier         "contract-uuid-or-human-readable-key" ;
  hub:hasOwner           <owner-uri> ;
  hub:hasTag             <tag-uri-1>, <tag-uri-2> ;
  dcat:keyword           "sales", "orders", "analytics" ;
  hub:hasQualityRule     <quality-rule-uri> ;
  hub:hasCompliancePolicy <compliance-policy-uri> ;
  hub:hasLifecyclePolicy  <lifecycle-policy-uri> ;
  hub:hasMarketplacePolicy <marketplace-policy-uri> .
```

**Field mappings:**

- `contract.original_spec_type`    → `hub:contractSpecType`
- `contract.original_spec_version` → `hub:contractSpecVersion`
- `contract.hub_contract_version`  → `hub:hubContractVersion`
- `contract.original_format`       → `hub:originalFormat`
- `hub_contract_json.info.name` (if present) → `dct:title`
- `hub_contract_json.info.description` (if present) → `dct:description`
- `hub_contract_json.info.version` (if present) → `dct:hasVersion`
- `contract.id` or an external key → `dct:identifier`

**Info section mappings:**

- `hub_contract_json.info.owners[]` → For each owner:
  - Create `hub:Owner` (or `foaf:Agent`) resource
  - Set `hub:ownerName` and `hub:ownerEmail` (or `foaf:name` and `foaf:mbox`)
  - Link via `hub:hasOwner`
- `hub_contract_json.info.tags[]` → For each tag:
  - Create `hub:Tag` resource
  - Set `rdfs:label` to tag value
  - Link via `hub:hasTag`
  - Also add as `dcat:keyword` for DCAT compatibility

**Quality section mappings:**

- `hub_contract_json.quality.default_profile_key` → `hub:defaultQualityProfile`
- `hub_contract_json.quality.rules[]` → For each rule:
  - Create `hub:QualityRule` resource
  - Set `hub:ruleId`, `hub:ruleDimension`, `hub:ruleExpression`, `hub:ruleSeverity`
  - Link dimension to DQV vocabulary (e.g., `dqv:completeness`, `dqv:accuracy`)
  - Link via `hub:hasQualityRule`

**Privacy/Compliance section mappings:**

- `hub_contract_json.privacy_compliance.contains_personal_data` → `hub:containsPersonalData`
- `hub_contract_json.privacy_compliance.personal_data_categories[]` → For each category:
  - Add `hub:hasPersonalDataCategory` (literal)
  - Link to DPV vocabulary where applicable (e.g., `dpv:EmailAddress`, `dpv:PhoneNumber`)
- `hub_contract_json.privacy_compliance.jurisdictions[]` → For each jurisdiction:
  - Add `hub:hasJurisdiction` (literal)
  - Link to DPV vocabulary where applicable (e.g., `dpv:EU-GDPR`, `dpv:BR-LGPD`)
- `hub_contract_json.privacy_compliance.legal_bases[]` → For each legal basis:
  - Add `hub:hasLegalBasis` (literal)
  - Link to DPV vocabulary where applicable (e.g., `dpv:Consent`, `dpv:Contract`)
- `hub_contract_json.privacy_compliance.retention_policy.period` → `hub:retentionPeriod`
- `hub_contract_json.privacy_compliance.retention_policy.notes` → `hub:retentionNotes`

**Lifecycle section mappings:**

- `hub_contract_json.lifecycle.data_source` → `hub:dataSource` (URI or literal)
  - Also create PROV-O relationship: `prov:wasDerivedFrom <source-uri>`
- `hub_contract_json.lifecycle.refresh_cadence` → `hub:refreshCadence`
- `hub_contract_json.lifecycle.slas.availability` → `hub:availabilitySLA`
- `hub_contract_json.lifecycle.slas.latency_ms_p95` → `hub:latencySLA`

**Marketplace section mappings:**

- `hub_contract_json.marketplace.license_summary` → `hub:licenseSummary`
- `hub_contract_json.marketplace.intended_use[]` → For each use:
  - Add `hub:intendedUse` (literal)
  - Create ODRL permission: `odrl:Permission` with `odrl:action` mapped from use case
- `hub_contract_json.marketplace.restricted_use[]` → For each restricted use:
  - Add `hub:restrictedUse` (literal)
  - Create ODRL prohibition: `odrl:Prohibition` with `odrl:action` mapped from use case

### 4.3 Schema & Fields (HubContract.schema → hub:Field)

Assuming `hub_contract_json` includes a schema section like:

```json
{
  "schema": {
    "fields": [
      {
        "name": "order_id",
        "data_type": "string",
        "nullable": false,
        "description": "Order identifier",
        "semantic_type": "ORDER_ID",
        "format": null,
        "pattern": "^ORD-[0-9]{8}$",
        "enum": null,
        "default": null,
        "min_length": 10,
        "max_length": 20,
        "minimum": null,
        "maximum": null,
        "metadata": {}
      }
    ],
    "primary_key": ["order_id"],
    "unique_constraints": [],
    "indexes": []
  }
}
```

For each field:

```turtle
<field-uri> a hub:Field ;
  hub:fieldName        "order_id" ;
  hub:fieldDataType    "string" ;
  hub:fieldNullable    false ;
  dct:description      "Order identifier" ;
  hub:fieldPIICategory "NONE" ;
  hub:fieldSemanticType "ORDER_ID" ;
  hub:fieldPattern     "^ORD-[0-9]{8}$" ;
  shacl:pattern        "^ORD-[0-9]{8}$" ;
  hub:fieldMinLength   10 ;
  shacl:minLength      10 ;
  hub:fieldMaxLength   20 ;
  shacl:maxLength      20 ;
  hub:isPrimaryKey     true .
```

And link back:

```turtle
<asset-uri> hub:hasField <field-uri> .
```

**Field mappings:**

- `fields[i].name`          → `hub:fieldName`
- `fields[i].data_type`     → `hub:fieldDataType`
- `fields[i].nullable`      → `hub:fieldNullable`
- `fields[i].description`   → `dct:description`
- `fields[i].semantic_type` → `hub:fieldSemanticType` (may also link to Schema.org types via `rdf:type`)
- `fields[i].format`         → `hub:fieldFormat`
- `fields[i].pattern`        → `hub:fieldPattern` and `shacl:pattern`
- `fields[i].enum`           → repeated `hub:fieldEnum` (one per enum value)
- `fields[i].default`        → `hub:fieldDefault`
- `fields[i].min_length`     → `hub:fieldMinLength` and `shacl:minLength`
- `fields[i].max_length`     → `hub:fieldMaxLength` and `shacl:maxLength`
- `fields[i].minimum`        → `hub:fieldMinimum` and `shacl:minInclusive`
- `fields[i].maximum`        → `hub:fieldMaximum` and `shacl:maxInclusive`
- PII category, if known from compliance runs:
  - e.g. `column_findings["customer_email"].categories = ["PII_EMAIL"]` → `hub:fieldPIICategory "PII_EMAIL"`.
- Primary key: If field name in `schema.primary_key[]` → `hub:isPrimaryKey true`
- Unique constraint: If field name in `schema.unique_constraints[]` → `hub:isUnique true`
- Index: If field name in `schema.indexes[]` → `hub:isIndexed true`

**Schema constraint mappings:**

- `schema.primary_key[]` → For each field in primary key, set `hub:isPrimaryKey true`
- `schema.unique_constraints[]` → For each field in unique constraints, set `hub:isUnique true`
- `schema.indexes[]` → For each field in indexes, set `hub:isIndexed true`

If multiple PII categories apply, additional properties or a list may be used.

### 4.4 Dataset Version Mapping (Dataset → hub:DatasetVersion / dcat:Distribution)

Given a `Dataset`:

- `id`
- `asset_id`
- `data_file_id`
- `row_count`
- `schema_json`
- `created_at`, etc.

We generate:

```turtle
<dataset-uri> a hub:DatasetVersion, dcat:Distribution ;
  dct:title         "Customer Orders Snapshot 2025-01-01" ;
  dct:issued        "2025-01-01T12:00:00Z"^^xsd:dateTime ;
  hub:rowCount      120000 ;
  hub:belongsToAsset <asset-uri> ;
  dcat:accessURL    <download-or-api-url> .
```

**Field mappings:**

- `dataset.id`          → `dataset-uri`
- `dataset.row_count`   → `hub:rowCount`
- `dataset.created_at`  → `dct:issued`
- `dataset.asset_id`    → `hub:belongsToAsset` → `asset-uri`
- Data access endpoints (if defined) → `dcat:accessURL`, `dcat:downloadURL` (API endpoints or pre-signed URL templates).

### 4.5 Data Quality Run Mapping (DQRun → hub:DataQualityRun)

Given a `DQRun`:

- `id`
- `asset_id`
- `dataset_id`
- `overall_status`
- `quality_score`
- `started_at`, `completed_at`, etc.

We generate:

```turtle
<dqrun-uri> a hub:DataQualityRun ;
  hub:overallDQStatus "PASS" ;
  hub:qualityScore    95.2 ;
  dct:created         "2025-01-01T12:02:00Z"^^xsd:dateTime ;
  hub:targetAsset     <asset-uri> ;
  hub:targetDataset   <dataset-uri> .
```

**Field mappings:**

- `dq_run.overall_status`   → `hub:overallDQStatus`
- `dq_run.quality_score`    → `hub:qualityScore`
- `dq_run.completed_at`     → `dct:created`
- `dq_run.asset_id`         → `hub:targetAsset`
- `dq_run.dataset_id`       → `hub:targetDataset`

Details of individual checks (`checks_json`) are not necessarily fully mapped; selected high-level metrics may be exposed later.

### 4.6 Compliance Run Mapping (ComplianceRun → hub:ComplianceRun)

Given a `ComplianceRun`:

- `id`
- `asset_id`, `dataset_id`
- `overall_status`
- `risk_level`
- `allowed_to_store`
- `applicable_regimes[]`
- `detected_categories[]`
- `started_at`, `completed_at`, etc.

We generate:

```turtle
<compliance-uri> a hub:ComplianceRun ;
  hub:overallComplianceStatus "WARN" ;
  hub:riskLevel               "MEDIUM" ;
  hub:allowedToStore          true ;
  hub:applicableRegime        "GDPR", "LGPD" ;
  hub:targetAsset             <asset-uri> ;
  hub:targetDataset           <dataset-uri> .
```
 
We may also link categories:

```turtle
<compliance-uri> hub:detectedCategory "PII_EMAIL", "PII_FINANCIAL_CARD" .
```

**Field mappings:**

- `compliance_run.overall_status`       → `hub:overallComplianceStatus`
- `compliance_run.risk_level`           → `hub:riskLevel`
- `compliance_run.allowed_to_store`     → `hub:allowedToStore`
- `compliance_run.applicable_regimes[]` → repeated `hub:applicableRegime`
- `compliance_run.detected_categories[]`→ repeated `hub:detectedCategory` (if defined)
- `asset_id` / `dataset_id`             → `hub:targetAsset` / `hub:targetDataset`

### 4.7 Marketplace Listing Mapping (Listing → hub:MarketplaceListing)

Given a `MarketplaceListing`:

- `id`
- `asset_id`
- `status`
- `title`
- `short_description`
- `price_model`
- `price_amount`
- `currency`, etc.

We generate:

```turtle
<listing-uri> a hub:MarketplaceListing ;
  dct:title       "Customer Orders (EU)" ;
  dct:description "Daily EU orders snapshot." ;
  hub:listingStatus "PUBLISHED" ;
  hub:priceModel    "ONE_TIME" ;
  hub:priceAmount   99.0 ;
  hub:currency      "USD" ;
  hub:linkedAsset   <asset-uri> .
```

---

## 5. Mapping Process & Architecture

### 5.1 Event-Driven Mapping

Semantic mapping is **event-driven** and **asynchronous**.

Events that trigger mapping (or re-mapping):

- `AssetCreated`, `AssetUpdated`
- `ContractCreated`, `ContractValidated`, `ContractUpdated`
- `DatasetCreated`
- `DQRunCompleted`
- `ComplianceRunCompleted`
- `ListingCreated`, `ListingUpdated`

#### 5.1.1 Automatic Trigger Timing

**Trigger Mechanism**

- **Event publication**: Events are published to a message bus (e.g., RabbitMQ, Kafka) immediately after the triggering operation completes
- **Event processing**: `semantic-mapper` service consumes events from the message bus
- **Processing delay**: Mapping jobs are queued and processed asynchronously with the following timing:

**Timing Details**

- **Immediate queuing**: Mapping job is **queued immediately** (within 1 second) after the triggering event is published
- **Processing start**: Mapping job **starts processing within 5 minutes** of event publication (under normal load)
- **Processing duration**: Mapping typically completes within **30 seconds to 2 minutes** (depending on entity complexity)
- **Total delay**: From triggering operation to semantic representation update: **typically 5-7 minutes** (under normal load)

**Trigger Conditions**

- **AssetCreated**: Triggered immediately after asset record is created in database
- **AssetUpdated**: Triggered immediately after asset record is updated (any field change)
- **ContractCreated**: Triggered immediately after contract record is created
- **ContractValidated**: Triggered after contract validation completes (`validation_status` is set)
- **ContractUpdated**: Triggered immediately after contract record is updated
- **DatasetCreated**: Triggered immediately after dataset record is created and linked to asset
- **DQRunCompleted**: Triggered after DQ run reaches terminal status (`SUCCEEDED`, `FAILED`)
- **ComplianceRunCompleted**: Triggered after compliance run reaches terminal status (`SUCCEEDED`, `FAILED`)
- **ListingCreated**: Triggered immediately after listing record is created
- **ListingUpdated**: Triggered immediately after listing record is updated

**Conditions That Prevent Auto-Mapping**

- **Tenant suspension**: Mapping is **not triggered** for events from suspended tenants (`status = SUSPENDED`)
- **Asset deletion**: Mapping is **not triggered** for deleted assets (`status = RETIRED` or hard-deleted)
- **Contract invalidation**: Mapping is **not triggered** for contracts with `validation_status = INVALID` or `ERROR` (unless explicitly requested via manual remap)
- **Queue backlog**: If message queue has significant backlog (> 1000 pending events), new mapping jobs may be delayed
- **Triple store unavailability**: If triple store is unavailable, mapping jobs are queued but not processed until store recovers

**Manual Trigger**

- **Endpoint**: `POST /api/v1/assets/{id}/remap`
- **Behavior**: Immediately queues a new mapping job (bypasses normal event-driven flow)
- **Use cases**:
  - After fixing data/contract issues
  - After triple store recovery
  - To refresh semantic representation after manual edits
  - To retry failed mappings

**Batch Processing**

- **Batching**: Multiple events for the same asset/contract may be batched together (processed in a single mapping job)
- **Deduplication**: If multiple events are received for the same entity within a short window (e.g., 1 minute), only one mapping job is created
- **Processing order**: Events are processed in order of receipt (FIFO)

A dedicated `semantic-mapper` service:

1. Listens to domain events (via message bus or internal queue).
2. Loads the relevant entities from the core database.
3. Applies the mapping rules described above.
4. Writes the resulting RDF to the triple store / semantic DB.

### 5.2 Asynchronous Behavior

- Core user flows (intake, DQ, compliance, marketplace) MUST NOT be blocked by RDF mapping.
- `/id/...` endpoints:
  - Should return semantic representations based on the current state of the triple store.
  - There may be a slight delay between core updates and semantic updates.
- Assets have a `semantic_status` field indicating mapping health:
  - `OK` – mapping up-to-date.
  - `DEGRADED` – mapping incomplete or failed.

### 5.3 Handling Contract & HubContract Version Changes

Semantic mapping is driven by Contract and HubContract events, while keeping
URIs for assets and contracts stable over time.

- The stable identifier for a contract in the semantic layer is:

  - `<contract-uri> = https://hub.example.com/id/contract/{contract_id}`

- When a contract is edited **without** changing `hub_contract_version`
  (e.g. description changes, minor field tweaks), the mapper:

  - Re-runs the Contract + Field mapping.
  - Updates triples for the existing `<contract-uri>` and `<field-uri>` resources in place.
  - Bumps the internal `mapping_version` for the affected entities
    (see Technical Design Document).

- When the contract is migrated to a **new** `hub_contract_version`
  (e.g. HubContract v1 → v2 for the same logical contract):

  - The same `<contract-uri>` remains the primary identifier in RDF.
  - The `hub:hubContractVersion` value is updated to the new version.
  - Triples are updated to follow the new normalized structure
    (including new/renamed/removed fields).
  - Fields that no longer exist in the new version SHOULD be removed or clearly
    deprecated in RDF on the next mapping run.

- Mapping jobs MUST always use the **latest normalized HubContract** for a given
  `contract_id` and `hub_contract_version`; older schemas MUST NOT be re-used
  for new mapping runs. 

- Historical, versioned representations of contracts MAY be exposed under
  versioned URIs (e.g. `/id/contract/{contract_id}/version/{n}`) in future
  iterations, but this is **out of scope for MVP**.

### 5.4 Semantic Store Technology (MVP)

For MVP, the semantic graph is stored in **Apache Jena Fuseki**:

- **Engine**: Apache Jena Fuseki with a TDB2-backed dataset.
- **Interface**:
  - Internal SPARQL endpoint used by the `semantic-mapper` service for inserts/updates.
  - Read-only SPARQL endpoint exposed via the hub’s API gateway for semantic queries (subject to auth and tenant scoping).
- **Multi-tenancy**:
  - Tenant isolation is enforced via:
    - URI design (tenant-scoped URIs as defined in §3).
    - Named graphs per tenant and/or access control in the semantic service.
- **Future flexibility**:
  - The design assumes only standard SPARQL 1.1 + RDF; the engine MAY be swapped (e.g., to Amazon Neptune) in a future phase without changing mapping rules or ontology.


---
## 6. Failure Handling & semantic_status

Semantic mapping is intentionally **best-effort** and **non-blocking** for core flows (intake, DQ, compliance, marketplace). When something goes wrong, we surface it via `semantic_status` and job state rather than breaking core data paths.

This section refines failure handling with:

- Explicit failure categories.
- Retry behavior for failed mappings.
- Manual rebuild operations.
- Partial mapping semantics.
- Consistency checks between RDF and the relational database.

### 6.1 Types of semantic failures

Examples of failures:

- **SYSTEM failures**
  - RDF / triple store unavailable (network, downtime).
  - Timeouts or resource exhaustion in the semantic service.
  - Serialization/parsing errors not tied to a specific mapping rule.

- **MAPPING failures**
  - Referenced column/field does not exist in the dataset schema.
  - Invalid or unknown ontology term / IRI.
  - Conflicting or malformed mapping rules.

- **PARTIAL failures**
  - Some mapping rules apply successfully; others fail with SYSTEM or MAPPING errors.
  - Triple store is left in a consistent but incomplete state.

### 6.2 Status updates

For each mapping attempt (per asset/dataset):

- If mapping and write **fully succeed**:
  - `asset.semantic_status = "OK"` (for that asset and its related entities).
- If any mapping or write **fails**:
  - `asset.semantic_status = "DEGRADED"`.
  - A `SEMANTIC_MAPPING_FAILED` or `SEMANTIC_MAPPING_PARTIAL` `AuditEvent` MUST be emitted with:
    - Entity IDs (asset/contract/dataset).
    - Error category (`SYSTEM`, `MAPPING`, `PARTIAL`).
    - Sanitized error message.

### 6.3 Retry Strategy

**Automatic Retries**

- **Retry attempts**: 3 automatic retries with exponential backoff
- **Backoff intervals**: 1 minute, 5 minutes, 30 minutes
- **Retry triggers**: Only for **transient errors**:
  - Network failures (connection refused, timeout)
  - Triple store unavailability (temporary)
  - Resource exhaustion (temporary)
  - Timeout errors
- **No retry for**: Permanent errors (invalid data, malformed mapping rules, unknown ontology terms)

**Retry Process**

1. **First failure**: Mapping job marked as `FAILED`, `semantic_status = DEGRADED`
2. **Automatic retry #1** (after 1 minute): Re-attempts mapping
3. **Automatic retry #2** (after 5 minutes): Re-attempts mapping if retry #1 failed
4. **Automatic retry #3** (after 30 minutes): Final retry attempt
5. **Permanent failure**: After 3 retries, mapping is considered permanently failed:
   - `semantic_status = DEGRADED` (remains)
   - Asset remains functional (core features work)
   - Semantic features (SPARQL queries, JSON-LD resolution) may be incomplete

**Manual Retry**

- **Endpoint**: `POST /api/v1/assets/{id}/remap`
- **Roles**: `DATA_PROVIDER` or `TENANT_ADMIN`
- **Behavior**:
  - Triggers a new semantic mapping job for the asset
  - Resets retry counter
  - Updates `semantic_status` based on result
- **Use cases**:
  - After fixing data/contract issues
  - After triple store recovery
  - To refresh semantic representation after manual edits

**Permanent Failure Handling**

- If mapping permanently fails (after all retries):
  - `semantic_status = DEGRADED` is set and remains
  - Asset core functionality is **not affected**:
    - Asset can still be `ACTIVE`
    - DQ/compliance checks continue to work
    - Marketplace listings remain functional
  - Semantic features are **degraded**:
    - SPARQL queries may return incomplete results
    - JSON-LD resolution (`/id/asset/{id}`) may return partial data
    - Semantic search may not include this asset
- Users are notified via UI and audit logs
- Manual retry is always available via `POST /api/v1/assets/{id}/remap`
    - Timestamp and retry count.

**Important:**

- A semantic failure MUST NOT change the validity of the asset/contract/data itself.
- Core operations (intake, DQ, compliance, data access) continue to work.
- Only semantic views and SPARQL/JSON-LD results may be incomplete.

### 6.3 Retry strategy for failed mappings

Retries are applied only when the failure is likely **transient**.

- Automatic retries are enabled for **SYSTEM failures** only.
- **MAPPING failures** (bad rules, missing columns, invalid IRIs) are **not retried** automatically until configuration changes.

Per-job defaults for `SEMANTIC_MAPPING` jobs:

- Max attempts: **3** (1 initial + 2 retries).
- Backoff with jitter:
  - Attempt 1 → 2: delay ~30 seconds.
  - Attempt 2 → 3: delay ~120 seconds.
  - ±50% random jitter to avoid synchronized retries.
- On all attempts failing with SYSTEM errors:
  - Job status: `FAILED`.
  - `asset.semantic_status` remains or becomes `"DEGRADED"`.
  - Existing, previously-successful semantic graph (if any) is preserved but treated as potentially stale.

For MAPPING failures:

- Job status: `FAILED` (or `SUCCEEDED_PARTIAL` if the job model supports it).
- `asset.semantic_status = "DEGRADED"`.
- Detailed rule-level errors are persisted for UI display and debugging.
- No automatic retry is scheduled; user must fix mapping rules and then trigger a manual rebuild.

### 6.4 Manual rebuild operations

Users and operators need a way to re-run semantic mapping after:

- Fixing mapping rules or ontology references.
- Changing dataset schemas.
- Recovering from triple store incidents or restores.

API (conceptual):

```http
POST /api/v1/semantic-runs
Content-Type: application/json

{
  "asset_id": "uuid",
  "dataset_id": "uuid",   // optional – defaults to latest_dataset_id
  "mode": "REBUILD"       // future: "INFER_ONLY", "INCREMENTAL"
}
```

Behavior:

1. Validate that the caller is allowed to manage semantics for the asset’s tenant.
2. Resolve `dataset_id`:
   - If omitted, use the asset’s `latest_dataset_id` (if any).
3. Enqueue a `SEMANTIC_MAPPING` job for that `(asset_id, dataset_id)`.
4. Job runs with the same retry strategy as above (SYSTEM-only retries).
5. On successful completion:
   - Asset’s `semantic_status` is set to `"OK"`.
   - Coverage metrics are updated.
6. On failure:
   - Asset’s `semantic_status` stays `"DEGRADED"`.
   - Rule-level errors are updated; a new audit event is emitted.

Optional convenience endpoints:

- `POST /api/v1/assets/{id}/semantic/rebuild` → wraps `POST /semantic-runs` with `asset_id` path param.
- Admin/ops endpoint:
  - `POST /api/v1/semantic/rebuild-tenant` to enqueue rebuilds for all assets in a tenant (throttled) after a triple store restore or major ontology change.

### 6.5 Partial mappings

If some entities or fields map successfully while others fail in the same job:

- Successfully mapped triples:
  - **Remain stored** in the asset’s named graph.
  - Are used for SPARQL and JSON-LD responses.
- Failed mappings:
  - Are **not written** to the triple store.
  - Are recorded in a rule-level error store with:
    - `mapping_rule_id`
    - `field_name` / `column_name`
    - `error_code` (e.g. `COLUMN_NOT_FOUND`, `INVALID_IRI`, `CONFLICTING_RULE`)
    - human-readable `error_message`.

Asset-level behavior:

- Set `semantic_status = "DEGRADED"`.
- Track coverage metrics, e.g.:

  ```json
  {
    "fields_total": 20,
    "fields_mapped_successfully": 15,
    "fields_failed": 5
  }
  ```

- UI and API should:
  - Clearly indicate that the semantic model is **degraded**, but partially usable.
  - Still enable semantic discovery based on the successfully mapped subset.
  - Surface failed fields and error reasons to mapping owners.

The mapper MUST NOT write obviously invalid or inconsistent statements (e.g. missing required RDF types); rules either succeed and write complete triples or they are skipped.

### 6.6 Consistency checks (RDF vs relational DB)

The relational database is the **source of truth** for:

- Assets, datasets, contracts, and runs.
- Semantic mapping configuration (rules, ontology bindings).

The triple store is a **derived** view. We maintain consistency using:

1. **Post-job verification**

   After each `SEMANTIC_MAPPING` job:

   - Compare counts:
     - Number of active mapping rules for an asset vs.
     - Approximate number of triples created per rule (within a tolerance).
   - Run small SPARQL spot checks:
     - For a subset of mapped fields, verify that at least one triple exists with the expected predicate/class.

   If checks fail:

   - Mark job as `FAILED` or `SUCCEEDED_WITH_WARNINGS`.
   - Keep `asset.semantic_status = "DEGRADED"`.
   - Optionally enqueue a follow-up job or flag for manual review.

2. **Periodic reconciliation**

   A background “semantic reconciler” job runs periodically (e.g. nightly):

   - Scans assets with `semantic_status = "DEGRADED"` or recent mapping changes.
   - For each asset:
     - Compare mapping configuration in the DB against triples in the asset’s named graph.
     - Detect:
       - Orphan graphs (asset/dataset deleted in DB but still present in RDF).
       - Missing graphs for assets that should have mappings.

   For detected inconsistencies, the reconciler may:

   - Enqueue a semantic rebuild job.
   - Or mark the asset with a more specific degradation reason (e.g. `RDF_OUT_OF_SYNC`).

3. **Triple store restore handling**

   After restoring the triple store from backup:

   - Determine the backup timestamp.
   - Identify assets/datasets created or changed **after** that timestamp.
   - Mark those assets:
     - `semantic_status = "DEGRADED"`.
   - Optionally enqueue rebuild jobs for them, throttled per tenant and per environment.

4. **Audit & traceability**

   Every semantic mapping job and reconciliation pass writes audit events:

   - `SEMANTIC_MAPPING_STARTED`
   - `SEMANTIC_MAPPING_COMPLETED`
   - `SEMANTIC_MAPPING_PARTIAL`
   - `SEMANTIC_MAPPING_FAILED`
   - `SEMANTIC_RECONCILIATION_RUN`

Each event includes:

- `asset_id`, `dataset_id`, `tenant_id`, `job_id` (if applicable).
- Counts of rules processed, succeeded, and failed.
- Error categories and key messages (sanitized).
- Any reconciliation actions taken (e.g., rebuild enqueued).

These mechanisms together ensure that:

- Failed or partial mappings are surfaced clearly and can be recovered.
- The semantic graph remains broadly consistent with the relational configuration.
- Semantic features degrade gracefully but safely in the presence of failures.

---

## 7. Privacy & Data Minimization in RDF

### 7.1 No Raw PII in RDF

The semantic model MUST **never** include raw PII or sensitive values:

- No actual emails, phone numbers, card numbers, IDs, etc.
- Only derived **categories** and classifications (e.g. `"PII_EMAIL"`).

This aligns with the security and privacy requirements:

- RDF is primarily structural / descriptive.
- Sensitive details stay in underlying data files and are guarded by entitlements & compliance rules.

### 7.2 Categories & Aggregates Only

When reflecting compliance or quality information in RDF:

- Use categories and aggregated metrics:

  - `hub:fieldPIICategory "PII_EMAIL"`
  - `hub:overallDQStatus "PASS"`
  - `hub:overallComplianceStatus "WARN"`
  - `hub:riskLevel "MEDIUM"`

- Optional numeric aggregates like row counts or null ratios may be included, but never cell-level data.

### 7.3 Multi-Tenant Considerations

- Public endpoints (`/id/...`, `/sparql`) MUST:
  - Expose only **public or intentionally shareable metadata**.
  - Respect tenant and listing visibility:
    - Non-public assets MUST NOT appear in public semantic views.
    - Tenant-specific queries (with auth) can show additional internal semantic metadata.

---

## 8. Example JSON-LD Representation

Example JSON-LD for an asset (simplified):

```json
{
  "@context": "https://hub.example.com/context.jsonld",
  "@id": "https://hub.example.com/id/asset/1234",
  "@type": ["hub:DataAsset", "dcat:Dataset"],
  "dct:title": "Customer Orders",
  "dct:description": "Orders data product for analytics.",
  "dcat:theme": "sales",
  "hub:status": "ACTIVE",
  "hub:semanticStatus": "OK",
  "hub:hasContract": {
    "@id": "https://hub.example.com/id/contract/abcd",
    "@type": "hub:DataContract"
  },
  "hub:hasField": [
    {
      "@id": "https://hub.example.com/id/field/1234/order_id",
      "@type": "hub:Field",
      "hub:fieldName": "order_id",
      "hub:fieldDataType": "string",
      "hub:fieldNullable": false,
      "dct:description": "Order identifier",
      "hub:fieldPIICategory": "NONE"
    },
    {
      "@id": "https://hub.example.com/id/field/1234/customer_email",
      "@type": "hub:Field",
      "hub:fieldName": "customer_email",
      "hub:fieldDataType": "string",
      "hub:fieldNullable": false,
      "hub:fieldPIICategory": "PII_EMAIL"
    }
  ]
}
```

---

## 9. Complete Mapping Example

### 9.1 Full HubContract to RDF Example

Given a complete HubContract with all sections populated:

```json
{
  "hub_contract_version": 1,
  "id": "orders-contract-v1",
  "info": {
    "name": "Customer Orders",
    "description": "Orders data product for analytics.",
    "version": "1.0.0",
    "owners": [
      {"name": "Data Platform Team", "email": "dataplatform@example.com"}
    ],
    "tags": ["sales", "orders", "analytics"]
  },
  "schema": {
    "fields": [
      {
        "name": "order_id",
        "data_type": "string",
        "nullable": false,
        "description": "Unique identifier",
        "semantic_type": "ORDER_ID",
        "pattern": "^ORD-[0-9]{8}$",
        "min_length": 10,
        "max_length": 20
      },
      {
        "name": "customer_email",
        "data_type": "string",
        "nullable": false,
        "description": "Customer email address",
        "semantic_type": "EMAIL",
        "format": "email"
      }
    ],
    "primary_key": ["order_id"],
    "unique_constraints": [],
    "indexes": []
  },
  "quality": {
    "default_profile_key": "intake_basic",
    "rules": [
      {
        "rule_id": "not_null_order_id",
        "dimension": "completeness",
        "expression": "order_id IS NOT NULL",
        "severity": "ERROR"
      }
    ]
  },
  "privacy_compliance": {
    "contains_personal_data": true,
    "personal_data_categories": ["PII_DIRECT_EMAIL"],
    "jurisdictions": ["GDPR", "LGPD"],
    "legal_bases": ["CONSENT", "CONTRACT"],
    "retention_policy": {
      "period": "P5Y",
      "notes": "5 years retention"
    }
  },
  "lifecycle": {
    "data_source": "OLTP.orders",
    "refresh_cadence": "DAILY",
    "slas": {
      "availability": "99.0",
      "latency_ms_p95": 5000
    }
  },
  "marketplace": {
    "license_summary": "Internal only",
    "intended_use": ["analytics", "machine_learning"],
    "restricted_use": ["credit_scoring"]
  }
}
```

The complete RDF representation:

```turtle
@prefix hub: <https://hub.example.com/ontology#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix dqv: <https://www.w3.org/ns/dqv#> .
@prefix dpv: <https://www.w3.org/ns/dpv#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix odrl: <https://www.w3.org/ns/odrl/2/> .
@prefix shacl: <http://www.w3.org/ns/shacl#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix schema: <https://schema.org/> .

# Contract
<https://hub.example.com/id/contract/uuid-123> a hub:DataContract ;
  dct:title "Customer Orders" ;
  dct:description "Orders data product for analytics." ;
  dct:hasVersion "1.0.0" ;
  hub:contractSpecType "ODCS" ;
  hub:contractSpecVersion "3.0.2" ;
  hub:hubContractVersion 1 ;
  hub:originalFormat "YAML" ;
  dct:identifier "orders-contract-v1" ;
  hub:hasOwner <https://hub.example.com/id/owner/hash-email> ;
  hub:hasTag <https://hub.example.com/id/tag/hash-sales>, <https://hub.example.com/id/tag/hash-orders> ;
  dcat:keyword "sales", "orders", "analytics" ;
  hub:hasQualityRule <https://hub.example.com/id/contract/uuid-123/quality-rule/not_null_order_id> ;
  hub:hasCompliancePolicy <https://hub.example.com/id/contract/uuid-123/compliance-policy> ;
  hub:hasLifecyclePolicy <https://hub.example.com/id/contract/uuid-123/lifecycle-policy> ;
  hub:hasMarketplacePolicy <https://hub.example.com/id/contract/uuid-123/marketplace-policy> .

# Owner
<https://hub.example.com/id/owner/hash-email> a foaf:Agent ;
  foaf:name "Data Platform Team" ;
  foaf:mbox "mailto:dataplatform@example.com" .

# Tags
<https://hub.example.com/id/tag/hash-sales> a hub:Tag ;
  rdfs:label "sales" .

<https://hub.example.com/id/tag/hash-orders> a hub:Tag ;
  rdfs:label "orders" .

# Quality Rule
<https://hub.example.com/id/contract/uuid-123/quality-rule/not_null_order_id> a hub:QualityRule ;
  hub:ruleId "not_null_order_id" ;
  hub:ruleDimension "completeness" ;
  dqv:isMeasurementOf dqv:completeness ;
  hub:ruleExpression "order_id IS NOT NULL" ;
  hub:ruleSeverity "ERROR" .

# Compliance Policy
<https://hub.example.com/id/contract/uuid-123/compliance-policy> a hub:CompliancePolicy ;
  hub:containsPersonalData true ;
  hub:hasPersonalDataCategory "PII_DIRECT_EMAIL" ;
  dpv:hasPersonalDataCategory dpv:EmailAddress ;
  hub:hasJurisdiction "GDPR", "LGPD" ;
  dpv:hasJurisdiction dpv:EU-GDPR, dpv:BR-LGPD ;
  hub:hasLegalBasis "CONSENT", "CONTRACT" ;
  dpv:hasLegalBasis dpv:Consent, dpv:Contract ;
  hub:retentionPeriod "P5Y" ;
  hub:retentionNotes "5 years retention" .

# Lifecycle Policy
<https://hub.example.com/id/contract/uuid-123/lifecycle-policy> a hub:LifecyclePolicy ;
  hub:dataSource <https://hub.example.com/id/source/hash-oltp-orders> ;
  hub:refreshCadence "DAILY" ;
  hub:availabilitySLA "99.0" ;
  hub:latencySLA 5000 .

<https://hub.example.com/id/source/hash-oltp-orders> a prov:Entity ;
  rdfs:label "OLTP.orders" .

# Marketplace Policy
<https://hub.example.com/id/contract/uuid-123/marketplace-policy> a hub:MarketplacePolicy ;
  hub:licenseSummary "Internal only" ;
  hub:intendedUse "analytics", "machine_learning" ;
  hub:restrictedUse "credit_scoring" ;
  odrl:permission [
    a odrl:Permission ;
    odrl:action odrl:use
  ] ;
  odrl:prohibition [
    a odrl:Prohibition ;
    odrl:action odrl:use
  ] .

# Fields
<https://hub.example.com/id/field/asset-uuid/order_id> a hub:Field ;
  hub:fieldName "order_id" ;
  hub:fieldDataType "string" ;
  hub:fieldNullable false ;
  dct:description "Unique identifier" ;
  hub:fieldSemanticType "ORDER_ID" ;
  hub:fieldPattern "^ORD-[0-9]{8}$" ;
  shacl:pattern "^ORD-[0-9]{8}$" ;
  hub:fieldMinLength 10 ;
  shacl:minLength 10 ;
  hub:fieldMaxLength 20 ;
  shacl:maxLength 20 ;
  hub:isPrimaryKey true .

<https://hub.example.com/id/field/asset-uuid/customer_email> a hub:Field, schema:EmailAddress ;
  hub:fieldName "customer_email" ;
  hub:fieldDataType "string" ;
  hub:fieldNullable false ;
  dct:description "Customer email address" ;
  hub:fieldSemanticType "EMAIL" ;
  hub:fieldFormat "email" ;
  hub:fieldPIICategory "PII_EMAIL" .
```

## 10. Open Issues & Future Extensions

- **Ontology refinement**  
  Further alignment with DCAT-AP, schema.org, and sector-specific ontologies (e.g. FIBO for finance, HL7 for health).

- **SHACL / OWL validation**  
  Formal constraint sets to validate semantic graph consistency; integration with CI.

- **Richer semantic search**  
  Index contracts and assets by domain concepts, legal constraints, and quality attributes.

- **Cross-hub federation**  
  Expose public DCAT catalogs for federation with external catalogs and data portals.

- **Semantic type mapping**  
  Automatic mapping of `semantic_type` values to Schema.org types and other standard vocabularies.

- **Vocabulary alignment**  
  Regular updates to align with latest versions of DQV, DPV, PROV-O, ODRL, and other standard vocabularies.

This design provides comprehensive coverage of contract normalization and ontology representation, ensuring full information preservation and maximum interoperability through standard vocabulary reuse.
