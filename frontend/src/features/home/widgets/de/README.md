# Data Engineer Widgets

**Persona:** DE (DATA_PROVIDER or TENANT_ADMIN role)
**Label:** "Data Engineer"

## Widget specs

### Ingestion Status Card
- **Data source:** `useJobs({ job_type: 'INGESTION', page_size: 5, ordering: '-created_at' })`
- **Display:** Latest 5 ingestion jobs with status badges (SUCCESS / FAILED / RUNNING)
- **Empty state:** "No ingestion jobs yet. Upload a file to get started."
- **Link:** `/jobs?job_type=INGESTION`

### Contract Health Card
- **Data source:** `useAssets({ status: 'DRAFT', page_size: 1 })` for draft count + contract attachment rate
- **Display:** "N of M assets have data contracts attached"
- **Link:** `/assets?status=DRAFT`

### Pipeline Health Card
- **Data source:** `useJobs({ page_size: 1 })` for recent failure count
- **Display:** "N recent job failures" (red if >0, green if 0)
- **Link:** `/jobs?status=FAILED`

### Quick action
- **"Upload Data"** → `/assets/create`
- **"New Ingestion Schedule"** → `/ingestion/create`
