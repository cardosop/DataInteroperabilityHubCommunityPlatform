/**
 * Topology Visualization — Phase 38 (36.4)
 *
 * Renders mesh topology using React Flow + dagre auto-layout via GraphCanvas.
 * Replaces original SVG circular layout with DomainNode / RelationshipEdge.
 */

import { useMemo, useCallback } from 'react';
import { MarkerType, type Node, type Edge } from '@xyflow/react';
import { useMeshTopology } from '../hooks/useMesh';
import { GraphCanvas } from '../../../shared/components/GraphCanvas';
import { useDagreLayout } from '../../../shared/hooks/useDagreLayout';
import { EmptyState } from '../../../shared/components/EmptyState';
import { DomainNode } from './nodes/DomainNode';
import { RelationshipEdge } from './edges/RelationshipEdge';
import { DOMAIN_HEALTH_THRESHOLDS } from '../constants/healthThresholds';
import type { TopologyNode, TopologyEdge } from '../../../shared/types/mesh';
import styles from './TopologyVisualization.module.css';

const nodeTypes = { domainNode: DomainNode } as const;
const edgeTypes = { relationship: RelationshipEdge } as const;

function toRFNode(node: TopologyNode): Node {
  return {
    id: node.id,
    type: 'domainNode',
    data: {
      name: node.name,
      status: node.status,
      health_score: node.health_metrics?.health_score,
      description: node.description,
      id: node.id,
    },
    position: { x: 0, y: 0 },
  };
}

function toRFEdge(edge: TopologyEdge): Edge {
  return {
    id: `${edge.source}-${edge.target}`,
    source: edge.source,
    target: edge.target,
    type: 'relationship',
    data: { relationship_type: edge.type },
    markerEnd: { type: MarkerType.ArrowClosed },
  };
}

function healthLabel(score: number | undefined): string {
  if (score == null) return 'Unknown';
  if (score >= DOMAIN_HEALTH_THRESHOLDS.healthy) return 'Healthy';
  if (score >= DOMAIN_HEALTH_THRESHOLDS.warning) return 'Warning';
  return 'Critical';
}

export function TopologyVisualization() {
  const { data: topology, isLoading, error, refetch } = useMeshTopology(true);

  const rfNodes: Node[] = useMemo(
    () => (topology?.nodes ?? []).map(toRFNode),
    [topology?.nodes],
  );

  const rfEdges: Edge[] = useMemo(
    () => (topology?.edges ?? []).map(toRFEdge),
    [topology?.edges],
  );

  const layoutedNodes = useDagreLayout(rfNodes, rfEdges, {
    direction: 'TB',
    nodeWidth: 180,
    nodeHeight: 80,
  });

  const handleNodeClick = useCallback(
    () => {
      /* Selection is handled internally by React Flow */
    },
    [],
  );

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <h2 className={styles.title}>Mesh Topology</h2>

        {topology && (
          <div className={styles.summary}>
            <span>{topology.summary.total_domains} Domains</span>
            <span>{topology.summary.total_relationships} Relationships</span>
            {topology.summary.average_health_score != null && (
              <span>
                Avg Health: {Number(topology.summary.average_health_score).toFixed(1)}
                {' '}({healthLabel(topology.summary.average_health_score)})
              </span>
            )}
          </div>
        )}
      </div>

      {topology && topology.nodes.length === 0 ? (
        <EmptyState
          icon="🔗"
          title="No domains found"
          message="Create a data mesh domain to see the topology."
          data-testid="topology-empty-state"
        />
      ) : (
        <GraphCanvas
          nodes={layoutedNodes}
          edges={rfEdges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          loading={isLoading}
          error={error ?? undefined}
          onRetry={() => refetch()}
          onNodeClick={handleNodeClick}
        />
      )}

      <div className={styles.legend}>
        <span className={styles.legendTitle}>Legend</span>
        <div className={styles.legendItems}>
          <div className={styles.legendItem}>
            <span
              className={styles.legendDot}
              style={{ background: 'var(--color-success-500, #4CAF50)' }}
            />
            <span>≥ {DOMAIN_HEALTH_THRESHOLDS.healthy}</span>
          </div>
          <div className={styles.legendItem}>
            <span
              className={styles.legendDot}
              style={{ background: 'var(--color-warning-500, #FFC107)' }}
            />
            <span>{DOMAIN_HEALTH_THRESHOLDS.warning}–{DOMAIN_HEALTH_THRESHOLDS.healthy - 1}</span>
          </div>
          <div className={styles.legendItem}>
            <span
              className={styles.legendDot}
              style={{ background: 'var(--color-error-500, #F44336)' }}
            />
            <span>&lt; {DOMAIN_HEALTH_THRESHOLDS.warning}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
