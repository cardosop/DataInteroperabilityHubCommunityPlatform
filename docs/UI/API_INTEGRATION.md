# API Integration Guide

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [API Client Setup](#api-client-setup)
3. [Authentication](#authentication)
4. [REST API Integration](#rest-api-integration)
5. [GraphQL API Integration](#graphql-api-integration)
6. [WebSocket Integration](#websocket-integration)
7. [Error Handling](#error-handling)
8. [Request/Response Interceptors](#requestresponse-interceptors)
9. [Caching Strategy](#caching-strategy)
10. [Rate Limiting Handling](#rate-limiting-handling)
11. [Retry Logic](#retry-logic)
12. [TypeScript Types](#typescript-types)
13. [Testing API Integration](#testing-api-integration)

---

## Overview

This guide provides comprehensive instructions for integrating the frontend application with the Data Interoperability Hub backend APIs. It covers REST API, GraphQL API, and WebSocket integration patterns, error handling, caching, and best practices.

**API Endpoints**:
- **REST API**: `/api/v1/`
- **GraphQL API**: `/graphql`
- **WebSocket API**: `/ws/events/`

**Base URLs**:
- **Development**: `http://localhost:8000`
- **Staging**: `https://staging-api.datahub.example.com`
- **Production**: `https://api.datahub.example.com`

---

## API Client Setup

### React Query Configuration

**Recommended**: Use React Query (TanStack Query) for server state management.

```typescript
// src/lib/api/react-query.ts
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
      retry: (failureCount, error) => {
        // Don't retry on 4xx errors
        if (error?.status >= 400 && error?.status < 500) {
          return false;
        }
        return failureCount < 3;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: false,
    },
  },
});

export { queryClient, QueryClientProvider, ReactQueryDevtools };
```

### Axios Configuration

```typescript
// src/lib/api/axios.ts
import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import { getAuthToken, refreshAuthToken } from './auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for authentication
apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const token = getAuthToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Add tenant ID if available
    const tenantId = getTenantId();
    if (tenantId) {
      config.headers['X-Tenant-ID'] = tenantId;
    }
    
    // Add request ID for tracing
    config.headers['X-Request-ID'] = crypto.randomUUID();
    
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling and token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    
    // Handle 401 Unauthorized - try to refresh token
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        const newToken = await refreshAuthToken();
        if (newToken) {
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return apiClient(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, redirect to login
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    
    // Handle rate limiting (429)
    if (error.response?.status === 429) {
      const retryAfter = error.response.headers['retry-after'];
      if (retryAfter) {
        await new Promise(resolve => setTimeout(resolve, parseInt(retryAfter) * 1000));
        return apiClient(originalRequest);
      }
    }
    
    return Promise.reject(error);
  }
);

export default apiClient;
```

### API Client Factory

```typescript
// src/lib/api/client.ts
import apiClient from './axios';
import { QueryClient } from '@tanstack/react-query';

export interface ApiResponse<T> {
  data: T;
  status: number;
  headers: Record<string, string>;
}

export interface PaginatedResponse<T> {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface CursorPaginatedResponse<T> {
  count: number;
  next_cursor: string | null;
  previous_cursor: string | null;
  page_size: number;
  results: T[];
}

export class ApiClient {
  constructor(
    private client = apiClient,
    private queryClient?: QueryClient
  ) {}

  async get<T>(url: string, config?: any): Promise<ApiResponse<T>> {
    const response = await this.client.get<T>(url, config);
    return {
      data: response.data,
      status: response.status,
      headers: response.headers,
    };
  }

  async post<T>(url: string, data?: any, config?: any): Promise<ApiResponse<T>> {
    const response = await this.client.post<T>(url, data, config);
    return {
      data: response.data,
      status: response.status,
      headers: response.headers,
    };
  }

  async put<T>(url: string, data?: any, config?: any): Promise<ApiResponse<T>> {
    const response = await this.client.put<T>(url, data, config);
    return {
      data: response.data,
      status: response.status,
      headers: response.headers,
    };
  }

  async patch<T>(url: string, data?: any, config?: any): Promise<ApiResponse<T>> {
    const response = await this.client.patch<T>(url, data, config);
    return {
      data: response.data,
      status: response.status,
      headers: response.headers,
    };
  }

  async delete<T>(url: string, config?: any): Promise<ApiResponse<T>> {
    const response = await this.client.delete<T>(url, config);
    return {
      data: response.data as T,
      status: response.status,
      headers: response.headers,
    };
  }
}

export const api = new ApiClient();
```

---

## Authentication

### Token Management

```typescript
// src/lib/api/auth.ts
const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const TOKEN_EXPIRY_KEY = 'token_expiry';

export interface AuthTokens {
  access: string;
  refresh: string;
  expiresIn: number;
}

export function setAuthTokens(tokens: AuthTokens): void {
  localStorage.setItem(TOKEN_KEY, tokens.access);
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh);
  
  const expiry = Date.now() + tokens.expiresIn * 1000;
  localStorage.setItem(TOKEN_EXPIRY_KEY, expiry.toString());
}

export function getAuthToken(): string | null {
  const token = localStorage.getItem(TOKEN_KEY);
  const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
  
  if (!token || !expiry) {
    return null;
  }
  
  // Check if token is expired
  if (Date.now() > parseInt(expiry)) {
    // Token expired, try to refresh
    refreshAuthToken();
    return null;
  }
  
  return token;
}

export async function refreshAuthToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refreshToken) {
    return null;
  }
  
  try {
    const response = await apiClient.post<AuthTokens>('/auth/refresh/', {
      refresh: refreshToken,
    });
    
    setAuthTokens(response.data);
    return response.data.access;
  } catch (error) {
    // Refresh failed, clear tokens
    clearAuthTokens();
    return null;
  }
}

export function clearAuthTokens(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(TOKEN_EXPIRY_KEY);
}

export function getTenantId(): string | null {
  return localStorage.getItem('tenant_id');
}

export function setTenantId(tenantId: string): void {
  localStorage.setItem('tenant_id', tenantId);
}
```

### Login Flow

```typescript
// src/lib/api/auth.ts (continued)
export interface LoginCredentials {
  email: string;
  password: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: {
    id: string;
    email: string;
    tenant_id: string;
  };
}

export async function login(credentials: LoginCredentials): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/auth/login/', credentials);
  
  setAuthTokens({
    access: response.data.access,
    refresh: response.data.refresh,
    expiresIn: 3600, // 1 hour default
  });
  
  if (response.data.user.tenant_id) {
    setTenantId(response.data.user.tenant_id);
  }
  
  return response.data;
}

export async function logout(): Promise<void> {
  try {
    await apiClient.post('/auth/logout/');
  } catch (error) {
    // Ignore errors on logout
  } finally {
    clearAuthTokens();
  }
}
```

---

## REST API Integration

### React Query Hooks

```typescript
// src/hooks/api/useAssets.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api/client';
import type { Asset, PaginatedResponse } from '@/types';

// Query keys
export const assetKeys = {
  all: ['assets'] as const,
  lists: () => [...assetKeys.all, 'list'] as const,
  list: (filters?: Record<string, any>) => [...assetKeys.lists(), filters] as const,
  details: () => [...assetKeys.all, 'detail'] as const,
  detail: (id: string) => [...assetKeys.details(), id] as const,
};

// List assets
export function useAssets(filters?: {
  page?: number;
  page_size?: number;
  ordering?: string;
  search?: string;
}) {
  return useQuery({
    queryKey: assetKeys.list(filters),
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters?.page) params.append('page', filters.page.toString());
      if (filters?.page_size) params.append('page_size', filters.page_size.toString());
      if (filters?.ordering) params.append('ordering', filters.ordering);
      if (filters?.search) params.append('search', filters.search);
      
      const response = await api.get<PaginatedResponse<Asset>>(
        `/assets/assets/?${params.toString()}`
      );
      return response.data;
    },
  });
}

// Get single asset
export function useAsset(id: string) {
  return useQuery({
    queryKey: assetKeys.detail(id),
    queryFn: async () => {
      const response = await api.get<Asset>(`/assets/assets/${id}/`);
      return response.data;
    },
    enabled: !!id,
  });
}

// Create asset
export function useCreateAsset() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (data: Partial<Asset>) => {
      const response = await api.post<Asset>('/assets/assets/', data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assetKeys.lists() });
    },
  });
}

// Update asset
export function useUpdateAsset() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<Asset> }) => {
      const response = await api.patch<Asset>(`/assets/assets/${id}/`, data);
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: assetKeys.detail(data.id) });
      queryClient.invalidateQueries({ queryKey: assetKeys.lists() });
    },
  });
}

// Delete asset
export function useDeleteAsset() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/assets/assets/${id}/`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: assetKeys.lists() });
    },
  });
}
```

### Pagination Handling

```typescript
// src/hooks/api/usePagination.ts
import { useState, useMemo } from 'react';
import type { PaginatedResponse } from '@/lib/api/client';

export function usePagination<T>(
  query: { data?: PaginatedResponse<T>; isLoading: boolean; error: any }
) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  
  const pagination = useMemo(() => {
    if (!query.data) {
      return {
        page: 1,
        pageSize: 20,
        totalPages: 0,
        totalCount: 0,
        hasNext: false,
        hasPrevious: false,
      };
    }
    
    return {
      page: query.data.page,
      pageSize: query.data.page_size,
      totalPages: query.data.total_pages,
      totalCount: query.data.count,
      hasNext: !!query.data.next,
      hasPrevious: !!query.data.previous,
    };
  }, [query.data]);
  
  const goToPage = (newPage: number) => {
    setPage(newPage);
  };
  
  const goToNext = () => {
    if (pagination.hasNext) {
      setPage(page + 1);
    }
  };
  
  const goToPrevious = () => {
    if (pagination.hasPrevious) {
      setPage(page - 1);
    }
  };
  
  return {
    ...pagination,
    goToPage,
    goToNext,
    goToPrevious,
    setPageSize,
  };
}
```

---

## GraphQL API Integration

### GraphQL Client Setup

```typescript
// src/lib/api/graphql.ts
import { GraphQLClient } from 'graphql-request';
import { getAuthToken } from './auth';

const GRAPHQL_ENDPOINT = `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/graphql`;

export const graphqlClient = new GraphQLClient(GRAPHQL_ENDPOINT, {
  headers: () => {
    const token = getAuthToken();
    return {
      Authorization: token ? `Bearer ${token}` : '',
    };
  },
});

// GraphQL query example
export const GET_ASSET_QUERY = `
  query GetAsset($id: ID!) {
    asset(id: $id) {
      id
      name
      key
      description
      status
      createdAt
      contract {
        id
        version
        status
      }
      dataset {
        id
        name
        version
      }
    }
  }
`;

export const LIST_ASSETS_QUERY = `
  query ListAssets($first: Int, $after: String, $filter: AssetFilter) {
    assets(first: $first, after: $after, filter: $filter) {
      edges {
        node {
          id
          name
          key
          status
        }
        cursor
      }
      pageInfo {
        hasNextPage
        hasPreviousPage
        startCursor
        endCursor
      }
    }
  }
`;
```

### React Query with GraphQL

```typescript
// src/hooks/api/useGraphQL.ts
import { useQuery } from '@tanstack/react-query';
import { graphqlClient, GET_ASSET_QUERY } from '@/lib/api/graphql';
import type { Asset } from '@/types';

export function useGraphQLAsset(id: string) {
  return useQuery({
    queryKey: ['graphql', 'asset', id],
    queryFn: async () => {
      const data = await graphqlClient.request<{ asset: Asset }>(GET_ASSET_QUERY, { id });
      return data.asset;
    },
    enabled: !!id,
  });
}
```

---

## WebSocket Integration

### WebSocket Client

```typescript
// src/lib/api/websocket.ts
import { getAuthToken } from './auth';

export type WebSocketEventType =
  | 'contract.created'
  | 'contract.updated'
  | 'contract.validated'
  | 'asset.created'
  | 'asset.updated'
  | 'job.started'
  | 'job.completed'
  | 'job.failed'
  | 'dq.run.completed'
  | 'compliance.scan.completed';

export interface WebSocketEvent {
  type: string;
  data: any;
  timestamp: string;
  request_id?: string;
}

export interface WebSocketMessage {
  type: 'subscribe' | 'unsubscribe' | 'ping';
  data?: {
    event_types?: WebSocketEventType[];
    filters?: Record<string, any>;
  };
}

export class WebSocketClient {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private listeners: Map<string, Set<(event: WebSocketEvent) => void>> = new Map();
  private pingInterval: number | null = null;

  constructor(private url: string) {}

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const token = getAuthToken();
      if (!token) {
        reject(new Error('No authentication token'));
        return;
      }

      const wsUrl = `${this.url}?token=${token}`;
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.startPingInterval();
        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketEvent = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };

      this.ws.onclose = () => {
        console.log('WebSocket disconnected');
        this.stopPingInterval();
        this.attemptReconnect();
      };
    });
  }

  private handleMessage(message: WebSocketEvent): void {
    // Handle different message types
    if (message.type === 'event') {
      const eventType = message.data?.event_type;
      if (eventType) {
        this.notifyListeners(eventType, message);
      }
    } else if (message.type === 'subscription_confirmed') {
      console.log('Subscription confirmed:', message.data);
    } else if (message.type === 'error') {
      console.error('WebSocket error:', message.data);
    } else if (message.type === 'pong') {
      // Ping response received
    }
  }

  subscribe(eventTypes: WebSocketEventType[], filters?: Record<string, any>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected');
      return;
    }

    const message: WebSocketMessage = {
      type: 'subscribe',
      data: {
        event_types: eventTypes,
        filters,
      },
    };

    this.ws.send(JSON.stringify(message));
  }

  unsubscribe(eventTypes: WebSocketEventType[]): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }

    const message: WebSocketMessage = {
      type: 'unsubscribe',
      data: {
        event_types: eventTypes,
      },
    };

    this.ws.send(JSON.stringify(message));
  }

  on(eventType: WebSocketEventType, callback: (event: WebSocketEvent) => void): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType)!.add(callback);

    // Return unsubscribe function
    return () => {
      this.listeners.get(eventType)?.delete(callback);
    };
  }

  private notifyListeners(eventType: string, event: WebSocketEvent): void {
    const listeners = this.listeners.get(eventType as WebSocketEventType);
    if (listeners) {
      listeners.forEach((callback) => callback(event));
    }
  }

  private startPingInterval(): void {
    this.pingInterval = window.setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000); // Ping every 30 seconds
  }

  private stopPingInterval(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

    setTimeout(() => {
      console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
      this.connect().catch((error) => {
        console.error('Reconnection failed:', error);
      });
    }, delay);
  }

  disconnect(): void {
    this.stopPingInterval();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

// Singleton instance
const WS_URL = `${import.meta.env.VITE_WS_URL || 'ws://localhost:8000'}/ws/events/`;
export const wsClient = new WebSocketClient(WS_URL);
```

### React Hook for WebSocket

```typescript
// src/hooks/useWebSocket.ts
import { useEffect, useRef } from 'react';
import { wsClient, type WebSocketEventType, type WebSocketEvent } from '@/lib/api/websocket';
import { useQueryClient } from '@tanstack/react-query';

export function useWebSocket(
  eventTypes: WebSocketEventType[],
  onEvent?: (event: WebSocketEvent) => void
) {
  const queryClient = useQueryClient();
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    let unsubscribeFunctions: (() => void)[] = [];

    const connectAndSubscribe = async () => {
      try {
        await wsClient.connect();
        wsClient.subscribe(eventTypes);

        // Set up listeners
        eventTypes.forEach((eventType) => {
          const unsubscribe = wsClient.on(eventType, (event) => {
            // Invalidate relevant queries
            if (eventType.startsWith('asset.')) {
              queryClient.invalidateQueries({ queryKey: ['assets'] });
            } else if (eventType.startsWith('contract.')) {
              queryClient.invalidateQueries({ queryKey: ['contracts'] });
            } else if (eventType.startsWith('job.')) {
              queryClient.invalidateQueries({ queryKey: ['jobs'] });
            }

            // Call custom handler
            onEventRef.current?.(event);
          });
          unsubscribeFunctions.push(unsubscribe);
        });
      } catch (error) {
        console.error('WebSocket connection failed:', error);
      }
    };

    connectAndSubscribe();

    return () => {
      unsubscribeFunctions.forEach((unsubscribe) => unsubscribe());
      wsClient.unsubscribe(eventTypes);
    };
  }, [eventTypes, queryClient]);
}
```

---

## Error Handling

### Error Types

```typescript
// src/lib/api/errors.ts
export interface ApiError {
  error: {
    code: string;
    message: string;
    http_status: number;
    request_id?: string;
    timestamp?: string;
    details?: Record<string, any>;
  };
}

