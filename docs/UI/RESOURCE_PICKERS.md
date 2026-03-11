# Resource Pickers

**Last Updated**: 2026-03-08  
**Version**: 1.0.0  
**Reference**: [tasks.md 29.69](../../openspec/changes/useronboardfix/tasks.md), [RESOURCE_PICKER_LINKING_PLAN.md](../../openspec/changes/useronboardfix/RESOURCE_PICKER_LINKING_PLAN.md)

---

## Overview

Resource pickers are searchable dropdown components for selecting assets, contracts, datasets, and files. They replace manual UUID entry with a search-and-select UX, improving usability and reducing errors.

**Location**: `frontend/src/shared/components/pickers/`

**Components**:
- **Single-select**: AssetPicker, ContractPicker, DatasetPicker, FilePicker
- **Multi-select**: AssetMultiPicker, DatasetMultiPicker, FileMultiPicker

**Feature flag**: `VITE_FEATURE_RESOURCE_PICKERS_ENABLED` (default: true). When false, pickers render plain text inputs for manual UUID entry.

---

## AssetPicker

Searchable, single-select picker for choosing an asset.

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string \| null` | — | Selected asset ID (UUID) or null |
| `onChange` | `(assetId: string \| null) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select an asset...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `data-testid` | `string` | `'asset-picker'` | Test ID for E2E |

### Usage

```tsx
import { AssetPicker } from '@/shared/components/pickers';

function MyForm() {
  const [assetId, setAssetId] = useState<string | null>(null);

  return (
    <AssetPicker
      value={assetId}
      onChange={setAssetId}
      placeholder="Select target asset"
      data-testid="my-asset-picker"
    />
  );
}
```

### Where Used

- ODPSUploadPage (asset selection)
- DatasetCreatePage (asset selection)
- DatasetDetailPage (edit: link to asset)
- RetentionPolicyCreatePage/EditPage
- DQRunListPage, ComplianceRunListPage (create modal)

---

## ContractPicker

Searchable, single-select picker for choosing a contract. Optional `specType` filter for ODPS-only contracts.

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string \| null` | — | Selected contract ID (UUID) or null |
| `onChange` | `(contractId: string \| null) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select a contract...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `specType` | `string` | — | Filter by spec_type (e.g. `ODPS` for ODPS Link page) |
| `data-testid` | `string` | `'contract-picker'` | Test ID for E2E |

### Usage

```tsx
import { ContractPicker } from '@/shared/components/pickers';

function ODPSLinkForm() {
  const [contractId, setContractId] = useState<string | null>(null);

  return (
    <ContractPicker
      value={contractId}
      onChange={setContractId}
      specType="ODPS"
      placeholder="Select ODPS contract"
      data-testid="odps-link-contract-picker"
    />
  );
}
```

### Where Used

- AssetDetailPage (attach contract)
- ODPSLinkPage (Link Existing ODPS mode)
- ScheduledExportCreatePage/EditPage (contract_id)

---

## DatasetPicker

Searchable, single-select picker for choosing a dataset. Optional `assetId` for cascading (filter datasets by asset).

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string \| null` | — | Selected dataset ID (UUID) or null |
| `onChange` | `(datasetId: string \| null) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select a dataset...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `assetId` | `string \| undefined` | — | Filter by asset_id (cascading) |
| `data-testid` | `string` | `'dataset-picker'` | Test ID for E2E |

### Usage

```tsx
import { AssetPicker, DatasetPicker } from '@/shared/components/pickers';

function DQCreateForm() {
  const [assetId, setAssetId] = useState<string | null>(null);
  const [datasetId, setDatasetId] = useState<string | null>(null);

  return (
    <>
      <AssetPicker value={assetId} onChange={setAssetId} />
      <DatasetPicker
        value={datasetId}
        onChange={setDatasetId}
        assetId={assetId ?? undefined}
      />
    </>
  );
}
```

### Where Used

- AssetDetailPage (attach dataset)
- DQRunListPage, ComplianceRunListPage (create modal)
- RetentionPolicyCreatePage/EditPage

---

## FilePicker

Searchable, single-select picker for choosing a file. Optional `assetId` and `datasetId` for cascading (passed for future use; backend files API does not yet support these filters).

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string \| null` | — | Selected file ID (UUID) or null |
| `onChange` | `(fileId: string \| null) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select a file...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `assetId` | `string \| undefined` | — | Filter by asset_id (future use) |
| `datasetId` | `string \| undefined` | — | Filter by dataset_id (future use) |
| `data-testid` | `string` | `'file-picker'` | Test ID for E2E |

