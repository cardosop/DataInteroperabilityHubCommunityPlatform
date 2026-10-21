# Critical Paths Prototypes – Interoperable Data Hub

> Scope: MVP v1  
> Status: Draft  
> Purpose: Describe and standardize the **critical path prototypes** that should be built early to de-risk the platform.

This document captures three high-priority technical spikes:

1. DataContract CLI integration  
2. Compliance service with sample data  
3. Semantic mapping from HubContract to RDF  

Each prototype is designed to be small, focused, and runnable in isolation, proving the most complex pieces of the architecture before the full system is implemented.

# Additions for CriticalPaths.md

The following sections are meant to be added to your existing **CriticalPaths.md**
document. You can paste them in appropriate places (for example, near the
prototype descriptions).

### Language Choice for Prototypes

Code examples in this document use **Python** for clarity and brevity. The
intent is to illustrate:

- the shape of service boundaries,
- how jobs/DQ/compliance/semantic mapping are orchestrated,
- how results flow through the system,

not to prescribe a specific production language or framework.

The **authoritative contracts** are:

- the HTTP/API definitions (`API_Spec_v1.md` / OpenAPI),
- the database schema (`Database_Schema.md`),
- and the job/queue semantics (`System_Architecture.md`).

Implementations MAY use a different stack (e.g. Node.js/TypeScript, Java, etc.)
as long as they conform to those contracts. Prototype code SHOULD be treated as
reference behavior rather than a hard requirement on the tech stack.


---

## Integration & Build Order

To minimise integration risk and rework, the three critical prototypes should be
built and integrated in the following order:

1. **Prototype 1 – Ingestion & Canonical Contract Model**
   - Establishes the core pipeline for bringing data into the hub and producing
     the normalized / canonical model used by downstream components.
   - Provides stable interfaces and sample datasets that the other prototypes
     can consume.

2. **Prototype 2 – Semantic Mapping & RDF Persistence**
   - Depends on the canonical contract model being available.
   - Exercises the semantic mapping rules, triple store integration, and query
     patterns required by later features (e.g., lineage, discovery).

3. **Prototype 3 – Compliance & Data Quality Rules**
   - Depends on both the canonical model and semantic layer.
   - Validates how well the earlier prototypes support real compliance and DQ
     scenarios (rules authoring, rule execution, reporting).

> **Rationale:** Each prototype builds on the foundations of the previous one.
> This sequence ensures we learn about schema design and integration issues
> early, then validate them in realistic compliance use cases.

---

## Effort & Complexity

The following estimates are indicative for the MVP and should be refined with
the implementation team.

| Prototype                                      | Complexity | Est. Dev Effort* | Notes                                           |
| ---------------------------------------------- | ---------- | ---------------- | ----------------------------------------------- |
| Ingestion & Canonical Contract Model           | Medium     | 5–8 days         | Service + basic persistence + happy-path tests. |
| Semantic Mapping & RDF Persistence             | High       | 8–12 days        | Mapping rules, triple store, query validation.  |
| Compliance & Data Quality Rules (batch focus)  | Medium     | 5–8 days         | Rule engine wiring + first rule set + reports.  |

\*Estimates are per engineer and assume familiarity with the tech stack.
 
---

## Compliance Prototype – Performance Benchmarks

Extend the Compliance prototype acceptance criteria with explicit performance
benchmarks:

- **Performance benchmarks (MVP):**
  - Supports at least **N rows/second** of rule evaluation on a single worker
    node (exact value to be agreed with infra; starting target: 5k–10k rows/s).
  - Can process a dataset of **10M rows** within an acceptable batch window
    (e.g., ≤ 30 minutes) under typical ruleset complexity.
  - Provides basic telemetry for:
    - throughput (rows/s),
    - rule evaluation time (p95/p99),
    - failure / rejection rates.


---

## 1. DataContract CLI Integration Prototype

### 1.1 Objective

Build an integration with the **DataContract CLI** that:

- Accepts a raw contract (YAML/JSON).
- Runs `datacontract` CLI (`lint`/`validate`).
- Returns a normalized result containing:
  - `validation_status`: `VALID | INVALID | WARNING_ONLY | ERROR`
  - `issues`: list of messages with severity, path, and code.
  - `raw_output`: optional raw CLI stdout/stderr for debugging (internal only).

This will later power:

- Contract-first intake.
- UI validation on contract edits.
- CI/CD-style validations in pipelines.

### 1.2 Minimal Architecture

Two implementation options:

- **Option A – Direct subprocess calls**  
  Backend (e.g. Python/Node) directly invokes `datacontract` via `subprocess`/`child_process` on the same host/container.