export class ApiException extends Error {
  constructor(
    public code: string,
    public message: string,
    public status: number,
    public requestId?: string,
    public details?: Record<string, any>
  ) {
    super(message);
    this.name = 'ApiException';
  }

  static fromAxiosError(error: any): ApiException {
    if (error.response?.data?.error) {
      const apiError = error.response.data.error;
      return new ApiException(
        apiError.code || 'UNKNOWN_ERROR',
        apiError.message || 'An error occurred',
        apiError.http_status || error.response.status,
        apiError.request_id,
        apiError.details
      );
    }

    return new ApiException(
      'NETWORK_ERROR',
      error.message || 'Network error occurred',
      error.response?.status || 0
    );
  }
}
```

### Error Boundary Component

```typescript
// src/components/ErrorBoundary.tsx
import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Alert, Button, Container } from '@mui/material';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    // Log to error tracking service (e.g., Sentry)
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Container maxWidth="md" sx={{ mt: 4 }}>
          <Alert severity="error" sx={{ mb: 2 }}>
            <strong>Something went wrong</strong>
            <p>{this.state.error?.message}</p>
          </Alert>
          <Button variant="contained" onClick={this.handleReset}>
            Try Again
          </Button>
        </Container>
      );
    }

    return this.props.children;
  }
}
```

### Error Handling Hook

```typescript
// src/hooks/useErrorHandler.ts
import { useCallback } from 'react';
import { useSnackbar } from 'notistack';
import { ApiException } from '@/lib/api/errors';

