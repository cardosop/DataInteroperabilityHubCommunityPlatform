/**
 * RelationshipEdge — Phase 38 (36.3)
 * Custom React Flow edge with midpoint label showing relationship type.
 */
import { memo } from 'react';
import {
  getBezierPath,
  EdgeLabelRenderer,
  type EdgeProps,
} from '@xyflow/react';

function RelationshipEdgeInner({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const label = (data as Record<string, unknown>)?.relationship_type as string | undefined;

  return (
    <>
      <path
        id={id}
        d={edgePath}
        fill="none"
        stroke="var(--color-neutral-400, #BDBDBD)"
        strokeWidth={1.5}
        markerEnd={markerEnd}
      />
      {label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              fontSize: 'var(--font-size-xs, 12px)',
              background: 'var(--color-neutral-50, #FAFAFA)',
              borderRadius: 'var(--border-radius-sm, 4px)',
              padding: '2px 6px',
              pointerEvents: 'none',
            }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export const RelationshipEdge = memo(RelationshipEdgeInner);
