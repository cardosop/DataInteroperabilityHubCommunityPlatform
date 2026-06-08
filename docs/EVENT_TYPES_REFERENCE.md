# Event Types Reference

This document catalogs all event types emitted by the Hub platform.

## Contract Events

- `contract.created` — Emitted when a new contract is created
- `contract.updated` — Emitted when a contract is updated
- `contract.deleted` — Emitted when a contract is deleted
- `contract.published` — Emitted when a contract is published
- `contract.status_changed` — Emitted when a contract status changes

## Asset Events

- `asset.created` — Emitted when a new asset is created
- `asset.updated` — Emitted when an asset is updated
- `asset.deleted` — Emitted when an asset is deleted
- `asset.activated` — Emitted when an asset is activated
- `asset.deactivated` — Emitted when an asset is deactivated

## ODPS Events

- `odps.created` — Emitted when a new ODPS document is created
- `odps.normalized` — Emitted when an ODPS document is normalized
- `odps.versioned` — Emitted when an ODPS document is versioned

## Pipeline Events

- `pipeline.started` — Emitted when a pipeline execution starts
- `pipeline.completed` — Emitted when a pipeline execution completes
- `pipeline.failed` — Emitted when a pipeline execution fails

## Workflow Events

- `workflow.started` — Emitted when a workflow instance starts
- `workflow.completed` — Emitted when a workflow instance completes
- `workflow.failed` — Emitted when a workflow instance fails

## Tenant Events

- `tenant.created` — Emitted when a new tenant is created
- `tenant.updated` — Emitted when a tenant is updated
- `tenant.suspended` — Emitted when a tenant is suspended