export function useErrorHandler() {
  const { enqueueSnackbar } = useSnackbar();

  const handleError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiException) {
        // Handle API errors
        const message = error.details?.field_errors
          ? Object.values(error.details.field_errors).flat().join(', ')
          : error.message;

        enqueueSnackbar(message, {
          variant: 'error',
          autoHideDuration: 5000,
        });

        // Handle specific error codes
        if (error.code === 'UNAUTHORIZED') {
          // Redirect to login
          window.location.href = '/login';
        } else if (error.code === 'RATE_LIMIT_EXCEEDED') {
          // Show rate limit message
          enqueueSnackbar('Rate limit exceeded. Please try again later.', {
            variant: 'warning',
          });
        }
      } else if (error instanceof Error) {
        // Handle generic errors
        enqueueSnackbar(error.message, { variant: 'error' });
      } else {
        // Handle unknown errors
        enqueueSnackbar('An unexpected error occurred', { variant: 'error' });
      }
    },
    [enqueueSnackbar]
  );

  return { handleError };
}
```

---

## Request/Response Interceptors

### Request Interceptor

```typescript
// src/lib/api/interceptors.ts
import { InternalAxiosRequestConfig } from 'axios';
import { getAuthToken, getTenantId } from './auth';

export function requestInterceptor(config: InternalAxiosRequestConfig): InternalAxiosRequestConfig {
  // Add authentication token
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  // Add tenant ID
  const tenantId = getTenantId();
  if (tenantId) {
    config.headers['X-Tenant-ID'] = tenantId;
  }

  // Add request ID for tracing
  config.headers['X-Request-ID'] = crypto.randomUUID();

  // Add API version
  config.headers['X-API-Version'] = 'v1';

  return config;
}
```

### Response Interceptor

```typescript
// src/lib/api/interceptors.ts (continued)
import { AxiosResponse, AxiosError } from 'axios';
import { refreshAuthToken } from './auth';

