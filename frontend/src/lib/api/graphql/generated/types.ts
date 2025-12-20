/**
 * GraphQL Generated Types
 *
 * This file is auto-generated from the GraphQL schema.
 * To regenerate, run: npm run graphql:codegen
 *
 * Prerequisites:
 * - Install GraphQL codegen packages:
 *   npm install --save-dev @graphql-codegen/cli @graphql-codegen/typescript @graphql-codegen/typescript-operations @graphql-codegen/typed-document-node
 *
 * - Ensure GraphQL endpoint is accessible
 * - Run: npm run graphql:codegen
 *
 * Note: This is a placeholder file. After running codegen, this will contain
 * all TypeScript types generated from your GraphQL schema.
 */

/**
 * Placeholder types - will be replaced by codegen
 */
export type Scalars = {
  ID: string
  String: string
  Boolean: boolean
  Int: number
  Float: number
  DateTime: string
  JSON: Record<string, any>
  UUID: string
}

/**
 * Example: Asset type (will be generated from schema)
 * This is a placeholder - actual types will be generated
 */
export type Asset = {
  __typename?: 'Asset'
  id: Scalars['ID']
  key: Scalars['String']
  name: Scalars['String']
  description?: Scalars['String'] | null
  domain?: Scalars['String'] | null
  status: AssetStatusEnum
  visibility: AssetVisibilityEnum
  dqStatus: DQStatusEnum
  complianceStatus: ComplianceStatusEnum
  createdAt: Scalars['DateTime']
  updatedAt: Scalars['DateTime']
}

/**
 * Example: Asset status enum (will be generated from schema)
 */
export type AssetStatusEnum = 'DRAFT' | 'ACTIVE' | 'PUBLIC' | 'RETIRED'

/**
 * Example: Asset visibility enum (will be generated from schema)
 */
export type AssetVisibilityEnum = 'INTERNAL' | 'PUBLIC'

/**
 * Example: DQ status enum (will be generated from schema)
 */
export type DQStatusEnum = 'UNKNOWN' | 'PASS' | 'WARN' | 'FAIL'

/**
 * Example: Compliance status enum (will be generated from schema)
 */
export type ComplianceStatusEnum = 'UNKNOWN' | 'PASS' | 'WARN' | 'FAIL'

/**
 * Example: Query type (will be generated from schema)
 */
export type Query = {
  __typename?: 'Query'
  me?: User | null
  asset?: Asset | null
  assets?: AssetConnection | null
  contract?: Contract | null
  contracts?: ContractConnection | null
  dataset?: Dataset | null
  datasets?: DatasetConnection | null
  job?: Job | null
  jobs?: JobConnection | null
}

/**
 * Example: User type (will be generated from schema)
 */
export type User = {
  __typename?: 'User'
  id: Scalars['ID']
  email: Scalars['String']
  displayName?: Scalars['String'] | null
  roles: Array<Scalars['String']>
  createdAt: Scalars['DateTime']
}

/**
 * Example: Contract type (will be generated from schema)
 */
export type Contract = {
  __typename?: 'Contract'
  id: Scalars['ID']
  name?: Scalars['String'] | null
  status: ContractStatusEnum
  createdAt: Scalars['DateTime']
  updatedAt: Scalars['DateTime']
}

/**
 * Example: Contract status enum (will be generated from schema)
 */
export type ContractStatusEnum = 'DRAFT' | 'ACTIVE' | 'RETIRED'

/**
 * Example: Dataset type (will be generated from schema)
 */
export type Dataset = {
  __typename?: 'Dataset'
  id: Scalars['ID']
  name?: Scalars['String'] | null
  format?: Scalars['String'] | null
  createdAt: Scalars['DateTime']
  updatedAt: Scalars['DateTime']
}

/**
 * Example: Job type (will be generated from schema)
 */
export type Job = {
  __typename?: 'Job'
  id: Scalars['ID']
  type: JobTypeEnum
  status: JobStatusEnum
  createdAt: Scalars['DateTime']
  updatedAt: Scalars['DateTime']
}

/**
 * Example: Job type enum (will be generated from schema)
 */
export type JobTypeEnum =
  | 'DQ_RUN'
  | 'COMPLIANCE_RUN'
  | 'CONTRACT_VALIDATION'
  | 'SEMANTIC_MAPPING'
  | 'CONTRACT_MIGRATION'
  | 'SCHEDULED_INGESTION'
  | 'RETENTION_POLICY_ENFORCEMENT'
  | 'SEARCH_INDEX_UPDATE'

/**
 * Example: Job status enum (will be generated from schema)
 */
export type JobStatusEnum = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED'

/**
 * Example: Connection types for pagination (will be generated from schema)
 */
export type AssetConnection = {
  __typename?: 'AssetConnection'
  edges?: Array<AssetEdge | null> | null
  pageInfo: PageInfo
}

export type AssetEdge = {
  __typename?: 'AssetEdge'
  node?: Asset | null
  cursor: Scalars['String']
}

export type ContractConnection = {
  __typename?: 'ContractConnection'
  edges?: Array<ContractEdge | null> | null
  pageInfo: PageInfo
}

export type ContractEdge = {
  __typename?: 'ContractEdge'
  node?: Contract | null
  cursor: Scalars['String']
}

export type DatasetConnection = {
  __typename?: 'DatasetConnection'
  edges?: Array<DatasetEdge | null> | null
  pageInfo: PageInfo
}

export type DatasetEdge = {
  __typename?: 'DatasetEdge'
  node?: Dataset | null
  cursor: Scalars['String']
}

export type JobConnection = {
  __typename?: 'JobConnection'
  edges?: Array<JobEdge | null> | null
  pageInfo: PageInfo
}

export type JobEdge = {
  __typename?: 'JobEdge'
  node?: Job | null
  cursor: Scalars['String']
}

export type PageInfo = {
  __typename?: 'PageInfo'
  hasNextPage: Scalars['Boolean']
  hasPreviousPage: Scalars['Boolean']
  startCursor?: Scalars['String'] | null
  endCursor?: Scalars['String'] | null
}

