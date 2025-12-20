/**
 * API Request Example Utilities
 *
 * Functions for generating code snippets in different languages
 */

import type { APIEndpoint } from '../APIEndpointCard/types'

/**
 * Generate cURL code snippet
 */
export function generateCurlSnippet(
  endpoint: APIEndpoint,
  baseUrl: string,
  authToken?: string
): string {
  const url = `${baseUrl}${endpoint.path}`
  const method = endpoint.method
  let curl = `curl -X ${method} "${url}"`

  if (authToken) {
    curl += ` \\\n  -H "Authorization: Bearer ${authToken}"`
  }

  // Add query parameters
  if (endpoint.parameters?.query && endpoint.parameters.query.length > 0) {
    const queryParams = endpoint.parameters.query
      .filter((p) => p.required)
      .map((p) => `${p.name}=value`)
      .join('&')
    if (queryParams) {
      const separator = url.includes('?') ? '&' : '?'
      curl += ` \\\n  "${url}${separator}${queryParams}"`
    }
  }

  // Add request body for non-GET requests
  if (endpoint.parameters?.body && method !== 'GET') {
    const body = JSON.stringify(endpoint.parameters.body.example, null, 2)
    curl += ` \\\n  -H "Content-Type: application/json" \\\n  -d '${body.replace(/'/g, "\\'")}'`
  }

  return curl
}

/**
 * Generate JavaScript (fetch) code snippet
 */
export function generateJavaScriptSnippet(
  endpoint: APIEndpoint,
  baseUrl: string,
  authToken?: string
): string {
  const url = `${baseUrl}${endpoint.path}`
  const method = endpoint.method.toLowerCase()

  const headers: Record<string, string> = {}
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`
  }
  if (endpoint.parameters?.body && method !== 'get') {
    headers['Content-Type'] = 'application/json'
  }

  let code = `const response = await fetch("${url}", {\n  method: "${endpoint.method}",`

  if (Object.keys(headers).length > 0) {
    code += `\n  headers: {`
    Object.entries(headers).forEach(([key, value]) => {
      code += `\n    "${key}": "${value}",`
    })
    code += `\n  },`
  } else {
    code += `\n  headers: {},`
  }

  if (endpoint.parameters?.body && method !== 'get') {
    const body = JSON.stringify(endpoint.parameters.body.example, null, 2)
    code += `\n  body: JSON.stringify(${body.replace(/\n/g, '\n    ')})`
  }

  code += `\n});\n\nconst data = await response.json();\nconsole.log(data);`

  return code
}

/**
 * Generate Python (requests) code snippet
 */
export function generatePythonSnippet(
  endpoint: APIEndpoint,
  baseUrl: string,
  authToken?: string
): string {
  const url = `${baseUrl}${endpoint.path}`
  const method = endpoint.method.toLowerCase()

  let code = `import requests\n\n`

  const headers: Record<string, string> = {}
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`
  }
  if (endpoint.parameters?.body && method !== 'get') {
    headers['Content-Type'] = 'application/json'
  }

  if (Object.keys(headers).length > 0) {
    code += `headers = ${JSON.stringify(headers, null, 2)}\n\n`
  }

  if (endpoint.parameters?.body && method !== 'get') {
    const body = endpoint.parameters.body.example
    code += `data = ${JSON.stringify(body, null, 2)}\n\n`
    code += `response = requests.${method}("${url}", headers=headers, json=data)`
  } else {
    if (Object.keys(headers).length > 0) {
      code += `response = requests.${method}("${url}", headers=headers)`
    } else {
      code += `response = requests.${method}("${url}")`
    }
  }

  code += `\n\nprint(response.json())`

  return code
}