export function responseInterceptor(response: AxiosResponse): AxiosResponse {
  // Log response for debugging (development only)
  if (import.meta.env.DEV) {
    console.log('API Response:', {
      url: response.config.url,
      status: response.status,
      data: response.data,
    });
  }

  // Extract rate limit headers
  const rateLimitHeaders = {
    limit: response.headers['x-ratelimit-limit'],
    remaining: response.headers['x-ratelimit-remaining'],
    reset: response.headers['x-ratelimit-reset'],
  };

  // Store rate limit info (can be used for UI indicators)
  if (rateLimitHeaders.limit) {
    localStorage.setItem('rate_limit_info', JSON.stringify(rateLimitHeaders));
  }

  return response;
}

export async function errorInterceptor(
  error: AxiosError
): Promise<AxiosError | any> {
  const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

  // Handle 401 - Unauthorized
  if (error.response?.status === 401 && !originalRequest._retry) {
    originalRequest._retry = true;

    try {
      const newToken = await refreshAuthToken();
      if (newToken) {
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      }
    } catch (refreshError) {
      // Refresh failed, redirect to login
      window.location.href = '/login';
      return Promise.reject(refreshError);
    }
  }

  // Handle 429 - Rate Limited
  if (error.response?.status === 429) {
    const retryAfter = error.response.headers['retry-after'];
    if (retryAfter) {
      await new Promise((resolve) => setTimeout(resolve, parseInt(retryAfter) * 1000));
      return apiClient(originalRequest);
    }
  }

  // Handle 500 - Server Error
  if (error.response?.status === 500) {
    // Log to error tracking service
    console.error('Server error:', error);
  }

  return Promise.reject(error);
}
```

---

## Caching Strategy

### React Query Caching

```typescript
// src/lib/api/cache.ts
import { QueryClient } from '@tanstack/react-query';

