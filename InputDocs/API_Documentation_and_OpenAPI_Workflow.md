# API Documentation & OpenAPI Workflow

This document defines how API documentation is **produced, maintained, and published**
for the Interoperable Data Hub (IDH), including:

- OpenAPI spec maintenance workflow.
- Documentation site build & deployment.
- Example request/response coverage.
- SDK documentation generation from shared sources.

This content fulfills the “API documentation generation” requirement (tracking item 13.2).

---

## 1. OpenAPI spec maintenance workflow

### 1.1 Source of truth

- The **canonical source of truth** for the public HTTP API is a versioned OpenAPI
  document in the main repo, for example:

  - `openapi/v1/openapi.v1.yaml` (or `.json`).

- `API_Spec_v1.md` remains the **human-readable contract overview** and should be
  consistent with the OpenAPI document. The OpenAPI file is the machine-readable
  source for:

  - Documentation site generation.
  - SDK code generation (if used).
  - Mock servers and contract tests.

- All `/api/v1` endpoints exposed in production MUST appear in:

  - `API_Spec_v1.md`
  - `openapi.v1.yaml`

with consistent paths, parameters, request/response bodies, and error envelopes.

### 1.2 Change process

Any change to the HTTP API (new endpoint, new field, breaking change) follows this
workflow:

1. **Design & discussion**
   - Propose the change in an ADR or design doc.
   - Update `API_Spec_v1.md` to reflect the intended contract.

2. **Update OpenAPI spec**
   - Edit `openapi/v1/openapi.v1.yaml` to add/modify:
     - Paths, operations, parameters.
     - Request/response schemas.
     - Error responses (using the standard error envelope).
     - Examples (see §3).

3. **Validation in CI**
   - CI MUST:
     - Validate syntax (`openapi`/`swagger` validators).
     - Lint for style/consistency (naming, descriptions, tags).
     - Optionally run contract tests against a test instance.

4. **Review & approval**
   - Every OpenAPI change MUST be reviewed by:
     - At least one API owner/maintainer.
     - Optionally an SDK/DevEx owner if it affects SDKs.
   - PR must include:
     - Summary of changes.
     - Impact on backward compatibility.
     - Links to updated examples and SDK docs if relevant.

5. **Versioning**
   - All changes to `/api/v1` must be **backward compatible**, except where
     explicitly allowed by the versioning policy.
   - For breaking changes:
     - Introduce new endpoints/fields alongside old ones.
     - Mark deprecated elements in OpenAPI (e.g. `deprecated: true`).
     - Plan migration and deprecation window as per API versioning strategy.

### 1.3 Tooling

- The repo includes scripts to:
  - `validate-openapi` – run validation & linting.
  - `bundle-openapi` – produce a bundled, single-file spec for docs and SDKs.
- These scripts MUST run in CI and block merges on failure.

---

## 2. Documentation site deployment

### 2.1 Static documentation site

- The public API docs are served as a **static site** generated from the OpenAPI
  spec using a standard tool (e.g., ReDoc, Redocly, Swagger UI, or similar).
- The build pipeline:
  1. Take `openapi.v1.yaml` from the main branch.
  2. Run docs generator (e.g., `redoc-cli bundle`).
  3. Produce static assets (HTML/CSS/JS) ready for hosting.

### 2.2 Environments & URLs

- At minimum, two documentation environments:

  - **Staging docs**:
    - Built from the staging branch or pre-release tag.
    - Used to validate upcoming changes.
  - **Production docs**:
    - Built from main / release branch.
    - Reflects the current production API.

- Typical URLs (examples):

  - Staging: `https://docs-staging.hub.example.com`
  - Production: `https://docs.hub.example.com`

- The OpenAPI `servers` section MUST clearly indicate base URLs per environment
  (`/api/v1`).

### 2.3 CI/CD pipeline

- A dedicated CI pipeline:

  - Watches for changes to:
    - `openapi/v1/openapi.v1.yaml`
    - `API_Spec_v1.md` (optionally).
  - On merge to `main`:
    - Builds docs.
    - Deploys them to the production docs site.
  - On merge to staging branch:
    - Builds and deploys to staging docs.

