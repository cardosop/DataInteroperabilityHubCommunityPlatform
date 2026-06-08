# API Endpoints Reference

Complete reference of all API endpoints with usage examples.

## Compliance Endpoints

### List Compliance Runs
```bash
curl -X GET "/api/v1/compliance/runs/" -H "Authorization: Bearer $TOKEN"
```

### Get Compliance Run
```bash
curl -X GET "/api/v1/compliance/runs/{id}/" -H "Authorization: Bearer $TOKEN"
```

### Get Compliance Run Results
```bash
curl -X GET "/api/v1/compliance/runs/{id}/results/" -H "Authorization: Bearer $TOKEN"
```

## DQ Endpoints

### List DQ Runs
```bash
curl -X GET "/api/v1/dq/runs/" -H "Authorization: Bearer $TOKEN"
```

### Get DQ Run
```bash
curl -X GET "/api/v1/dq/runs/{id}/" -H "Authorization: Bearer $TOKEN"
```

### Get DQ Run Results
```bash
curl -X GET "/api/v1/dq/runs/{id}/results/" -H "Authorization: Bearer $TOKEN"
```

## Authentication
All endpoints require a valid JWT bearer token except for the version discovery (`GET /api/v1/`) and OpenAPI schema endpoints.