export const cacheConfig = {
  // Short-lived cache (1 minute) - frequently changing data
  short: {
    staleTime: 1 * 60 * 1000,
    cacheTime: 5 * 60 * 1000,
  },

  // Medium cache (5 minutes) - moderately changing data
  medium: {
    staleTime: 5 * 60 * 1000,
    cacheTime: 10 * 60 * 1000,
  },

  // Long cache (30 minutes) - rarely changing data
  long: {
    staleTime: 30 * 60 * 1000,
    cacheTime: 60 * 60 * 1000,
  },

  // Infinite cache - static reference data
  infinite: {
    staleTime: Infinity,
    cacheTime: Infinity,
  },
};

// Cache invalidation helpers
export function invalidateAssetCache(queryClient: QueryClient, assetId?: string): void {
  if (assetId) {
    queryClient.invalidateQueries({ queryKey: ['assets', 'detail', assetId] });
  }
  queryClient.invalidateQueries({ queryKey: ['assets', 'list'] });
}

export function invalidateContractCache(queryClient: QueryClient, contractId?: string): void {
  if (contractId) {
    queryClient.invalidateQueries({ queryKey: ['contracts', 'detail', contractId] });
  }
  queryClient.invalidateQueries({ queryKey: ['contracts', 'list'] });
}
```

---

## Rate Limiting Handling

### Rate Limit Hook

```typescript
// src/hooks/useRateLimit.ts
import { useState, useEffect } from 'react';

