/**
 * ContractNode — Phase 37 (35.1)
 *
 * Custom React Flow node for lineage graph.
 * Color-coded by type, truncated label, link to contract on select.
 */

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Link } from 'react-router-dom';

interface ContractNodeData {
  type: string;
  name: string;
  id: string;
  contract_id?: string;
  [key: string]: unknown;
}

const TYPE_COLORS: Record<string, string> = {
  contract: 'var(--color-secondary-500, #2F6BFF)',
  model: 'var(--color-success-500, #4CAF50)',
  field: 'var(--color-warning-500, #FFC107)',
};

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max) + '\u2026' : s;
}

function ContractNodeInner({ data, selected }: NodeProps) {
  const nodeData = data as unknown as ContractNodeData;
  const color = TYPE_COLORS[nodeData.type] ?? 'var(--color-neutral-500, #9E9E9E)';

  return (
    <div
      style={{
        padding: '8px 12px',
        background: 'var(--color-background-primary, white)',
        border: `2px solid ${selected ? 'var(--color-primary, #0A1F44)' : color}`,
        borderRadius: 'var(--border-radius-md, 8px)',
        width: 160,
        minHeight: 70,
        textAlign: 'center',
        boxShadow: selected ? 'var(--shadow-md)' : 'var(--shadow-sm)',
      }}
    >
      <Handle type="target" position={Position.Left} />

      <div
        style={{
          display: 'inline-block',
          padding: '1px 6px',
          borderRadius: 'var(--border-radius-sm, 4px)',
          background: color,
          color: 'white',
          fontSize: 'var(--font-size-xs, 12px)',
          fontWeight: 600,
          textTransform: 'uppercase',
          marginBottom: 4,
        }}
      >
        {nodeData.type}
      </div>

      <div
        style={{ fontSize: 'var(--font-size-sm, 14px)', fontWeight: 500 }}
        title={nodeData.name}
      >
        {truncate(nodeData.name, 20)}
      </div>

      {selected && nodeData.contract_id && (
        <Link
          to={`/contracts/${nodeData.contract_id}`}
          style={{
            display: 'block',
            marginTop: 6,
            fontSize: 'var(--font-size-xs, 12px)',
            color: 'var(--color-primary, #0A1F44)',
          }}
        >
          Open Contract &rarr;
        </Link>
      )}

      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export const ContractNode = memo(ContractNodeInner);