- **Option B – Dedicated CLI microservice (target design)**  
  A small `cli-service` exposing an internal API:

  - `POST /cli/validate`  
    Request:
    ```json
    {
      "raw_contract": "<string>",
      "format": "yaml" // or "json"
    }
    ```
    Response:
    ```json
    {
      "validation_status": "VALID",
      "issues": [
        { "severity": "ERROR", "message": "...", "path": "$.schema.fields[0].name", "code": "..." }
      ],
      "raw_output": {
        "stdout": "...",
        "stderr": "...",
        "exit_code": 0
      }
    }
    ```

For the **prototype**, start with Option A (subprocess) and wrap it behind a simple HTTP endpoint (Option B) only if needed.

### 1.3 Normalized Output Schema

Proposed canonical structure for a validation result:

```json
{
  "validation_status": "VALID",
  "issues": [
    {
      "severity": "ERROR",
      "message": "Field 'name' is required",
      "path": "$.schema.fields[0].name",
      "code": "ODCS_MISSING_PROPERTY"
    }
  ],
  "raw_output": {
    "stdout": "...",
    "stderr": "...",
    "exit_code": 0
  }
}
```

- `severity`: `INFO | WARNING | ERROR | FATAL` (based on CLI output).
- `path`: JSONPath-like string to the problematic field.
- `code`: CLI-specific or normalized issue code.

### 1.4 Prototype Implementation (Python Subprocess)

**Core function (example):**

```python
import subprocess
import json
import tempfile
from enum import Enum

class ValidationStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    WARNING_ONLY = "WARNING_ONLY"
    ERROR = "ERROR"

def run_datacontract_validate(raw_contract: str, fmt: str = "yaml") -> dict:
    suffix = ".yaml" if fmt == "yaml" else ".json"
    with tempfile.NamedTemporaryFile(mode="w+", suffix=suffix, delete=False) as f:
        f.write(raw_contract)
        f.flush()
        path = f.name

    cmd = ["datacontract", "lint", path, "--output", "json"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
    except subprocess.TimeoutExpired:
        return {
            "validation_status": ValidationStatus.ERROR,
            "issues": [{
                "severity": "ERROR",
                "message": "Validation timed out",
                "path": None,
                "code": "CONTRACT_CLI_TIMEOUT"
            }],
            "raw_output": None
        }

    stdout = proc.stdout
    stderr = proc.stderr
    exit_code = proc.returncode

    issues = []
    try:
        cli_json = json.loads(stdout) if stdout.strip() else {}
    except json.JSONDecodeError:
        cli_json = {}
        issues.append({
            "severity": "ERROR",
            "message": "CLI returned non-JSON output",
            "path": None,
            "code": "CONTRACT_CLI_OUTPUT_INVALID"
        })

    for item in cli_json.get("issues", []):
        issues.append({
            "severity": item.get("severity", "ERROR"),
            "message": item.get("message", ""),
            "path": item.get("path"),
            "code": item.get("code", "CLI_ISSUE")
        })

    if exit_code == 0 and not [i for i in issues if i["severity"] in ("ERROR", "FATAL")]:
        status = ValidationStatus.VALID
    elif exit_code == 0 and any(i for i in issues if i["severity"] == "WARNING"):
        status = ValidationStatus.WARNING_ONLY
    elif exit_code != 0:
        status = ValidationStatus.INVALID
    else:
        status = ValidationStatus.ERROR

    return {
        "validation_status": status,
        "issues": issues,
        "raw_output": {
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code
        }
    }
```

### 1.5 Thin HTTP Wrapper (Example)

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ValidateRequest(BaseModel):
    raw_contract: str
    format: str = "yaml"

class ValidateResponse(BaseModel):
    validation_status: str
    issues: list
    raw_output: dict | None

@app.post("/cli/validate", response_model=ValidateResponse)
def validate(req: ValidateRequest):
    result = run_datacontract_validate(req.raw_contract, req.format)
    return result
```

### 1.6 Acceptance Criteria

- Given a valid example contract from ODCS/datacontract.com:
  - `validation_status = VALID` and `issues = []` (or warnings only).
- Given an intentionally broken contract:
  - `validation_status = INVALID`.
  - `issues` contain at least one `ERROR` with path and message.
- Timeouts or crashes:
  - Return `validation_status = ERROR` with meaningful issue code (`CONTRACT_CLI_TIMEOUT`, etc.), not a raw stack trace.

---

## 2. Compliance Service Prototype (Sample Data)

### 2.1 Objective

Build a **minimal compliance engine** that:

- Accepts a small CSV dataset as input.
- Detects basic PII categories per column (EMAIL, PHONE, CARD, etc.).
- Estimates a simple `risk_score`.
- Computes `allowed_to_store` based on default thresholds.
- Returns a JSON report compatible with the `compliance_runs` model.

This prototype proves:

- PII detection works in practice.
- Threshold-based policy (`allowed_to_store`) can be implemented.
- Response structure fits the planned DB and API.

### 2.2 Minimal Architecture

Single service: `compliance-service` (Python + FastAPI).

- Endpoint:
  - `POST /scan-file`
    - For prototype, accept a file upload (`multipart/form-data`).
    - Later, accept `file_id` and read from object storage.

### 2.3 Detection Logic (Prototype)

Use:

- `pandas` to load CSV.
- Regex-based classifiers on samples per column:
  - Email: `r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"`
  - Phone: `r"\+?\d[\d\- ]{7,}"`
  - Card-like: `r"\b(?:\d[ -]*?){13,16}\b"` plus optional Luhn check.