export interface RateLimitInfo {
  limit: number;
  remaining: number;
  reset: number;
}

export function useRateLimit(): RateLimitInfo | null {
  const [rateLimit, setRateLimit] = useState<RateLimitInfo | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem('rate_limit_info');
    if (stored) {
      try {
        setRateLimit(JSON.parse(stored));
      } catch (error) {
        console.error('Failed to parse rate limit info:', error);
      }
    }
  }, []);

  return rateLimit;
}
```

### Rate Limit Indicator Component

```typescript
// src/components/RateLimitIndicator.tsx
import { LinearProgress, Tooltip, Box } from '@mui/material';
import { useRateLimit } from '@/hooks/useRateLimit';

export function RateLimitIndicator() {
  const rateLimit = useRateLimit();

  if (!rateLimit) {
    return null;
  }

  const percentage = (rateLimit.remaining / rateLimit.limit) * 100;
  const isLow = percentage < 20;

  return (
    <Tooltip title={`${rateLimit.remaining} of ${rateLimit.limit} requests remaining`}>
      <Box sx={{ width: 100, mr: 2 }}>
        <LinearProgress
          variant="determinate"
          value={percentage}
          color={isLow ? 'error' : 'primary'}
          sx={{ height: 4, borderRadius: 2 }}
        />
      </Box>
    </Tooltip>
  );
}
```

---

## Retry Logic

### Retry Configuration

```typescript
// src/lib/api/retry.ts
export interface RetryConfig {
  maxRetries: number;
  retryDelay: number;
  retryableStatuses: number[];
  retryableErrors: string[];
}