### Usage

```tsx
import { AssetPicker, DatasetPicker, FilePicker } from '@/shared/components/pickers';

function AccessRequestForm() {
  const [assetId, setAssetId] = useState<string | null>(null);
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [fileId, setFileId] = useState<string | null>(null);

  return (
    <>
      <AssetPicker value={assetId} onChange={setAssetId} />
      <DatasetPicker
        value={datasetId}
        onChange={setDatasetId}
        assetId={assetId ?? undefined}
      />
      <FilePicker
        value={fileId}
        onChange={setFileId}
        assetId={assetId ?? undefined}
        datasetId={datasetId ?? undefined}
      />
    </>
  );
}
```

### Where Used

- DQRunListPage, ComplianceRunListPage (create modal)
- AccessRequestCreatePage
- RetentionPolicyCreatePage/EditPage

---

## AssetMultiPicker

Searchable, multi-select picker for choosing multiple assets.
Selected items display as tags with remove buttons.

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string[]` | — | Array of selected asset IDs |
| `onChange` | `(assetIds: string[]) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select assets...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `data-testid` | `string` | `'asset-multi-picker'` | Test ID for E2E |

### Usage

```tsx
import { AssetMultiPicker } from '@/shared/components/pickers';

function ScheduledExportForm() {
  const [assetIds, setAssetIds] = useState<string[]>([]);

  return (
    <AssetMultiPicker
      value={assetIds}
      onChange={setAssetIds}
      placeholder="Select assets to export"
      data-testid="scheduled-export-asset-picker"
    />
  );
}
```

### Where Used

- ScheduledExportCreatePage/EditPage (asset_ids)

---

## DatasetMultiPicker

Searchable, multi-select picker for choosing multiple datasets.

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string[]` | — | Array of selected dataset IDs |
| `onChange` | `(datasetIds: string[]) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select datasets...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `assetId` | `string \| undefined` | — | Filter by asset_id (cascading) |
| `data-testid` | `string` | `'dataset-multi-picker'` | Test ID for E2E |

---

## FileMultiPicker

Searchable, multi-select picker for choosing multiple files.

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `value` | `string[]` | — | Array of selected file IDs |
| `onChange` | `(fileIds: string[]) => void` | — | Called when selection changes |
| `placeholder` | `string` | `'Search and select files...'` | Placeholder text |
| `disabled` | `boolean` | `false` | Disable the picker |
| `assetId` | `string \| undefined` | — | Filter by asset_id (future use) |
| `datasetId` | `string \| undefined` | — | Filter by dataset_id (future use) |
| `data-testid` | `string` | `'file-multi-picker'` | Test ID for E2E |

### Where Used

- ScheduledExportCreatePage/EditPage (dataset_ids, file_ids)

---

## Backend API

Pickers call list APIs with search, filter, and ordering:

| Endpoint | search | filter | ordering |
|----------|--------|--------|----------|
| GET /api/v1/assets/ | name, key, description | domain, status, visibility | name, key, created_at, updated_at |
| GET /api/v1/contracts/ | info.name, info.title | status, spec_type, etc. | created_at, updated_at, quality_score |
| GET /api/v1/datasets/ | file name, format | asset_id, dataset_format | created_at, updated_at, format |
| GET /api/v1/files/ | name | status | name, created_at, updated_at |

See [API_REFERENCE.md](../API_REFERENCE.md#list-api-query-parameters-resource-pickers).

---

## Accessibility

- **ARIA**: combobox, listbox, aria-expanded, aria-multiselectable (multi)
- **Keyboard**: ArrowDown/Up, Enter (select), Escape (close)
- **Labels**: aria-label on search input and options

---

## Troubleshooting

See [docs/runbooks/RESOURCE_PICKER_TROUBLESHOOTING.md](../runbooks/RESOURCE_PICKER_TROUBLESHOOTING.md).

---

## Related

- [docs/API_REFERENCE.md](../API_REFERENCE.md) — List API params
- [docs/runbooks/RESOURCE_PICKER_TROUBLESHOOTING.md](../runbooks/RESOURCE_PICKER_TROUBLESHOOTING.md)
- [scripts/run_resource_picker_tests.sh](../../scripts/run_resource_picker_tests.sh)
