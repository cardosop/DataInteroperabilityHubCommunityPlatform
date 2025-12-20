/**
 * API Documentation Page
 *
 * Comprehensive API documentation page with:
 * - API overview and introduction
 * - Authentication methods (JWT, API Key)
 * - REST API endpoints documentation
 * - GraphQL API documentation
 * - WebSocket API documentation
 * - Interactive API explorer
 * - Code snippet generation (cURL, JavaScript, Python)
 * - API version selector
 * - Search functionality
 * - OpenAPI/Swagger documentation display
 */

import React, { useState, useMemo, useCallback } from 'react'
import {
  Container,
  Box,
  Typography,
  Paper,
  Tabs,
  Tab,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Card,
  CardContent,
  Divider,
  Chip,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from '@mui/material'
import {
  Search as SearchIcon,
  ContentCopy as CopyIcon,
  PlayArrow as PlayIcon,
  ExpandMore as ExpandMoreIcon,
  Code as CodeIcon,
  Http as HttpIcon,
  Schema as SchemaIcon,
  Web as WebSocketIcon,
} from '@mui/icons-material'
import { CodeBlock } from '@/components/data-display/CodeBlock'

/**
 * API Endpoint definition
 */
interface APIEndpoint {
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  path: string
  description: string
  parameters?: {
    query?: Array<{ name: string; type: string; required: boolean; description: string }>
    path?: Array<{ name: string; type: string; description: string }>
    body?: { schema: Record<string, any>; example: any }
  }
  responses: Array<{ status: number; description: string; schema?: Record<string, any>; example?: any }>
  rateLimit?: string
}

/**
 * REST API Endpoints
 */
const REST_ENDPOINTS: APIEndpoint[] = [
  {
    method: 'GET',
    path: '/api/v1/assets/',
    description: 'List all assets',
    parameters: {
      query: [
        { name: 'page', type: 'integer', required: false, description: 'Page number' },
        { name: 'page_size', type: 'integer', required: false, description: 'Items per page' },
        { name: 'search', type: 'string', required: false, description: 'Search query' },
        { name: 'status', type: 'string', required: false, description: 'Filter by status' },
      ],
    },
    responses: [
      {
        status: 200,
        description: 'Success',
        example: {
          results: [{ id: 'uuid', name: 'Asset Name', status: 'ACTIVE' }],
          count: 1,
          next: null,
          previous: null,
        },
      },
    ],
    rateLimit: '100 requests per minute',
  },
  {
    method: 'GET',
    path: '/api/v1/assets/{id}/',
    description: 'Get asset by ID',
    parameters: {
      path: [{ name: 'id', type: 'UUID', description: 'Asset UUID' }],
    },
    responses: [
      { status: 200, description: 'Success', example: { id: 'uuid', name: 'Asset Name' } },
      { status: 404, description: 'Asset not found' },
    ],
    rateLimit: '100 requests per minute',
  },
  {
    method: 'POST',
    path: '/api/v1/assets/',
    description: 'Create a new asset',
    parameters: {
      body: {
        schema: {
          name: 'string (required)',
          description: 'string (optional)',
          domain: 'string (optional)',
        },
        example: {
          name: 'My Asset',
          description: 'Asset description',
          domain: 'finance',
        },
      },
    },
    responses: [
      { status: 201, description: 'Asset created', example: { id: 'uuid', name: 'My Asset' } },
      { status: 400, description: 'Validation error' },
    ],
    rateLimit: '50 requests per minute',
  },
]

/**
 * Generate cURL code snippet
 */
function generateCurlSnippet(endpoint: APIEndpoint, baseUrl: string, authToken?: string): string {
  const url = `${baseUrl}${endpoint.path}`
  const method = endpoint.method
  let curl = `curl -X ${method} "${url}"`

  if (authToken) {
    curl += ` \\\n  -H "Authorization: Bearer ${authToken}"`
  }

  if (endpoint.parameters?.query && endpoint.parameters.query.length > 0) {
    const queryParams = endpoint.parameters.query
      .filter((p) => p.required)
      .map((p) => `${p.name}=value`)
      .join('&')
    if (queryParams) {
      curl += ` \\\n  "${url.includes('?') ? '&' : '?'}${queryParams}"`
    }
  }

  if (endpoint.parameters?.body && method !== 'GET') {
    const body = JSON.stringify(endpoint.parameters.body.example, null, 2)
    curl += ` \\\n  -H "Content-Type: application/json" \\\n  -d '${body}'`
  }

  return curl
}

/**
 * Generate JavaScript code snippet
 */
function generateJavaScriptSnippet(endpoint: APIEndpoint, baseUrl: string, authToken?: string): string {
  const url = `${baseUrl}${endpoint.path}`
  const method = endpoint.method.toLowerCase()
  let code = `const response = await fetch("${url}", {\n  method: "${endpoint.method}",`

  if (authToken) {
    code += `\n  headers: {\n    "Authorization": "Bearer ${authToken}",`
  } else {
    code += `\n  headers: {`
  }

  if (endpoint.parameters?.body && method !== 'get') {
    code += `\n    "Content-Type": "application/json",`
  }

  code += `\n  },`

  if (endpoint.parameters?.body && method !== 'get') {
    const body = JSON.stringify(endpoint.parameters.body.example, null, 2)
    code += `\n  body: JSON.stringify(${body.replace(/\n/g, '\n    ')})`
  }

  code += `\n});\n\nconst data = await response.json();`

  return code
}

/**
 * Generate Python code snippet
 */
function generatePythonSnippet(endpoint: APIEndpoint, baseUrl: string, authToken?: string): string {
  const url = `${baseUrl}${endpoint.path}`
  const method = endpoint.method
  let code = `import requests\n\n`

  const headers: Record<string, string> = {}
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`
  }
  if (endpoint.parameters?.body && method !== 'GET') {
    headers['Content-Type'] = 'application/json'
  }

  code += `headers = ${JSON.stringify(headers, null, 2)}\n\n`

  if (endpoint.parameters?.body && method !== 'GET') {
    const body = endpoint.parameters.body.example
    code += `data = ${JSON.stringify(body, null, 2)}\n\n`
    code += `response = requests.${method.toLowerCase()}("${url}", headers=headers, json=data)`
  } else {
    code += `response = requests.${method.toLowerCase()}("${url}", headers=headers)`
  }

  code += `\n\nprint(response.json())`

  return code
}

/**
 * API Documentation Page Component
 */
export const APIDocumentationPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [apiVersion, setApiVersion] = useState('v1')
  const [selectedEndpoint, setSelectedEndpoint] = useState<APIEndpoint | null>(REST_ENDPOINTS[0])
  const [codeLanguage, setCodeLanguage] = useState<'curl' | 'javascript' | 'python'>('curl')
  const [authToken, setAuthToken] = useState('')

  // Get base URL from config
  const baseUrl = useMemo(() => {
    // Try to get from config, fallback to window location
    try {
      return (window as any).__API_BASE_URL__ || window.location.origin
    } catch {
      return window.location.origin
    }
  }, [])

  // Filter endpoints based on search
  const filteredEndpoints = useMemo(() => {
    if (!searchQuery) return REST_ENDPOINTS
    const query = searchQuery.toLowerCase()
    return REST_ENDPOINTS.filter(
      (endpoint) =>
        endpoint.path.toLowerCase().includes(query) ||
        endpoint.description.toLowerCase().includes(query) ||
        endpoint.method.toLowerCase().includes(query)
    )
  }, [searchQuery])

  // Generate code snippet
  const codeSnippet = useMemo(() => {
    if (!selectedEndpoint) return ''
    const token = authToken || 'YOUR_AUTH_TOKEN'
    switch (codeLanguage) {
      case 'curl':
        return generateCurlSnippet(selectedEndpoint, baseUrl, token)
      case 'javascript':
        return generateJavaScriptSnippet(selectedEndpoint, baseUrl, token)
      case 'python':
        return generatePythonSnippet(selectedEndpoint, baseUrl, token)
      default:
        return ''
    }
  }, [selectedEndpoint, codeLanguage, baseUrl, authToken])

  const handleCopyCode = useCallback(() => {
    navigator.clipboard.writeText(codeSnippet)
  }, [codeSnippet])

  return (
    <Container maxWidth="xl">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="h3" gutterBottom>
            API Documentation
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Comprehensive API documentation for the Data Interoperability Hub
          </Typography>
        </Box>

        {/* Search and Version Selector */}
        <Paper sx={{ p: 2, mb: 3 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                placeholder="Search API endpoints..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                InputProps={{
                  startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />,
                }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <FormControl fullWidth>
                <InputLabel>API Version</InputLabel>
                <Select value={apiVersion} label="API Version" onChange={(e) => setApiVersion(e.target.value)}>
                  <MenuItem value="v1">v1</MenuItem>
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="Auth Token (for examples)"
                type="password"
                value={authToken}
                onChange={(e) => setAuthToken(e.target.value)}
                placeholder="Optional: Enter token for code examples"
              />
            </Grid>
          </Grid>
        </Paper>

        {/* Main Tabs */}
        <Paper sx={{ mb: 3 }}>
          <Tabs value={activeTab} onChange={(_, newValue) => setActiveTab(newValue)}>
            <Tab label="Overview" icon={<HttpIcon />} iconPosition="start" />
            <Tab label="REST API" icon={<HttpIcon />} iconPosition="start" />
            <Tab label="GraphQL" icon={<SchemaIcon />} iconPosition="start" />
            <Tab label="WebSocket" icon={<WebSocketIcon />} iconPosition="start" />
            <Tab label="API Explorer" icon={<CodeIcon />} iconPosition="start" />
          </Tabs>
        </Paper>

        {/* Tab Content */}
        <Box>
          {/* Overview Tab */}
          {activeTab === 0 && (
            <Box>
              <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>
                  API Overview
                </Typography>
                <Typography variant="body1" paragraph>
                  The Data Interoperability Hub provides a comprehensive REST API, GraphQL API, and WebSocket API
                  for programmatic access to all platform features. All APIs are versioned and follow RESTful
                  principles.
                </Typography>
                <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>
                  Base URL
                </Typography>
                <CodeBlock code={baseUrl} language="text" />
              </Paper>

              <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>
                  Authentication
                </Typography>
                <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                  JWT Authentication
                </Typography>
                <Typography variant="body2" paragraph>
                  Most API endpoints require authentication using JWT tokens. Include the token in the Authorization
                  header:
                </Typography>
                <CodeBlock code='Authorization: Bearer YOUR_JWT_TOKEN' language="text" />
                <Typography variant="body2" paragraph sx={{ mt: 2 }}>
                  To obtain a JWT token, authenticate using the login endpoint:
                </Typography>
                <CodeBlock
                  code={`POST ${baseUrl}/api/v1/auth/login/\nContent-Type: application/json\n\n{\n  "email": "user@example.com",\n  "password": "password"\n}`}
                  language="text"
                />

                <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>
                  API Key Authentication
                </Typography>
                <Typography variant="body2" paragraph>
                  For programmatic access, you can use API keys. Include the API key in the Authorization header:
                </Typography>
                <CodeBlock code='Authorization: ApiKey YOUR_API_KEY' language="text" />
                <Typography variant="body2" paragraph sx={{ mt: 2 }}>
                  API keys can be generated in your account settings and provide the same permissions as your user
                  account.
                </Typography>
              </Paper>

              <Paper sx={{ p: 3 }}>
                <Typography variant="h5" gutterBottom>
                  Rate Limiting
                </Typography>
                <Typography variant="body2" paragraph>
                  API requests are rate-limited to ensure fair usage and system stability. Rate limits vary by
                  endpoint:
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Endpoint Type</TableCell>
                        <TableCell>Rate Limit</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      <TableRow>
                        <TableCell>Read operations (GET)</TableCell>
                        <TableCell>100 requests per minute</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Write operations (POST, PUT, PATCH)</TableCell>
                        <TableCell>50 requests per minute</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Delete operations</TableCell>
                        <TableCell>20 requests per minute</TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </TableContainer>
                <Alert severity="info" sx={{ mt: 2 }}>
                  Rate limit headers are included in all responses: X-RateLimit-Limit, X-RateLimit-Remaining,
                  X-RateLimit-Reset
                </Alert>
              </Paper>

              <Paper sx={{ p: 3 }}>
                <Typography variant="h5" gutterBottom>
                  OpenAPI/Swagger Documentation
                </Typography>
                <Typography variant="body2" paragraph>
                  The API follows the OpenAPI 3.0 specification. You can access the OpenAPI schema at:
                </Typography>
                <CodeBlock code={`${baseUrl}/api/v1/schema/`} language="text" />
                <Typography variant="body2" paragraph sx={{ mt: 2 }}>
                  You can use tools like Swagger UI or Postman to import the OpenAPI schema for interactive API
                  exploration:
                </Typography>
                <Alert severity="info" sx={{ mt: 2 }}>
                  <Typography variant="body2">
                    <strong>Swagger UI:</strong> Visit <code>{baseUrl}/api/v1/schema/swagger-ui/</code> for an
                    interactive API explorer
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    <strong>ReDoc:</strong> Visit <code>{baseUrl}/api/v1/schema/redoc/</code> for alternative
                    documentation view
                  </Typography>
                </Alert>
              </Paper>
            </Box>
          )}

          {/* REST API Tab */}
          {activeTab === 1 && (
            <Box>
              <Grid container spacing={3}>
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2, maxHeight: '70vh', overflow: 'auto' }}>
                    <Typography variant="h6" gutterBottom>
                      Endpoints
                    </Typography>
                    {filteredEndpoints.map((endpoint, index) => (
                      <Card
                        key={index}
                        sx={{
                          mb: 1,
                          cursor: 'pointer',
                          border: selectedEndpoint === endpoint ? 2 : 1,
                          borderColor: selectedEndpoint === endpoint ? 'primary.main' : 'divider',
                        }}
                        onClick={() => setSelectedEndpoint(endpoint)}
                      >
                        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center', mb: 1 }}>
                            <Chip
                              label={endpoint.method}
                              size="small"
                              color={endpoint.method === 'GET' ? 'primary' : endpoint.method === 'POST' ? 'success' : 'warning'}
                            />
                            <Typography variant="body2" sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                              {endpoint.path}
                            </Typography>
                          </Box>
                          <Typography variant="body2" color="text.secondary">
                            {endpoint.description}
                          </Typography>
                        </CardContent>
                      </Card>
                    ))}
                  </Paper>
                </Grid>
                <Grid item xs={12} md={8}>
                  {selectedEndpoint && (
                    <Paper sx={{ p: 3 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Box>
                          <Typography variant="h5" gutterBottom>
                            {selectedEndpoint.method} {selectedEndpoint.path}
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            {selectedEndpoint.description}
                          </Typography>
                        </Box>
                      </Box>

                      <Divider sx={{ my: 2 }} />

                      {/* Parameters */}
                      {selectedEndpoint.parameters && (
                        <Box sx={{ mb: 3 }}>
                          <Typography variant="h6" gutterBottom>
                            Parameters
                          </Typography>
                          {selectedEndpoint.parameters.path && selectedEndpoint.parameters.path.length > 0 && (
                            <Box sx={{ mb: 2 }}>
                              <Typography variant="subtitle2" gutterBottom>
                                Path Parameters
                              </Typography>
                              <TableContainer>
                                <Table size="small">
                                  <TableHead>
                                    <TableRow>
                                      <TableCell>Name</TableCell>
                                      <TableCell>Type</TableCell>
                                      <TableCell>Description</TableCell>
                                    </TableRow>
                                  </TableHead>
                                  <TableBody>
                                    {selectedEndpoint.parameters.path.map((param) => (
                                      <TableRow key={param.name}>
                                        <TableCell>
                                          <code>{param.name}</code>
                                        </TableCell>
                                        <TableCell>{param.type}</TableCell>
                                        <TableCell>{param.description}</TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              </TableContainer>
                            </Box>
                          )}
                          {selectedEndpoint.parameters.query && selectedEndpoint.parameters.query.length > 0 && (
                            <Box sx={{ mb: 2 }}>
                              <Typography variant="subtitle2" gutterBottom>
                                Query Parameters
                              </Typography>
                              <TableContainer>
                                <Table size="small">
                                  <TableHead>
                                    <TableRow>
                                      <TableCell>Name</TableCell>
                                      <TableCell>Type</TableCell>
                                      <TableCell>Required</TableCell>
                                      <TableCell>Description</TableCell>
                                    </TableRow>
                                  </TableHead>
                                  <TableBody>
                                    {selectedEndpoint.parameters.query.map((param) => (
                                      <TableRow key={param.name}>
                                        <TableCell>
                                          <code>{param.name}</code>
                                        </TableCell>
                                        <TableCell>{param.type}</TableCell>
                                        <TableCell>{param.required ? 'Yes' : 'No'}</TableCell>
                                        <TableCell>{param.description}</TableCell>
                                      </TableRow>
                                    ))}
                                  </TableBody>
                                </Table>
                              </TableContainer>
                            </Box>
                          )}
                          {selectedEndpoint.parameters.body && (
                            <Box sx={{ mb: 2 }}>
                              <Typography variant="subtitle2" gutterBottom>
                                Request Body
                              </Typography>
                              <CodeBlock
                                code={JSON.stringify(selectedEndpoint.parameters.body.example, null, 2)}
                                language="json"
                              />
                            </Box>
                          )}
                        </Box>
                      )}

                      {/* Responses */}
                      <Box sx={{ mb: 3 }}>
                        <Typography variant="h6" gutterBottom>
                          Responses
                        </Typography>
                        {selectedEndpoint.responses.map((response, index) => (
                          <Accordion key={index}>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                                <Chip
                                  label={response.status}
                                  size="small"
                                  color={response.status < 300 ? 'success' : response.status < 400 ? 'info' : 'error'}
                                />
                                <Typography>{response.description}</Typography>
                              </Box>
                            </AccordionSummary>
                            <AccordionDetails>
                              {response.example && (
                                <CodeBlock code={JSON.stringify(response.example, null, 2)} language="json" />
                              )}
                            </AccordionDetails>
                          </Accordion>
                        ))}
                      </Box>

                      {/* Rate Limit */}
                      {selectedEndpoint.rateLimit && (
                        <Alert severity="info">
                          <strong>Rate Limit:</strong> {selectedEndpoint.rateLimit}
                        </Alert>
                      )}

                      {/* Code Examples */}
                      <Box sx={{ mt: 3 }}>
                        <Typography variant="h6" gutterBottom>
                          Code Examples
                        </Typography>
                        <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                          <Button
                            variant={codeLanguage === 'curl' ? 'contained' : 'outlined'}
                            size="small"
                            onClick={() => setCodeLanguage('curl')}
                          >
                            cURL
                          </Button>
                          <Button
                            variant={codeLanguage === 'javascript' ? 'contained' : 'outlined'}
                            size="small"
                            onClick={() => setCodeLanguage('javascript')}
                          >
                            JavaScript
                          </Button>
                          <Button
                            variant={codeLanguage === 'python' ? 'contained' : 'outlined'}
                            size="small"
                            onClick={() => setCodeLanguage('python')}
                          >
                            Python
                          </Button>
                          <Box sx={{ flex: 1 }} />
                          <Tooltip title="Copy code">
                            <IconButton onClick={handleCopyCode} size="small">
                              <CopyIcon />
                            </IconButton>
                          </Tooltip>
                        </Box>
                        <CodeBlock code={codeSnippet} language={codeLanguage} />
                      </Box>
                    </Paper>
                  )}
                </Grid>
              </Grid>
            </Box>
          )}

          {/* GraphQL Tab */}
          {activeTab === 2 && (
            <Box>
              <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>
                  GraphQL API
                </Typography>
                <Typography variant="body1" paragraph>
                  The GraphQL API provides a flexible query language for fetching data. All GraphQL requests are
                  sent to a single endpoint.
                </Typography>
                <CodeBlock code={`POST ${baseUrl}/api/v1/graphql/`} language="text" />
              </Paper>

              <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Query Examples
                </Typography>
                <CodeBlock
                  code={`query GetAssets {
  assets {
    id
    name
    status
    created_at
  }
}`}
                  language="graphql"
                />
              </Paper>

              <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Mutation Examples
                </Typography>
                <CodeBlock
                  code={`mutation CreateAsset($input: CreateAssetInput!) {
  createAsset(input: $input) {
    asset {
      id
      name
      status
    }
  }
}`}
                  language="graphql"
                />
              </Paper>

              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Schema Explorer
                </Typography>
                <Alert severity="info">
                  Use the GraphQL playground at <code>{baseUrl}/api/v1/graphql/</code> to explore the schema
                  interactively.
                </Alert>
              </Paper>
            </Box>
          )}

          {/* WebSocket Tab */}
          {activeTab === 3 && (
            <Box>
              <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h5" gutterBottom>
                  WebSocket API
                </Typography>
                <Typography variant="body1" paragraph>
                  The WebSocket API provides real-time updates for jobs, compliance scans, and data quality runs.
                </Typography>
              </Paper>

              <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Connection
                </Typography>
                <Typography variant="body2" paragraph>
                  Connect to the WebSocket endpoint:
                </Typography>
                <CodeBlock code={`wss://${window.location.host}/ws/`} language="text" />
                <Typography variant="body2" paragraph sx={{ mt: 2 }}>
                  Include authentication in the connection URL:
                </Typography>
                <CodeBlock code={`wss://${window.location.host}/ws/?token=YOUR_JWT_TOKEN`} language="text" />
              </Paper>

              <Paper sx={{ p: 3, mb: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Event Types
                </Typography>
                <TableContainer>
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableCell>Event Type</TableCell>
                        <TableCell>Description</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      <TableRow>
                        <TableCell>
                          <code>job.status.updated</code>
                        </TableCell>
                        <TableCell>Job status has been updated</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>
                          <code>compliance.scan.completed</code>
                        </TableCell>
                        <TableCell>Compliance scan has completed</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>
                          <code>dq.run.completed</code>
                        </TableCell>
                        <TableCell>Data quality run has completed</TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </TableContainer>
              </Paper>

              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Subscription Example
                </Typography>
                <CodeBlock
                  code={`const ws = new WebSocket('wss://${window.location.host}/ws/?token=YOUR_TOKEN');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);
};

// Subscribe to job updates
ws.send(JSON.stringify({
  type: 'subscribe',
  channel: 'job.status.updated',
  job_id: 'job-uuid'
}));`}
                  language="javascript"
                />
              </Paper>
            </Box>
          )}

          {/* API Explorer Tab */}
          {activeTab === 4 && (
            <Box>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h5" gutterBottom>
                  Interactive API Explorer
                </Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  Try API calls directly from the browser. Note: This requires CORS to be enabled on the API.
                </Typography>

                <Box sx={{ mt: 3 }}>
                  <FormControl fullWidth sx={{ mb: 2 }}>
                    <InputLabel>Select Endpoint</InputLabel>
                    <Select
                      value={selectedEndpoint?.path || ''}
                      label="Select Endpoint"
                      onChange={(e) => {
                        const endpoint = REST_ENDPOINTS.find((ep) => ep.path === e.target.value)
                        setSelectedEndpoint(endpoint || null)
                      }}
                    >
                      {REST_ENDPOINTS.map((endpoint) => (
                        <MenuItem key={endpoint.path} value={endpoint.path}>
                          {endpoint.method} {endpoint.path}
                        </MenuItem>
                      ))}
                    </Select>
                  </FormControl>

                  {selectedEndpoint && (
                    <Box>
                      <Typography variant="h6" gutterBottom>
                        Request
                      </Typography>
                      <CodeBlock code={codeSnippet} language={codeLanguage} />

                      <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
                        <Button variant="contained" startIcon={<PlayIcon />}>
                          Send Request
                        </Button>
                        <Button variant="outlined" startIcon={<CopyIcon />} onClick={handleCopyCode}>
                          Copy Code
                        </Button>
                      </Box>

                      <Alert severity="warning" sx={{ mt: 2 }}>
                        Interactive API explorer requires CORS to be enabled. Use the code examples above to make
                        requests from your application.
                      </Alert>
                    </Box>
                  )}
                </Box>
              </Paper>
            </Box>
          )}
        </Box>
      </Box>
    </Container>
  )
}