export const defaultRetryConfig: RetryConfig = {
  maxRetries: 3,
  retryDelay: 1000,
  retryableStatuses: [500, 502, 503, 504],
  retryableErrors: ['NETWORK_ERROR', 'TIMEOUT'],
};

export async function retryRequest<T>(
  request: () => Promise<T>,
  config: Partial<RetryConfig> = {}
): Promise<T> {
  const finalConfig = { ...defaultRetryConfig, ...config };
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= finalConfig.maxRetries; attempt++) {
    try {
      return await request();
    } catch (error: any) {
      lastError = error;

      // Don't retry on last attempt
      if (attempt === finalConfig.maxRetries) {
        break;
      }

      // Check if error is retryable
      const isRetryable =
        finalConfig.retryableStatuses.includes(error?.response?.status) ||
        finalConfig.retryableErrors.includes(error?.code);

      if (!isRetryable) {
        break;
      }

      // Wait before retry with exponential backoff
      const delay = finalConfig.retryDelay * Math.pow(2, attempt);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }

  throw lastError || new Error('Request failed');
}
```

---

## TypeScript Types

### API Types

```typescript
// src/types/api.ts
export interface ApiResponse<T> {
  data: T;
  status: number;
  headers: Record<string, string>;
}

export interface PaginatedResponse<T> {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface CursorPaginatedResponse<T> {
  count: number;
  next_cursor: string | null;
  previous_cursor: string | null;
  page_size: number;
  results: T[];
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    http_status: number;
    request_id?: string;
    timestamp?: string;
    details?: {
      field_errors?: Record<string, string[]>;
      [key: string]: any;
    };
  };
}
```

---

## Testing API Integration

### Mock API Client

```typescript
// src/lib/api/mock.ts
import { ApiClient } from './client';

export class MockApiClient extends ApiClient {
  private mockData: Map<string, any> = new Map();

  setMockData(endpoint: string, data: any): void {
    this.mockData.set(endpoint, data);
  }

  async get<T>(url: string): Promise<ApiResponse<T>> {
    const mockData = this.mockData.get(url);
    if (mockData) {
      return {
        data: mockData,
        status: 200,
        headers: {},
      };
    }
    throw new Error(`No mock data for ${url}`);
  }
}

