/**
 * Lineage types
 * Aligned with backend GET /api/v1/contracts/{id}/lineage/visualization/?format=json
 * Response shape: { nodes, links } (backend uses "links" not "edges")
 */

export type ContractLineageNodeType = 'contract' | 'model' | 'field';

export interface ContractLineageNode {
  id: string;
  type: ContractLineageNodeType;
  name: string | null;
  label: string | null;
  contract_id?: string;
}

export interface ContractLineageLink {
  source: string;
  target: string;
}

export interface ContractLineageVisualization {
  nodes: ContractLineageNode[];
  links: ContractLineageLink[];
}

export interface ContractLineageVisualizationParams {
  format?: 'json' | 'dot' | 'mermaid';
  max_depth?: number;
}