- For each column:
  - Sample up to N rows (e.g. 1000).
  - Compute `match_ratio` per category (0–1).

### 2.4 Prototype Core Logic

```python
import pandas as pd
import re
from dataclasses import dataclass

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\- ]{7,}")
CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

@dataclass
class ColumnCompliance:
    column: str
    categories: list[str]
    match_ratio: float

def classify_column(series: pd.Series) -> ColumnCompliance | None:
    non_null = series.dropna().astype(str)
    if non_null.empty:
        return None

    sample = non_null.sample(n=min(1000, len(non_null)), random_state=42)

    def ratio(regex):
        matches = sample.str.contains(regex, regex=True)
        return float(matches.mean())

    email_r = ratio(EMAIL_RE.pattern)
    phone_r = ratio(PHONE_RE.pattern)
    card_r = ratio(CARD_RE.pattern)

    categories = []
    max_ratio = 0.0

    if email_r > 0.01:
        categories.append("EMAIL")
        max_ratio = max(max_ratio, email_r)
    if phone_r > 0.01:
        categories.append("PHONE")
        max_ratio = max(max_ratio, phone_r)
    if card_r > 0.01:
        categories.append("CARD")
        max_ratio = max(max_ratio, card_r)

    if not categories:
        return None

    return ColumnCompliance(
        column=series.name,
        categories=categories,
        match_ratio=max_ratio
    )

def compute_risk_score(cols: list[ColumnCompliance]) -> float:
    weights = {
        "EMAIL": 1.0,
        "PHONE": 1.0,
        "CARD": 3.0,
    }
    score = 0.0
    for c in cols:
        for cat in c.categories:
            score += weights.get(cat, 1.0) * c.match_ratio
    return score
```

### 2.5 API Handler Example

```python
from fastapi import FastAPI, UploadFile, File

app = FastAPI()

@app.post("/scan-file")
async def scan_file(file: UploadFile = File(...)):
    df = pd.read_csv(file.file)

    col_reports = []
    for col in df.columns:
        col_result = classify_column(df[col])
        if col_result:
            col_reports.append({
                "column": col_result.column,
                "categories": col_result.categories,
                "match_ratio": col_result.match_ratio,
            })

    risk_score = compute_risk_score(
        [ColumnCompliance(**{k: v for k, v in c.items()}) for c in col_reports]
    )

    allowed_to_store = True
    for c in col_reports:
        if "CARD" in c["categories"] and c["match_ratio"] >= 0.01:
            allowed_to_store = False
            break

    return {
        "status": "SUCCEEDED",
        "regulations": ["GDPR", "LGPD"],  # stub for prototype
        "allowed_to_store": allowed_to_store,
        "pii_summary": col_reports,
        "risk_score": risk_score,
        "issues": [] if allowed_to_store else [{
            "severity": "HIGH",
            "message": "Detected card-like data; not allowed to store.",
            "code": "CARD_DATA_DETECTED"
        }]
    }
```

### 2.6 Acceptance Criteria

- Given a CSV with:
  - Only non-PII columns → `allowed_to_store = true`.
  - A column with fake card numbers in ≥1% of rows → `allowed_to_store = false`.
- Responses must:
  - Be deterministic for the same input.
  - Avoid including raw PII in `issues` or logs (only aggregated metrics).

---

## 3. Semantic Mapping Prototype (HubContract → RDF)

### 3.1 Objective

Create a **prototype semantic mapping** pipeline that:

- Takes a HubContract JSON for a single asset.
- Produces an RDF graph (e.g. Turtle or JSON-LD).
- Models at least:
  - Dataset as `dcat:Dataset`.
  - Contract as `hub:DataContract`.
  - Fields as `hub:Field` resources with name/type.
- Supports simple SPARQL queries.

This proves:

- The viability of the ontology structure.
- That URIs/IRIs are stable and queryable.
- That contracts → RDF mapping can be automated.

### 3.2 Minimal Ontology & URI Scheme

