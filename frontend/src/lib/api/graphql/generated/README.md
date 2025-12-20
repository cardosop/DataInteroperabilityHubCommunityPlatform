# GraphQL Generated Types

This directory contains auto-generated TypeScript types and utilities from the GraphQL schema.

## Files

- `types.ts` - TypeScript types generated from the GraphQL schema
- `documents.ts` - Typed document nodes for queries and mutations

## Generation

To regenerate these files, run:

```bash
npm run graphql:codegen
```

## Prerequisites

1. GraphQL endpoint must be accessible
2. GraphQL schema introspection must be enabled
3. Environment variable `VITE_GRAPHQL_URL` should be set (or defaults to `http://localhost:8000/graphql-graphene/`)

## Usage

```tsx
import { GetAssetQuery, GetAssetQueryVariables } from '@/lib/api/graphql/generated/types'
import { GET_ASSET_QUERY } from '@/lib/api/graphql/generated/documents'
import { useGraphQLQuery } from '@/hooks/useGraphQLQuery'

function AssetDetail({ assetId }: { assetId: string }) {
  const { data, isLoading } = useGraphQLQuery<GetAssetQuery, GetAssetQueryVariables>({
    query: GET_ASSET_QUERY,
    variables: { id: assetId }
  })

  // data is fully typed!
  return <div>{data?.asset?.name}</div>
}
```

## Note

These files are auto-generated and should not be edited manually.
Any changes will be overwritten on the next code generation run.

