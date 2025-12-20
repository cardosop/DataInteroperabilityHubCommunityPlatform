/**
 * APIExplorer Component
 *
 * Interactive component for testing API endpoints:
 * - Endpoint selection and display
 * - Request parameter input (query, path, body)
 * - API call execution
 * - Response display with syntax highlighting
 * - Error handling
 * - Loading states
 */

import React, { useState, useCallback, useMemo } from 'react'
import {
  Box,
  Paper,
  Typography,
  Button,
  TextField,
  Grid,
  Chip,
  Alert,
  CircularProgress,
  Divider,
} from '@mui/material'
import { PlayArrow as PlayIcon } from '@mui/icons-material'
import Editor from '@monaco-editor/react'
import { useMutation } from '@tanstack/react-query'
import { apiClient } from '@/lib/api/client'
import type { APIEndpoint } from '../APIEndpointCard/types'
import { APIResponseExample } from '../APIResponseExample'

export interface APIExplorerProps {
  /**
   * API endpoint information
   */
  endpoint: APIEndpoint
  /**
   * Base URL for the API
   */
  baseUrl: string
  /**
   * Authentication token (optional)
   */
  authToken?: string
  /**
   * Additional CSS class name
   */
  className?: string
}

/**
 * Get color for HTTP method badge
 */
function getMethodColor(method: APIEndpoint['method']): 'primary' | 'success' | 'warning' | 'error' | 'default' {
  switch (method) {
    case 'GET':
      return 'primary'
    case 'POST':
      return 'success'
    case 'PUT':
    case 'PATCH':
      return 'warning'
    case 'DELETE':
      return 'error'
    default:
      return 'default'
  }
}

/**
 * APIExplorer component
 */
