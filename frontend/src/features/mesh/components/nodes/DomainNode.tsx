/**
 * DomainNode — Phase 38 (36.2)
 * Custom React Flow node for mesh topology.
 */
import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Link } from 'react-router-dom';
import { healthColor } from '../../constants/healthThresholds';

interface DomainNodeData {
  name: string;
  status: string;
  health_score?: number;
  description?: string;
  id: string;
  [key: string]: unknown;
}

function DomainNodeInner({ data, selected }: NodeProps) {
  const d = data as unknown as DomainNodeData;
  const color = healthColor(d.health_score);

  return (
    <div style={{
      padding: '10px 14px',
      background: 'var(--color-background-primary, white)',
      border: `2px solid ${selected ? 'var(--color-primary, #0A1F44)' : color}`,
      borderRadius: 'var(--border-radius-md, 8px)',
      minWidth: 160,
      textAlign: 'center',
      boxShadow: selected ? 'var(--shadow-md)' : 'var(--shadow-sm)',
    }}>
      <Handle type="target" position={Position.Top} />
      <Handle type="target" position={Position.Left} id="left-target" />

      <div style={{ fontWeight: 600, fontSize: 'var(--font-size-sm, 14px)', marginBottom: 4 }}>
        {d.name}
      </div>

      <div style={{ display: 'flex', justifyContent: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{
          padding: '1px 6px',
          borderRadius: 'var(--border-radius-sm, 4px)',
          background: 'var(--color-neutral-100, #F5F5F5)',
          fontSize: 'var(--font-size-xs, 12px)',
        }}>
          {d.status}
        </span>
        {d.health_score != null && (
          <span style={{
            padding: '1px 6px',
            borderRadius: 'var(--border-radius-sm, 4px)',
            background: color,
            color: 'white',
            fontSize: 'var(--font-size-xs, 12px)',
            fontWeight: 600,
          }}>
            {d.health_score}
          </span>
        )}
      </div>

      {selected && (
        <Link
          to={`/mesh/domains/${d.id}`}
          style={{ fontSize: 'var(--font-size-xs, 12px)', color: 'var(--color-primary, #0A1F44)' }}
        >
          View Domain &rarr;
        </Link>
      )}

      <Handle type="source" position={Position.Bottom} />
      <Handle type="source" position={Position.Right} id="right-source" />
    </div>
  );
}

export const DomainNode = memo(DomainNodeInner);
