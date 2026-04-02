/**
 * Contract Lineage Visualization — Phase 37 (35.2)
 *
 * Renders lineage graph from GET /api/v1/contracts/{id}/lineage/visualization/
 * using React Flow + dagre auto-layout.  Replaces the original SVG-based
 * circular layout.
 */

import { useState, useCallback, useMemo } from 'react';
import { MarkerType, type Node, type Edge } from '@xyflow/react';
import { useContractLineageVisualization } from '../../contracts/hooks/useContracts';
import { GraphCanvas } from '../../../shared/components/GraphCanvas';
import { useDagreLayout } from '../../../shared/hooks/useDagreLayout';
import { ContractNode } from './nodes/ContractNode';
import styles from './ContractLineageVisualization.module.css';

const nodeTypes = { contractNode: ContractNode };

interface ContractLineageVisualizationProps {
  contractId: string;
  maxDepth?: number;
}

export function ContractLineageVisualization({
  contractId,
  maxDepth = 10,
}: ContractLineageVisualizationProps) {
  const [localMaxDepth, setLocalMaxDepth] = useState(maxDepth);
  const { data: lineage, isLoading, error, refetch } = useContractLineageVisualization(
    contractId,
    { format: 'json', max_depth: localMaxDepth },
  );

  const handleDepthChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setLocalMaxDepth(Number(e.target.value));
    },
    [],
  );

  // Transform API → React Flow format
  const rfNodes: Node[] = useMemo(
    () =>
      (lineage?.nodes ?? []).map((n) => ({
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
    [lineage?.nodes],
  );

  const rfEdges: Edge[] = useMemo(
    () =>
      (lineage?.links ?? []).map((l) => ({
        id: `${l.source}-${l.target}`,
        source: l.source,
        target: l.target,
        markerEnd: { type: MarkerType.ArrowClosed },
      })),
    [lineage?.links],
  );

  // Auto-layout via dagre
  const layoutedNodes = useDagreLayout(rfNodes, rfEdges, {
    direction: 'LR',
    nodeWidth: 160,
    nodeHeight: 70,
  });

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <h3>Lineage</h3>
        <div className={styles.controls}>
          <label className={styles.depthLabel}>
            Depth: {localMaxDepth}
            <input
              type="range"
              min={1}
              max={15}
              value={localMaxDepth}
              onChange={handleDepthChange}
              className={styles.depthSlider}
            />
          </label>
          {lineage && (
            <span className={styles.summary}>
              {lineage.nodes.length} nodes &middot; {lineage.links.length} links
            </span>
          )}
        </div>
      </div>

      <GraphCanvas
        nodes={layoutedNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        loading={isLoading}
        error={error ?? undefined}
        onRetry={() => refetch()}
      />
    </div>
  );
}