export const APIExplorer: React.FC<APIExplorerProps> = ({
  endpoint,
  baseUrl,
  authToken,
  className,
}) => {
  const [queryParams, setQueryParams] = useState<Record<string, string>>({})
  const [pathParams, setPathParams] = useState<Record<string, string>>({})
  const [requestBody, setRequestBody] = useState<string>('')
  const [response, setResponse] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  // Initialize request body from endpoint example
  React.useEffect(() => {
    if (endpoint.parameters?.body?.example) {
      setRequestBody(JSON.stringify(endpoint.parameters.body.example, null, 2))
    } else {
      setRequestBody('')
    }
  }, [endpoint])

  // Build request URL with path parameters
  const requestUrl = useMemo(() => {
    let url = endpoint.path
    if (endpoint.parameters?.path) {
      endpoint.parameters.path.forEach((param) => {
        const value = pathParams[param.name] || `{${param.name}}`
        url = url.replace(`{${param.name}}`, value)
      })
    }
    return url
  }, [endpoint.path, endpoint.parameters?.path, pathParams])

  // Build query string
  const queryString = useMemo(() => {
    const params = new URLSearchParams()
    endpoint.parameters?.query?.forEach((param) => {
      const value = queryParams[param.name]
      if (value) {
        params.append(param.name, value)
      }
    })
    const query = params.toString()
    return query ? `?${query}` : ''
  }, [endpoint.parameters?.query, queryParams])

  // API call mutation
  const mutation = useMutation({
    mutationFn: async () => {
      setError(null)
      setResponse(null)

      const url = `${requestUrl}${queryString}`
      const config: any = {}

      // Add authentication if provided
      if (authToken) {
        config.headers = {
          Authorization: `Bearer ${authToken}`,
        }
      }

      // Parse and add request body for non-GET requests
      let body: any = undefined
      if (endpoint.parameters?.body && endpoint.method !== 'GET') {
        try {
          body = JSON.parse(requestBody)
        } catch (err) {
          throw new Error('Invalid JSON in request body')
        }
      }

      // Make API call based on method
      // Construct full URL with baseUrl
      const fullUrl = `${baseUrl}${url}`
      switch (endpoint.method) {
        case 'GET':
          return await apiClient.get(fullUrl, { ...config, baseURL: undefined })
        case 'POST':
          return await apiClient.post(fullUrl, body, { ...config, baseURL: undefined })
        case 'PUT':
          return await apiClient.put(fullUrl, body, { ...config, baseURL: undefined })
        case 'PATCH':
          return await apiClient.patch(fullUrl, body, { ...config, baseURL: undefined })
        case 'DELETE':
          return await apiClient.delete(fullUrl, { ...config, baseURL: undefined })
        default:
          throw new Error(`Unsupported HTTP method: ${endpoint.method}`)
      }
    },
    onSuccess: (data) => {
      setResponse(data)
      setError(null)
    },
    onError: (err: any) => {
      setError(err.response?.data?.error?.message || err.message || 'Request failed')
      setResponse(null)
    },
  })

  const handleSendRequest = useCallback(() => {
    mutation.mutate()
  }, [mutation])

  const handleQueryParamChange = useCallback((name: string, value: string) => {
    setQueryParams((prev) => ({ ...prev, [name]: value }))
  }, [])

  const handlePathParamChange = useCallback((name: string, value: string) => {
    setPathParams((prev) => ({ ...prev, [name]: value }))
  }, [])

  const handleRequestBodyChange = useCallback((value: string | undefined) => {
    setRequestBody(value || '')
  }, [])

  return (
    <Paper className={className} sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
        <Chip label={endpoint.method} size="small" color={getMethodColor(endpoint.method)} />
        <Typography variant="h6" sx={{ fontFamily: 'monospace', flex: 1 }}>
          {requestUrl}
        </Typography>
        <Button
          variant="contained"
          startIcon={mutation.isPending ? <CircularProgress size={16} /> : <PlayIcon />}
          onClick={handleSendRequest}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? 'Sending...' : 'Send Request'}
        </Button>
      </Box>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {endpoint.description}
      </Typography>

      <Divider sx={{ my: 3 }} />

      {/* Query Parameters */}
      {endpoint.parameters?.query && endpoint.parameters.query.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Query Parameters
          </Typography>
          <Grid container spacing={2}>
            {endpoint.parameters.query.map((param) => (
              <Grid item xs={12} sm={6} key={param.name}>
                <TextField
                  fullWidth
                  label={param.name}
                  type={param.type === 'integer' ? 'number' : 'text'}
                  value={queryParams[param.name] || ''}
                  onChange={(e) => handleQueryParamChange(param.name, e.target.value)}
                  helperText={param.description}
                  required={param.required}
                  size="small"
                />
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* Path Parameters */}
      {endpoint.parameters?.path && endpoint.parameters.path.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Path Parameters
          </Typography>
          <Grid container spacing={2}>
            {endpoint.parameters.path.map((param) => (
              <Grid item xs={12} sm={6} key={param.name}>
                <TextField
                  fullWidth
                  label={param.name}
                  value={pathParams[param.name] || ''}
                  onChange={(e) => handlePathParamChange(param.name, e.target.value)}
                  helperText={param.description}
                  required
                  size="small"
                />
              </Grid>
            ))}
          </Grid>
        </Box>
      )}

      {/* Request Body */}
      {endpoint.parameters?.body && endpoint.method !== 'GET' && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Request Body
          </Typography>
          <Editor
            height="200px"
            language="json"
            value={requestBody}
            onChange={handleRequestBodyChange}
            options={{
              minimap: { enabled: false },
              lineNumbers: 'on',
              scrollBeyondLastLine: false,
              automaticLayout: true,
              wordWrap: 'on',
              folding: true,
              bracketPairColorization: { enabled: true },
              fontSize: 14,
              theme: 'vs-dark',
            }}
          />
        </Box>
      )}

      {/* Response */}
      {mutation.isSuccess && response && (
        <Box sx={{ mt: 3 }}>
          <Typography variant="subtitle1" gutterBottom>
            Response
          </Typography>
          <APIResponseExample
            response={{
              status: response.status || 200,
              description: 'Success',
              example: response.data,
            }}
          />
        </Box>
      )}

      {/* Error */}
      {error && (
        <Alert severity="error" sx={{ mt: 3 }}>
          <Typography variant="body2">
            <strong>Error:</strong> {error}
          </Typography>
        </Alert>
      )}
    </Paper>
  )
}

APIExplorer.displayName = 'APIExplorer'