// Usage in tests
export const mockApi = new MockApiClient();
```

### Test Utilities

```typescript
// src/test-utils/api.ts
import { QueryClient } from '@tanstack/react-query';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        cacheTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderOptions
) {
  const queryClient = createTestQueryClient();

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...options });
}
```

---

## Workflow State Management

### Overview

The frontend tracks multi-step workflow execution through React Query and WebSocket integration.

### Workflow Progress Components

#### TransformationPipelineProgress

Tracks transformation pipeline execution progress:

```typescript
import { useWorkflowProgress } from '@/hooks/useWorkflowProgress';

function TransformationPipelineProgress({ pipelineId }: { pipelineId: string }) {
  const { workflow, progress, currentStep, error } = useWorkflowProgress(
    'transformation_pipeline',
    pipelineId
  );

  return (
    <WorkflowProgress
      workflow={workflow}
      progress={progress}
      currentStep={currentStep}
      error={error}
    />
  );
}
```

#### AIMLOperationProgress

Tracks AI/ML operation progress:

```typescript
function AIMLOperationProgress({ operationId }: { operationId: string }) {
  const { workflow, progress, currentStep, error } = useWorkflowProgress(
    'ai_ml_operation',
    operationId
  );

  return (
    <WorkflowProgress
      workflow={workflow}
      progress={progress}
      currentStep={currentStep}
      error={error}
    />
  );
}
```

### React Query Integration

Workflow state is cached in React Query:

```typescript
import { useQuery } from '@tanstack/react-query';

function useWorkflowProgress(workflowName: string, instanceId: string) {
  return useQuery({
    queryKey: ['workflow', workflowName, instanceId],
    queryFn: () => api.getWorkflowInstance(workflowName, instanceId),
    refetchInterval: 2000, // Poll every 2 seconds
  });
}
```

### WebSocket Integration

Real-time workflow updates via WebSocket:

```typescript
import { useWebSocket } from '@/hooks/useWebSocket';

function useWorkflowUpdates(workflowName: string, instanceId: string) {
  const { data, queryClient } = useWebSocket(`workflow.${workflowName}.${instanceId}`);

  useEffect(() => {
    if (data) {
      // Update React Query cache
      queryClient.setQueryData(
        ['workflow', workflowName, instanceId],
        data
      );
    }
  }, [data, workflowName, instanceId, queryClient]);
}
```

### State Reconciliation

Handle conflicts between optimistic updates and server state:

```typescript
function useWorkflowMutation(workflowName: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: WorkflowInput) => 
      api.startWorkflow(workflowName, input),
    onMutate: async (input) => {
      // Optimistic update
      await queryClient.cancelQueries(['workflow', workflowName]);
      const previous = queryClient.getQueryData(['workflow', workflowName]);
      queryClient.setQueryData(['workflow', workflowName], {
        ...previous,
        status: 'running',
      });
      return { previous };
    },
    onError: (err, input, context) => {
      // Rollback on error
      queryClient.setQueryData(['workflow', workflowName], context.previous);
    },
    onSettled: () => {
      // Refetch to reconcile
      queryClient.invalidateQueries(['workflow', workflowName]);
    },
  });
}
```

### Workflow Error Handling

Handle workflow failures gracefully:

```typescript
function WorkflowError({ error, workflow }: { error: Error; workflow: Workflow }) {
  if (error.type === 'COMPENSATION_FAILED') {
    return <CompensationError workflow={workflow} />;
  }
  if (error.type === 'STEP_FAILED') {
    return <StepError workflow={workflow} failedStep={error.step} />;
  }
  return <GenericError error={error} />;
}
```

---

## Best Practices

1. **Always use React Query for server state** - Don't use useState for API data
2. **Handle loading and error states** - Always show appropriate UI states
3. **Use TypeScript types** - Define types for all API responses
4. **Implement optimistic updates** - Update UI immediately, rollback on error
5. **Cache invalidation** - Invalidate related queries after mutations
6. **Error boundaries** - Wrap components in error boundaries
7. **Request deduplication** - React Query handles this automatically
8. **Pagination** - Use cursor-based pagination for large datasets
9. **WebSocket reconnection** - Always implement reconnection logic
10. **Rate limit awareness** - Show rate limit status to users

---

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

