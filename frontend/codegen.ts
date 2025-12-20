/**
 * GraphQL Code Generation Configuration
 *
 * This configuration file sets up GraphQL code generation to:
 * - Generate TypeScript types from GraphQL schema
 * - Generate typed hooks for queries and mutations
 * - Generate typed document nodes for better type safety
 *
 * Usage:
 *   npm run graphql:codegen
 *
 * This will:
 * 1. Fetch the GraphQL schema from the backend
 * 2. Generate TypeScript types in src/lib/api/graphql/generated/
 * 3. Generate typed hooks and operations
 *
 * Prerequisites:
 * - GraphQL endpoint must be accessible
 * - GraphQL schema introspection must be enabled
 */

import type { CodegenConfig } from '@graphql-codegen/cli'

const config: CodegenConfig = {
  // GraphQL schema source
  // Can be a URL, local file, or schema object
  schema: process.env.VITE_GRAPHQL_URL
    ? `${process.env.VITE_GRAPHQL_URL}/graphql-graphene/`
    : 'http://localhost:8000/graphql-graphene/',

  // GraphQL documents (queries, mutations, subscriptions)
  documents: ['src/**/*.{ts,tsx}', '!src/**/*.test.{ts,tsx}', '!src/**/*.spec.{ts,tsx}'],

  // Output configuration
  generates: {
    // TypeScript types from schema
    'src/lib/api/graphql/generated/types.ts': {
      plugins: ['typescript', 'typescript-operations'],
      config: {
        // Use enums instead of string unions
        enumsAsTypes: true,
        // Use const enums for better performance
        constEnums: true,
        // Generate input types
        inputMaybeValue: 'T | null | undefined',
        // Skip type checking for generated files
        skipTypename: false,
        // Add __typename to all types
        addTypename: true,
        // Use exact types
        exactOptionalPropertyTypes: true,
        // Generate scalars
        scalars: {
          DateTime: 'string',
          JSON: 'Record<string, any>',
          UUID: 'string',
          ID: 'string',
        },
      },
    },

    // Typed document nodes for better type safety
    'src/lib/api/graphql/generated/documents.ts': {
      plugins: ['typed-document-node'],
      config: {
        // Use typed document nodes
        dedupeOperationSuffix: true,
        // Optimize for bundle size
        optimizeDocumentNode: true,
      },
    },

    // React Query hooks (optional - we're using our own hooks)
    // Uncomment if you want to use generated hooks instead
    // 'src/lib/api/graphql/generated/hooks.ts': {
    //   plugins: ['typescript', 'typescript-operations', 'typescript-react-query'],
    //   config: {
    //     fetcher: '@/lib/api/graphql#graphqlClient',
    //     exposeQueryKeys: true,
    //     exposeFetcher: true,
    //   },
    // },
  },

  // Ignore patterns
  ignoreNoDocuments: true,

  // Override configuration
  config: {
    // Use const enums
    constEnums: true,
    // Skip type checking
    skipTypename: false,
    // Add __typename
    addTypename: true,
  },
}

export default config

