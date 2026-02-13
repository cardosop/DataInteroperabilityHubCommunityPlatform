/**
 * Contract Lineage Visualization
 * Renders lineage graph from GET /api/v1/contracts/{id}/lineage/visualization/
 * Aligned with mesh TopologyVisualization (nodes + links, circular layout).
 * No stub data; uses real API only.
 */

import { useEffect, useRef, useState } from 'react';
import { useContractLineageVisualization } from '../../contracts/hooks/useContracts';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import type { ContractLineageNode, ContractLineageLink } from '../../../shared/types/lineage';
import './ContractLineageVisualization.css';

interface NodePosition {
  x: number;
  y: number;
}

interface ContractLineageVisualizationProps {
  contractId: string;
  maxDepth?: number;
}

export function ContractLineageVisualization({ contractId, maxDepth = 10 }: ContractLineageVisualizationProps) {
  const { data: lineage, isLoading, error, refetch } = useContractLineageVisualization(contractId, {
    format: 'json',
    max_depth: maxDepth,
  });
  const svgRef = useRef<SVGSVGElement>(null);
  const [nodePositions, setNodePositions] = useState<Map<string, NodePosition>>(new Map());
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  useEffect(() => {
    if (!lineage?.nodes.length || !svgRef.current) return;

    const svg = svgRef.current;
    const width = svg.clientWidth || 1000;
    const height = svg.clientHeight || 600;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.35;

    const positions = new Map<string, NodePosition>();
    const nodes = lineage.nodes;
    const angleStep = nodes.length > 0 ? (2 * Math.PI) / nodes.length : 0;

    nodes.forEach((node, index) => {
      const angle = index * angleStep - Math.PI / 2;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      positions.set(node.id, { x, y });
    });

    setNodePositions(positions);
  }, [lineage]);

  if (isLoading) {
    return <LoadingSpinner message="Loading lineage..." />;
  }

  if (error || !lineage) {
    return (
      <ErrorDisplay
        error={error ?? new Error('Failed to load lineage')}
        title="Failed to load lineage"
        onRetry={() => refetch()}
      />
    );
  }

  const renderLink = (link: ContractLineageLink) => {
    const sourcePos = nodePositions.get(link.source);
    const targetPos = nodePositions.get(link.target);
    if (!sourcePos || !targetPos) return null;

    return (
      <line
        key={`${link.source}-${link.target}`}
        x1={sourcePos.x}
        y1={sourcePos.y}
        x2={targetPos.x}
        y2={targetPos.y}
        stroke="#999"
        strokeWidth={2}
        strokeOpacity={0.5}
        markerEnd="url(#lineage-arrowhead)"
      />
    );
  };

  const nodeColor = (type: string) => {
    switch (type) {
      case 'contract':
        return '#2196f3';
      case 'model':
        return '#4caf50';
      case 'field':
        return '#ff9800';
      default:
        return '#9e9e9e';
    }
  };

  const renderNode = (node: ContractLineageNode) => {
    const pos = nodePositions.get(node.id);
    if (!pos) return null;

    const isSelected = selectedNode === node.id;
    const fill = nodeColor(node.type);
    const label = node.label ?? node.name ?? node.id;

    return (
      <g key={node.id}>
        <circle
          cx={pos.x}
          cy={pos.y}
          r={isSelected ? 22 : 18}
          fill={fill}
          stroke={isSelected ? '#1565c0' : '#333'}
          strokeWidth={isSelected ? 3 : 2}
          onClick={() => setSelectedNode(isSelected ? null : node.id)}
          style={{ cursor: 'pointer' }}
        />
        <text
          x={pos.x}
          y={pos.y + 32}
          textAnchor="middle"
          fontSize="11"
          fill="#333"
          fontWeight={isSelected ? 'bold' : 'normal'}
        >
          {label}
        </text>
        <text
          x={pos.x}
          y={pos.y + 46}
          textAnchor="middle"
          fontSize="9"
          fill="#666"
        >
          {node.type}
        </text>
      </g>
    );
  };

  return (
    <div className="contract-lineage-visualization">
      <div className="lineage-header">
        <h3>Lineage</h3>
        <div className="lineage-summary">
          <span>{lineage.nodes.length} nodes</span>
          <span>{lineage.links.length} links</span>
        </div>
      </div>

      <div className="lineage-canvas">
        <svg ref={svgRef} width="100%" height="600" viewBox="0 0 1000 600">
          <defs>
            <marker
              id="lineage-arrowhead"
              markerWidth="10"
              markerHeight="10"
              refX="9"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 10 3, 0 6" fill="#999" />
            </marker>
          </defs>
          {lineage.links.map(renderLink)}
          {lineage.nodes.map(renderNode)}
        </svg>
      </div>

      {selectedNode && (
        <div className="lineage-node-details">
          <h4>Node</h4>
          {(() => {
            const node = lineage.nodes.find((n) => n.id === selectedNode);
            if (!node) return null;
            return (
              <div>
                <p><strong>Type:</strong> {node.type}</p>
                <p><strong>Name:</strong> {node.name ?? '—'}</p>
                <p><strong>ID:</strong> {node.id}</p>
                {node.contract_id != null && (
                  <p><strong>Contract:</strong> {node.contract_id}</p>
                )}
              </div>
            );
          })()}
        </div>
      )}

      <div className="lineage-legend">
        <h4>Legend</h4>
        <div className="legend-items">
          <div className="legend-item">
            <div className="legend-color" style={{ background: '#2196f3' }} />
            <span>Contract</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ background: '#4caf50' }} />
            <span>Model</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ background: '#ff9800' }} />
            <span>Field</span>
          </div>
        </div>
      </div>
    </div>
  );
}