Use:

- `dcat:` (Data Catalog Vocabulary).
- `dct:` (Dublin Core Terms).
- `hub:` (custom namespace; e.g. `https://hub.example.com/ontology#`).

URI scheme (prototype):

- Asset: `https://hub.example.com/asset/{asset_id}`
- Contract: `https://hub.example.com/contract/{contract_id}`
- Field: `https://hub.example.com/asset/{asset_id}#field-{field_name}`

Classes & properties:

- `hub:DataContract`  
- `hub:Field`  
- `hub:hasContract` (Dataset → Contract)  
- `hub:field` (Dataset → Field)  
- `hub:fieldName`, `hub:fieldType`

### 3.3 Example HubContract (simplified)

```json
{
  "id": "contract-123",
  "assetId": "asset-abc",
  "info": {
    "title": "Customer Events",
    "description": "Events generated by customers in the web app"
  },
  "schema": {
    "fields": [
      { "name": "customer_id", "type": "string" },
      { "name": "event_type", "type": "string" },
      { "name": "timestamp", "type": "timestamp" }
    ]
  }
}
```

### 3.4 Mapping Implementation (Python + rdflib)

```python
from rdflib import Graph, Namespace, URIRef, Literal
from rdflib.namespace import RDF, DCTERMS

DCAT = Namespace("http://www.w3.org/ns/dcat#")
HUB = Namespace("https://hub.example.com/ontology#")

def hubcontract_to_rdf(hub_contract: dict) -> Graph:
    g = Graph()
    g.bind("dcat", DCAT)
    g.bind("dct", DCTERMS)
    g.bind("hub", HUB)

    contract_id = hub_contract["id"]
    asset_id = hub_contract["assetId"]

    asset_uri = URIRef(f"https://hub.example.com/asset/{asset_id}")
    contract_uri = URIRef(f"https://hub.example.com/contract/{contract_id}")

    # Dataset
    g.add((asset_uri, RDF.type, DCAT.Dataset))

    title = hub_contract.get("info", {}).get("title")
    desc = hub_contract.get("info", {}).get("description")

    if title:
        g.add((asset_uri, DCTERMS.title, Literal(title)))
    if desc:
        g.add((asset_uri, DCTERMS.description, Literal(desc)))

    # Contract
    g.add((contract_uri, RDF.type, HUB.DataContract))
    g.add((asset_uri, HUB.hasContract, contract_uri))

    # Fields
    for field in hub_contract.get("schema", {}).get("fields", []):
        field_name = field["name"]
        field_uri = URIRef(f"{asset_uri}#field-{field_name}")
        g.add((field_uri, RDF.type, HUB.Field))
        g.add((field_uri, HUB.fieldName, Literal(field_name)))
        if "type" in field:
            g.add((field_uri, HUB.fieldType, Literal(field["type"])))
        g.add((asset_uri, HUB.field, field_uri))

    return g
```

### 3.5 Querying the Graph

```python
q = '''
PREFIX dcat: <http://www.w3.org/ns/dcat#>
PREFIX hub: <https://hub.example.com/ontology#>
SELECT ?field ?name ?type WHERE {
  ?dataset a dcat:Dataset .
  ?dataset hub:field ?field .
  ?field hub:fieldName ?name .
  OPTIONAL { ?field hub:fieldType ?type }
}
'''
for row in g.query(q):
    print(row)
```

### 3.6 Acceptance Criteria

- Given a valid HubContract JSON:
  - RDF graph contains `dcat:Dataset` for the asset.
  - RDF graph contains `hub:DataContract` for the contract.
  - All fields appear as `hub:Field` nodes with `hub:fieldName` and `hub:fieldType`.
- SPARQL query returns all fields and their types.
- URIs are stable and deterministic from `assetId`/`contractId`.

---

## 4. Next Steps & Integration Plan

Once these prototypes are working independently:

1. **Wire DataContract CLI prototype into the main backend**:
   - Use it in `/contracts/validate` and in contract-first flow.
   - Normalize status & issues into `contracts.cli_validation_status` and `contracts.cli_output`.

2. **Wrap Compliance prototype with Job & Audit**:
   - Integrate with the `jobs` table and `compliance_runs`.
   - Enforce `allowed_to_store=false` as an intake gate for data-first/contract-first flows.

3. **Integrate Semantic mapping into asset lifecycle**:
   - Run `hubcontract_to_rdf` each time a contract becomes valid/active.
   - Store RDF in the triple store.
   - Expose `GET /semantic/assets/{id}` returning JSON-LD or Turtle.

These critical path prototypes de-risk the hardest parts of the platform (standards integration, compliance scanning, and semantic modeling) and give you concrete, working code to evolve into production services.
