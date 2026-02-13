# [API Name] API Reference

**Version**: [API Version]  
**Last Updated**: [Date]  
**Owner**: [Team/Individual]  
**Status**: [Draft/Review/Approved]

## Overview

[API purpose, scope, and key features.]

## Base URL

```
https://api.example.com/v1
```

## Authentication

[Describe authentication requirements.]

### Authentication Methods
- **API Key**: [How to use API keys]
- **OAuth 2.0**: [How to use OAuth]
- **Bearer Token**: [How to use bearer tokens]

## Rate Limiting

[Describe rate limiting policies.]

- **Rate Limit**: [e.g., 1000 requests per hour]
- **Rate Limit Headers**: [Headers returned]

## Endpoints

### [Endpoint Name]

**Method**: `GET|POST|PUT|DELETE|PATCH`  
**Path**: `/api/v1/endpoint`  
**Description**: [Endpoint description]

**Authentication**: Required/Optional

**Request Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| param1 | string | Yes | Parameter description |
| param2 | integer | No | Parameter description |

**Request Body** (if applicable):
```json
{
  "field1": "value1",
  "field2": "value2"
}
```

**Response**:

**Success (200 OK)**:
```json
{
  "data": {
    "id": "123",
    "name": "Example"
  }
}
```

**Error (400 Bad Request)**:
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Error message",
    "details": {}
  }
}
```

**ODPS Integration**: [If applicable, describe ODPS-related endpoints and how they work with ODPS data products.]

## Error Handling

### Error Response Format

All errors follow this format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "Additional error details"
    }
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| INVALID_REQUEST | 400 | Request is invalid |
| UNAUTHORIZED | 401 | Authentication required |
| FORBIDDEN | 403 | Insufficient permissions |
| NOT_FOUND | 404 | Resource not found |
| INTERNAL_ERROR | 500 | Internal server error |

## Examples

### Example 1: [Use Case Name]

**Request**:
```bash
curl -X GET "https://api.example.com/v1/endpoint" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Response**:
```json
{
  "data": {
    "result": "success"
  }
}
```

### Example 2: [Use Case Name]

[Another example]

## SDK Usage

[If applicable, show how to use the API with SDKs.]

### Python
```python
from sdk import Client

client = Client(api_key="YOUR_KEY")
result = client.get_endpoint()
```

### JavaScript
```javascript
const client = new Client({ apiKey: 'YOUR_KEY' });
const result = await client.getEndpoint();
```

## Webhooks

[If applicable, describe webhook integration.]

## References

- [API Standards](../API_STANDARDS.md)
- [Error Codes](../API_ERROR_CODES.md)
- [Related Documentation](./path/to/doc.md)