- The pipeline SHOULD:
  - Invalidate CDN caches where applicable.
  - Tag deployed versions (e.g., `docs-YYYYMMDD-HHMM`).

---

## 3. Example request/response coverage

Each API endpoint MUST have **example requests and responses** in the OpenAPI spec.

### 3.1 Requirements per endpoint

For every operation (`GET /assets`, `POST /dq-runs`, etc.):

- At least one **example request**:
  - Example path parameters.
  - Example query parameters.
  - Example JSON request body (if applicable).
- At least one **example success response**:
  - Example JSON body for 2xx response (e.g., 200, 201).
- Recommended: an **example error response**:
  - Using the standard error envelope (`code`, `message`, `details`, `request_id`).

Examples SHOULD be provided via:

- Standard OpenAPI `example` or `examples` fields, and/or
- Vendor extensions (e.g. `x-codeSamples`) for language-specific snippets.

### 3.2 Example style & consistency

- Examples MUST be:
  - Realistic but synthetic (no actual tenant data).
  - Consistent with:
    - Data model (`Domain_Model.md`),
    - Status enums and error codes.
- For resources with relationships (assets, datasets, jobs), examples should show
  the **minimum useful set** of fields to make them understandable.

### 3.3 Generation of snippets

The documentation site MUST expose:

- Example `curl` commands for each endpoint.
- Optionally, code samples for:
  - JavaScript/TypeScript SDK usage.
  - Python SDK usage.

These may be:

- Hand-authored using `x-codeSamples`, or
- Generated from shared templates that use the OpenAPI spec as input.

---

## 4. SDK documentation generation

SDK documentation MUST be consistent with the API and generated from shared
sources where possible.

### 4.1 API reference vs. guides

Each SDK (JS/TS and Python) MUST provide:

1. **API reference docs**:
   - Methods, parameters, return types.
   - Error types (see SDK error handling spec).
2. **Guides / how-tos**:
   - “Getting started” guides.
   - End-to-end flows:
     - Data-first intake.
     - Contract-first intake.
     - Scan-only DQ/compliance.
     - Marketplace access and entitlements.

### 4.2 JS/TS SDK docs

- Generated using a tool such as **TypeDoc** from TSDoc-annotated source.
- The doc build MUST:
  - Run in CI for each SDK release.
  - Publish HTML or markdown output to:
    - The main docs site under `/sdk/js/`, or
    - A dedicated SDK docs host.

- The JS SDK reference should link back to the corresponding API endpoints where
  relevant (e.g., `client.assets.getAsset` → `GET /assets/{id}` in API docs).

### 4.3 Python SDK docs

- Generated using **Sphinx** (or pdoc / mkdocs+autodoc) from docstring-annotated
  source.
- Similar requirements to JS:
  - Built in CI on each SDK release.
  - Published to `/sdk/python/` paths or equivalent.

### 4.4 OpenAPI-driven generation

Where feasible:

- Use the OpenAPI spec to:
  - Generate baseline client code or models (even if hand-edited later).
  - Generate endpoint/parameter tables in SDK docs.
- Ensure that:
  - Changes to `openapi.v1.yaml` are reflected in:
    - SDK method signatures.
    - SDK docs (e.g., via regenerated markdown or type definitions).

### 4.5 Version alignment

- Each SDK release MUST document:
  - The **API version** it targets (e.g., `/api/v1`).
  - Any known discrepancies or experimental endpoints.
- Docs site SHOULD provide:
  - SDK version selector (if multiple major versions are maintained).
  - Clear mapping from API versions → supported SDK versions.

---

With this workflow:

- The OpenAPI spec is the single machine-readable source of truth.
- Documentation sites are automatically built and deployed from that spec.
- Each endpoint has concrete, realistic request/response examples.
- SDK docs stay aligned with the API via shared artifacts and CI enforcement.
