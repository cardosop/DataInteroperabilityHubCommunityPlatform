# GraphQL Setup Guide

This guide explains how to set up and use GraphQL in the frontend application.

## Overview

The frontend uses Apollo Client for GraphQL operations, integrated with React Query for caching and state management. GraphQL code generation is set up to generate TypeScript types from the GraphQL schema.

## Prerequisites

1. **GraphQL Endpoint**: The GraphQL API must be accessible at `/graphql-graphene/` (or configured via `VITE_GRAPHQL_URL`)
2. **GraphQL Schema**: Schema introspection must be enabled on the backend
3. **Apollo Client**: Already installed and configured

## Installation

### GraphQL Code Generation Packages

To enable GraphQL code generation, install the required packages:

```bash
npm install --save-dev @graphql-codegen/cli @graphql-codegen/typescript @graphql-codegen/typescript-operations @graphql-codegen/typed-document-node
```

## Configuration

### GraphQL Client

The Apollo Client is configured in `src/lib/config/apollo.ts`:
- Authentication headers (JWT token + tenant ID)
- Error handling
- In-memory cache
- Default query options

### Code Generation

GraphQL code generation is configured in `codegen.ts`:
- Schema source: GraphQL endpoint URL
- Documents: All `.ts` and `.tsx` files (excluding tests)
- Output: TypeScript types and typed document nodes

## Usage

### 1. Generic GraphQL Hooks

#### useGraphQLQuery

Generic hook for GraphQL queries:

```tsx
import { gql } from '@apollo/client'
import { useGraphQLQuery } from '@/hooks/useGraphQLQuery'

const GET_ASSET = gql`
  query GetAsset($id: ID!) {
    asset(id: $id) {
      id
      name
      status
    }
  }
`

function AssetDetail({ assetId }: { assetId: string }) {
  const { data, isLoading, error } = useGraphQLQuery({
    query: GET_ASSET,
    variables: { id: assetId }
  })

  if (isLoading) return <Loading />
  if (error) return <Error message={error.message} />

  return <div>{data?.data?.asset?.name}</div>
}
```

#### useGraphQLMutation

Generic hook for GraphQL mutations:

```tsx
import { gql } from '@apollo/client'
import { useGraphQLMutation } from '@/hooks/useGraphQLMutation'

const CREATE_ASSET = gql`
  mutation CreateAsset($input: AssetInput!) {
    createAsset(input: $input) {
      asset {
        id
        name
      }
      errors {
        field
        message
      }
    }
  }
`

function CreateAssetForm() {
  const createAsset = useGraphQLMutation({
    mutation: CREATE_ASSET
  })

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      const result = await createAsset.mutateAsync({
        input: {
          name: 'New Asset',
          key: 'new-asset'
        }
      })
      // Handle success
    } catch (error) {
      // Handle error
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <button disabled={createAsset.isPending}>Create</button>
    </form>
  )
}
```

### 2. Example Hook: useGraphQLAsset

An example hook for fetching a single asset:

```tsx
import { useGraphQLAsset } from '@/hooks/useGraphQLAsset'

function AssetDetail({ assetId }: { assetId: string }) {
  const { data, isLoading, error } = useGraphQLAsset(assetId)

  if (isLoading) return <Loading />
  if (error) return <Error message={error.message} />
  if (!data?.asset) return <NotFound />

  return <div>{data.asset.name}</div>
}
```

### 3. GraphQL Code Generation

After installing the codegen packages, generate TypeScript types:

```bash
npm run graphql:codegen
```

This will:
1. Fetch the GraphQL schema from the backend
2. Generate TypeScript types in `src/lib/api/graphql/generated/types.ts`
3. Generate typed document nodes in `src/lib/api/graphql/generated/documents.ts`

### 4. Using Generated Types

Once code generation is complete, you can use the generated types:

```tsx
import { GetAssetQuery, GetAssetQueryVariables } from '@/lib/api/graphql/generated/types'
import { GetAssetDocument } from '@/lib/api/graphql/generated/documents'
import { useGraphQLQuery } from '@/hooks/useGraphQLQuery'

function AssetDetail({ assetId }: { assetId: string }) {
  const { data, isLoading } = useGraphQLQuery<GetAssetQuery, GetAssetQueryVariables>({
    query: GetAssetDocument,
    variables: { id: assetId }
  })

  // data is fully typed!
  return <div>{data?.data?.asset?.name}</div>
}
```

## Integration with React Query

The GraphQL hooks integrate Apollo Client with React Query:

- **Caching**: React Query manages query caching and invalidation
- **State Management**: React Query provides loading, error, and success states
- **Deduplication**: React Query deduplicates identical queries
- **Background Refetching**: React Query handles background refetching

## Best Practices

1. **Use Code Generation**: Always use generated types for type safety
2. **Query Keys**: Query keys are automatically generated from query strings and variables
3. **Error Handling**: Check both `data.errors` and React Query `error` state
4. **Cache Invalidation**: Mutations automatically invalidate GraphQL queries
5. **Fetch Policies**: Use appropriate fetch policies for your use case:
   - `cache-first`: Default, use cache if available
   - `cache-and-network`: Use cache but also fetch fresh data
   - `network-only`: Always fetch from network

## Troubleshooting

### Code Generation Fails

1. Ensure GraphQL endpoint is accessible
2. Check that schema introspection is enabled
3. Verify `VITE_GRAPHQL_URL` is set correctly

### Types Not Generated

1. Run `npm run graphql:codegen` manually
2. Check `codegen.ts` configuration
3. Ensure GraphQL queries/mutations are in `.ts` or `.tsx` files

### Authentication Errors

1. Check that JWT token is valid
2. Verify tenant ID is set correctly
3. Check Apollo Client auth link configuration

## Files

- `src/lib/config/apollo.ts` - Apollo Client configuration
- `src/lib/api/graphql.ts` - GraphQL client utilities
- `src/hooks/useGraphQLQuery.ts` - Generic query hook
- `src/hooks/useGraphQLMutation.ts` - Generic mutation hook
- `src/hooks/useGraphQLAsset.ts` - Example asset query hook
- `codegen.ts` - GraphQL code generation configuration
- `src/lib/api/graphql/generated/` - Generated types and documents

