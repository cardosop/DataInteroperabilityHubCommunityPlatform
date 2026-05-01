/**
 * Contract Lineage Visualization — Phase 37 (35.2)
 *
 * Renders lineage graph from GET /api/v1/contracts/{id}/lineage/visualization/
 * using React Flow + dagre auto-layout.  Replaces the original SVG-based
 * circular layout.
 */

import { useState, useCallback, useMemo } from 'react';
import { MarkerType, type Node, type Edge } from '@xyflow/react';
import {
  useContractLineageVisualization,
  useContractLineageDiff,
} from '../../contracts/hooks/useContracts';
import { EmptyState } from '../../../shared/components/EmptyState';
import { GraphCanvas } from '../../../shared/components/GraphCanvas';
import { useDagreLayout } from '../../../shared/hooks/useDagreLayout';
import { ContractNode } from './nodes/ContractNode';
import { LineageTimeTravelControls } from './LineageTimeTravelControls';
import { LineageDiffView } from './LineageDiffView';
import styles from './ContractLineageVisualization.module.css';

const nodeTypes = { contractNode: ContractNode };

interface ContractLineageVisualizationProps {
  contractId: string;
  maxDepth?: number;
  /**
   * Phase 228 F5 (228.F5.15) — pre-fetched version list. When omitted
   * the time-travel controls render with no version dropdown (the
   * date picker still works). Consumers wire this through their own
   * version-history hook.
   */
  availableVersions?: Array<{ version: number; label?: string }>;
}

export function ContractLineageVisualization({
  contractId,
  maxDepth = 10,
  availableVersions = [],
}: ContractLineageVisualizationProps) {
  const [localMaxDepth, setLocalMaxDepth] = useState(maxDepth);
  // Phase 228 F5 (228.F5.15) — point-in-time anchor.
  const [asOf, setAsOf] = useState<string | null>(null);
  const [version, setVersion] = useState<number | null>(null);
  // Phase 228 F5 (228.F5.13 + GAP-A5) — diff mode. When ON, the
  // visualization area swaps from the graph canvas to the
  // LineageDiffView, which renders {added/removed/changed/unchanged}
  // between the time-travel anchor and now.
  const [diffMode, setDiffMode] = useState(false);

  const { data: lineage, isLoading, error, refetch } = useContractLineageVisualization(
    contractId,
    {
      format: 'json',
      max_depth: localMaxDepth,
      ...(asOf ? { as_of: asOf } : {}),
      ...(version != null ? { version } : {}),
    },
  );

  // Phase 228 F5 (228.F5.13 + 228.F5.14) — when diff mode is ON and an
  // anchor is selected, fetch the diff between the anchor and now.
  const diffQuery = useContractLineageDiff(diffMode ? contractId : null, {
    ...(asOf ? { from: asOf } : {}),
    ...(version != null ? { from_version: version } : {}),
  });

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

  // Phase 227 Wave 1 (227.L5.7) — two-tier empty state.
  //
  // Tier 1 (``nodes.length <= 1``): the contract itself has no models
  // or fields declared — i.e. structureless. Surface a Schema-editor
  // deep-link so the user can fix it directly.
  // Tier 2 (``nodes.length > 1 && links.length === 0``): the contract
  // is structural but has no lineage edges. Existing copy stays.
  const isStructureless =
    lineage && !isLoading && !error && lineage.nodes.length <= 1;
  const showNoRelationshipsHint =
    lineage &&
    !isLoading &&
    !error &&
    lineage.links.length === 0 &&
    lineage.nodes.length > 1;

  return (
    <div className={styles.wrapper}>
      {/* Phase 228 F5 (228.F5.15) — time-travel controls above graph. */}
      <LineageTimeTravelControls
        asOf={asOf}
        version={version}
        availableVersions={availableVersions}
        onApply={({ asOf: nextAsOf, version: nextVersion }) => {
          setAsOf(nextAsOf);
          setVersion(nextVersion);
        }}
        onReset={() => {
          setAsOf(null);
          setVersion(null);
          setDiffMode(false);
        }}
      />

      {/* Phase 228 F5 (228.F5.13 + GAP-A5) — diff mode toggle. Visible
          only when an anchor is set; otherwise the toggle is a no-op. */}
      {(asOf || version != null) && (
        <div className={styles.diffModeRow}>
          <label
            htmlFor="lineage-diff-mode-toggle"
            className={styles.diffModeLabel}
          >
            <input
              id="lineage-diff-mode-toggle"
              data-testid="lineage-diff-mode-toggle"
              type="checkbox"
              checked={diffMode}
              onChange={(e) => setDiffMode(e.target.checked)}
              className={styles.diffModeCheckbox}
            />
            Show diff vs. live
          </label>
        </div>
      )}

      {diffMode ? (
        <LineageDiffView
          diff={diffQuery.data ?? null}
          isLoading={diffQuery.isLoading}
          error={(diffQuery.error as Error | null) ?? null}
        />
      ) : (
      <>
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

      {isStructureless ? (
        <EmptyState
          data-testid="contract-lineage-empty-structureless"
          title="No models or fields declared"
          message="This contract has no resolvable models or schema fields, so there is nothing to render lineage for. Open the Schema tab on the editor to add at least one model with one field."
          actionLabel="Open Schema editor"
          actionHref={`/contracts/${contractId}/edit?tab=schema`}
        />
      ) : showNoRelationshipsHint ? (
        <EmptyState
          data-testid="contract-lineage-empty"
          title="No lineage relationships in this contract"
          message="The normalized data contract has no declared contract, model, or field lineage, and no other contract in this tenant references it by name. Add lineage in the contract document or link related contracts to populate the graph."
        />
      ) : (
        <GraphCanvas
          nodes={layoutedNodes}
          edges={rfEdges}
          nodeTypes={nodeTypes}
          loading={isLoading}
          error={error ?? undefined}
          onRetry={() => refetch()}
        />
      )}
      </>
      )}
    </div>
  );
}
