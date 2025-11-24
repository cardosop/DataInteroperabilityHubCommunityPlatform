# API Contract-First Workflow (MVP)

This document describes how the Interoperable Data Hub designs, validates, and
ships **HTTP APIs using an OpenAPI-first (contract-first)** approach.

The high-level flow is:

1. Capture requirements and design the API at the **contract level**.
2. Author and review an **OpenAPI** specification as the single source of truth.
3. Validate the spec in **CI/CD** (syntax, style, compatibility).
4. Generate **SDKs and wrappers** from the spec.
5. Implement services **behind** the contract using a **wrapper / adapter
   pattern**.
6. Version and evolve the API in a controlled way, handling breaking changes
   explicitly. 

## OpenAPI Version for MVP

The Interoperable Data Hub **standardizes on OpenAPI 3.1.0 for MVP**.

- All public REST APIs MUST be described using **OpenAPI 3.1.0**.
- New endpoints MUST NOT introduce additional OpenAPI versions in MVP
  (e.g. 3.0.3) unless there is a documented tooling constraint.
- If a specific tool only supports 3.0.x:
  - we either:
    - generate a **derived 3.0.x artifact** from the canonical 3.1.0 spec, or
    - document an explicit exception in the technical design,
  - but the **source of truth** remains the 3.1.0 specification checked into
    the repo.

The canonical spec file for API v1 SHOULD be named:

- `api/openapi-hub-v1.yaml` with `openapi: 3.1.0` at the top.

All CI validation, SDK generation, and documentation publishing MUST use this
canonical spec as their input.


---

## 1. Principles

- **Contract-first.** The OpenAPI file is the source of truth for public
  behaviour of the API (paths, payloads, error codes).
- **Automation-friendly.** Everything that can be automated (linting,
  compatibility checks, SDK generation) should be.
- **Backward compatibility by default.** Day-to-day changes are additive; breaking
  changes are rare, explicit, and versioned.
- **Language agnostic.** Clients in different languages (TypeScript, Python,
  Java, etc.) are generated from the same spec.
- **Separation of concerns.** Business logic and storage are insulated behind
  adapters/wrappers that conform to the generated interfaces.

---

## 2. End-to-End Workflow

### 2.1 Capture requirements

- Start from use cases and domain language in the **Domain Model** and
  **MVP Scope** documents.
- Identify:
  - resources (e.g. contracts, assets, rules),
  - operations (e.g. create, list, validate),
  - error scenarios and constraints.

Output: a rough sketch of endpoints and payloads in plain language.

### 2.2 Author the OpenAPI spec

- Create or update `api/openapi.yaml` (or `openapi-v1.yaml`).
- Use a contract-first tool (e.g. VS Code extension, `openapi-cli`, Redocly)
  to edit the spec.
- For each endpoint:
  - Define path, method, tags, summary/description.
  - Define request bodies and parameters.
  - Define response codes and schemas (including error shapes).
  - Reuse shared components (`components.schemas.*`) where possible.

The spec must be human-readable and machine-validated.

### 2.3 Review & approval

- OpenAPI changes are proposed via **pull requests**.
- Reviewers check:
  - Semantics (does this match the domain model and requirements?)
  - Naming, consistency, and documentation.
  - Backward compatibility (will this break current clients?)
- No implementation work starts until the contract is agreed and merged.

### 2.4 Generate SDKs & client stubs

Once the spec is merged:

- Use OpenAPI generators to produce:
  - HTTP client SDKs (e.g. TypeScript, Python).
  - Server stubs where helpful (optional).
- **Tools**: `openapi-generator-cli` (Node.js) or `openapi-python-client` (Python)
- Generated code lives in dedicated packages / modules, not edited by hand.
- The generated SDKs are versioned and published in lockstep with the API
  version (e.g. `hub-api-client-js@1.x` for `/api/hub/v1`).
- See `Technology_Stack_Decisions.md` for specific tool versions and configuration.

Example (pseudo) command:

```bash
openapi-generator-cli generate   -i api/openapi-v1.yaml   -g typescript-fetch   -o clients/typescript
```

### 2.5 Implement the service (wrapper pattern)

- Service implementations **wrap** the generated interfaces rather than
  manually parsing HTTP requests everywhere.
- Preferred pattern:
  - Use a **thin HTTP layer** (framework routes) that delegates to generated
    request/response types.
  - Implement business logic in **use-case services** that accept/return
    domain objects.
  - Provide **adapters** between domain objects and OpenAPI DTOs.

Benefits:

- OpenAPI keeps HTTP surface stable even as internal models evolve.
- Most changes to the spec are visible and reviewed before any code is touched.

---

## 3. Tooling Recommendations

The following tools are recommended (non-binding for the MVP, but illustrative):

- **Editing & linting**
  - `@redocly/cli` (linting, bundling)
  - `openapi-cli`, `swagger-cli`, or similar
  - OpenAPI VS Code extensions for schema-aware editing
- **Documentation**
  - Redoc / Swagger UI for interactive docs published from the spec
- **Generation**
  - `openapi-generator-cli` or `swagger-codegen` for SDKs & server stubs

