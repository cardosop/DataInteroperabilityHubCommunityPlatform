/**
 * API Endpoint Types
 *
 * Type definitions for API endpoint documentation
 */

export type HTTPMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface QueryParameter {
  name: string
  type: string
  required: boolean
  description: string
}

export interface PathParameter {
  name: string
  type: string
  description: string
}

export interface RequestBody {
  schema: Record<string, any>
  example: any
}

export interface APIResponse {
  status: number
  description: string
  schema?: Record<string, any>
  example?: any
}

export interface APIEndpoint {
  method: HTTPMethod
  path: string
  description: string
  parameters?: {
    query?: QueryParameter[]
    path?: PathParameter[]
    body?: RequestBody
  }
  responses: APIResponse[]
  rateLimit?: string
}

