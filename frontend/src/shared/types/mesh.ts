/**
 * Mesh Domain Types
 * Based on backend DomainSerializer and DataMeshDomain model
 */

export const DomainStatus = {
  ACTIVE: 'ACTIVE',
  INACTIVE: 'INACTIVE',
  ARCHIVED: 'ARCHIVED',
} as const;
export type DomainStatus = (typeof DomainStatus)[keyof typeof DomainStatus];

export interface MeshDomain {
  id: string;
  name: string;
  description?: string;
  owner?: string;
  owner_email?: string;
  tenant: string;
  tenant_name: string;
  boundaries: Record<string, any>;
  capabilities: Record<string, any>;
  resource_quota: Record<string, any>;
  resource_usage: Record<string, any>;
  status: DomainStatus;
  created_at: string;
  updated_at: string;
}

export interface MeshDomainCreateRequest {
  name: string;
  description?: string;
  owner_id?: string;
  boundaries?: Record<string, any>;
  capabilities?: Record<string, any>;
  resource_quota?: Record<string, any>;
  status?: DomainStatus;
}

export interface MeshDomainUpdateRequest {
  name?: string;
  description?: string;
  owner_id?: string;
  boundaries?: Record<string, any>;
  capabilities?: Record<string, any>;
  resource_quota?: Record<string, any>;
  status?: DomainStatus;
}

export interface MeshDomainListFilters {
  page?: number;
  page_size?: number;
  ordering?: string;
  search?: string;
  status?: DomainStatus;
  owner_id?: string;
}

export interface DomainAnalytics {
  domain_id: string;
  domain_name: string;
  status: DomainStatus;
  created_at: string;
  updated_at: string;
  resource_usage: Record<string, any>;
  resource_quota: Record<string, any>;
  resource_usage_percentages: Record<string, number>;
  total_policies: number;
  applied_policies: number;
  pending_policies: number;
  compliance_status?: string;
  violation_count: number;
  last_compliance_check?: string;
  boundaries_count: number;
  capabilities_count: number;
  health_score?: number;
  health_status?: string;
}

export interface TopologyNode {
  id: string;
  name: string;
  description?: string;
  status: DomainStatus;
  owner_id?: string;
  created_at?: string;
  health_metrics?: {
    health_score: number;
    policy_count: number;
    compliance_status: string;
    violation_count: number;
    is_active: boolean;
  };
}

export interface TopologyEdge {
  source: string;
  target: string;
  type: string;
  weight: number;
}

export interface TopologyMetadata {
  tenant_id: string;
  domain_count: number;
  relationship_count: number;
  generated_at: string;
}

export interface TopologySummary {
  total_domains: number;
  active_domains: number;
  total_relationships: number;
  average_health_score?: number;
}

export interface MeshTopology {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  metadata: TopologyMetadata;
  summary: TopologySummary;
}

export interface DomainTopology {
  domain: TopologyNode;
  relationships: TopologyEdge[];
  health_metrics: {
    health_score: number;
    policy_count: number;
    compliance_status: string;
    violation_count: number;
    is_active: boolean;
  };
}

export interface PolicyApplication {
  id: string;
  domain_id: string;
  domain_name: string;
  policy_id?: string;
  policy_name?: string;
  applied_by_id?: string;
  applied_by_email?: string;
  overrides: Record<string, any>;
  status: string;
  applied_at?: string;
  created_at: string;
  updated_at: string;
}

export interface ApplyPolicyRequest {
  policy_id: string;
  overrides?: Record<string, any>;
}

export interface ComplianceReport {
  id: string;
  domain_id: string;
  domain_name: string;
  asset_id?: string;
  asset_name?: string;
  compliance_status: string;
  violations: Record<string, any>;
  violation_count: number;
  generated_at: string;
  created_at: string;
  updated_at: string;
}

export interface CheckComplianceRequest {
  asset_id?: string;
}