These tools are wired into **CI/CD**, not just run locally.

---

## 4. OpenAPI Validation in CI/CD

Every change to the API contract MUST be validated automatically in CI/CD before
it is merged or deployed.

### 4.1 Validation steps

For each change to the OpenAPI spec:

- **Syntax & schema validation**
  - Run `openapi-cli` / `@redocly/cli` / `swagger-cli` (or equivalent)
    to verify the spec is structurally valid.
- **Style & consistency checks**
  - Enforce naming conventions (paths, operations, schemas).
  - Ensure descriptions and tags are present for public operations.
- **Backward-compatibility checks**
  - Compare the updated spec against the last released version.
  - Fail the build if a breaking change is detected and not explicitly flagged
    as a new major version (see “Handling Breaking Changes” section).

### 4.2 Example (GitHub Actions-style pseudo config)

```yaml
jobs:
  api-contract-validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install OpenAPI tools
        run: |
          npm install -g @redocly/cli

      - name: Lint & validate OpenAPI
        run: |
          redocly lint api/openapi-v1.yaml

      - name: Backward-compatibility check
        run: |
          ./scripts/check-openapi-breaking.sh             api/openapi-v1-prev.yaml             api/openapi-v1.yaml
```

> **Rule of thumb:** No contract change gets merged without passing these checks.
> The OpenAPI file is treated as the single source of truth for the public API.

---

## 5. API Versioning Strategy

The platform follows a **major-version-in-path** strategy for public APIs, with
minor changes managed via backward-compatible updates.

### 5.1 Version placement

- Base path pattern:

  - `/api/hub/v1/...`
  - `/api/hub/v2/...` (future major)

- Within a major version:
  - Only **backward-compatible** changes are allowed (see next section).
  - No breaking change is introduced without bumping the major version.

### 5.2 When to create v2

Create a new major version (e.g. `v1 → v2`) when at least one of the following
is required:

- Removing or renaming existing fields in request/response bodies.
- Changing response codes in a way that breaks existing client expectations.
- Changing semantics of fields in a non-compatible way.
- Removing or renaming stable endpoints.

### 5.3 Coexistence & deprecation

- At least two adjacent major versions (e.g. `v1` and `v2`) SHOULD coexist for
  a defined **deprecation window** (e.g. 6–12 months).
- During that time:
  - Both specs are published (`openapi-v1.yaml`, `openapi-v2.yaml`).
  - Both are validated and tested in CI/CD.
  - SDKs/wrappers for both versions are generated and maintained.

- After the deprecation window:
  - `v1` is removed from documentation and SDK generation.
  - `v1` endpoints may return a clear error indicating they are retired.

---

## 6. Handling Breaking Changes in OpenAPI

Breaking changes must be **explicit**, **intentional**, and accompanied by a
migration path for existing clients.

### 6.1 What counts as breaking?

Typical breaking changes include:

- Removing an endpoint or changing its path.
- Changing HTTP method (e.g. `GET` → `POST`).
- Removing or renaming required request fields.
- Tightening validation (e.g. shrinking allowed enum values).
- Changing response shape in a way that existing clients cannot deserialize.

Non-breaking (compatible) examples:

- Adding new optional fields.
- Adding new endpoints.
- Relaxing validation (e.g. expanding allowed enum values).
- Adding new response codes that are clearly optional / additive.

### 6.2 Process for a breaking change

When a breaking change is needed:

1. **Introduce a new major version**
   - Copy the OpenAPI spec to `openapi-v2.yaml`.
   - Apply the breaking changes only to the new version (`/api/hub/v2/...`).

2. **Update tooling & wrappers**
   - Generate new SDKs / wrappers from `openapi-v2.yaml`.
   - Keep `v1` SDKs available but mark them as deprecated.

3. **Run compatibility checks**
   - CI MUST:
     - Treat changes in `openapi-v1.yaml` as breaking errors (disallowed).
     - Allow breaking changes only in the new `openapi-v2.yaml` file.

4. **Communicate & document migration**
   - Document changes between `v1` and `v2` (changelogs, migration guides).
   - Provide examples that show how to move from v1 wrappers/SDKs to v2.

5. **Plan deprecation**
   - Set a clear timeline for when `v1` will be retired.
   - Track key consumers and support them through the migration.

### 6.3 CI enforcement

- PRs that **modify the current GA spec** (`openapi-v1.yaml`) and introduce a
  breaking change MUST fail unless:
  - the change is reworked to be backward-compatible, or
  - the change is moved into a new major spec (e.g. `openapi-v2.yaml`).

> **Goal:** breaking changes are rare, visible, and controlled. Most day-to-day
> evolution happens via additive, backward-compatible OpenAPI changes.

---

## 7. Wrapper Pattern – Summary

- Treat the OpenAPI spec as the **public surface**.
- Generate **typed clients** and (optionally) server stubs from the spec.
- Implement business logic in internal services/adapters that are:
  - unit-testable without HTTP,
  - stable even as external contracts evolve,
  - reusable across multiple API surfaces if needed.

This pattern keeps contract evolution and internal implementation loosely
coupled, making it easier to adopt the versioning and compatibility rules
described above.
