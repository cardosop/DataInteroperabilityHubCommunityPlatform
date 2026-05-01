/**
 * LineageGraph — read-only lineage canvas (Phase 228.F1.13)
 *
 * Presentation component that renders a lineage graph without any
 * data-fetching concerns.  Two distinct call sites:
 *
 *   1. Contract editor's Lineage tab — wrapped by
 *      `ContractLineageVisualization` which adds depth controls + the
 *      `useContractLineageVisualization` data hook.
 *   2. Marketplace listing's Lineage tab (Phase 228.F1.10) — wrapped
 *      by `ListingLineagePanel` which adds the entitlement-aware
 *      detail toggle + the "Buy listing" CTA below the graph.
 *
 * Why a separate read-only component
 * ----------------------------------
 * The two call sites need the SAME visualization but different
 * surrounding chrome.  Keeping the canvas/transform/dagre logic in
 * one place avoids the "inline-different-graph-renderers" drift
 * that creeps in when each consumer rolls its own.  This is the F1.13
 * deliverable.
 */
import { useMemo } from 'react';
import { MarkerType, type Edge, type Node } from '@xyflow/react';

import { GraphCanvas } from '../../../shared/components/GraphCanvas';
import { useDagreLayout } from '../../../shared/hooks/useDagreLayout';
import { ContractNode } from './nodes/ContractNode';

/** Wire-format graph node — matches the API response. */
export interface LineageGraphNode {
  id: string;
  type: string;
  label?: string | null;
  name?: string | null;
  contract_id?: string;
}

/** Wire-format graph link — matches the API response. */
export interface LineageGraphLink {
  source: string;
  target: string;
  edge_type?: string;
  transformation_ref?: string;
  job_ref?: string;
}

const nodeTypes = { contractNode: ContractNode };

export interface LineageGraphProps {
  nodes: LineageGraphNode[];
  links: LineageGraphLink[];
  loading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  /**
   * Direction for the dagre layout.  Defaults to LR (left-to-right)
   * which mirrors the contract Lineage tab; the listing panel may
   * override to TB (top-to-bottom) for a more compact pre-purchase
   * preview.
   */
  layoutDirection?: 'LR' | 'TB';
}

export function LineageGraph({
  nodes,
  links,
  loading = false,
  error = null,
  onRetry,
  layoutDirection = 'LR',
}: LineageGraphProps) {
  const rfNodes: Node[] = useMemo(
    () =>
      nodes.map((n) => ({
        id: n.id,
        type: 'contractNode',
        data: {
          type: n.type,
          name: n.name ?? n.label ?? n.id,
          id: n.id,
          contract_id: n.contract_id,
        },
        position: { x: 0, y: 0 },
      })),
    [nodes],
  );

  const rfEdges: Edge[] = useMemo(
    () =>
      links.map((l) => ({
        id: `${l.source}-${l.target}`,
        source: l.source,
        target: l.target,
        // Show edge_type as a label when present (e.g. "transformation",
        // "reference") so the consumer can tell at a glance how each
        // hop was created.  No transformation_ref / job_ref leaks via
        // the label — those are surfaced via the full-tier tooltip
        // panel (out of scope for this read-only canvas).
        label: l.edge_type ?? undefined,
        markerEnd: { type: MarkerType.ArrowClosed },
      })),
    [links],
  );

  const layoutedNodes = useDagreLayout(rfNodes, rfEdges, {
    direction: layoutDirection,
    nodeWidth: 160,
    nodeHeight: 70,
  });

  return (
    <GraphCanvas
      nodes={layoutedNodes}
      edges={rfEdges}
      nodeTypes={nodeTypes}
      loading={loading}
      error={error ?? undefined}
      onRetry={onRetry}
    />
  );
}
