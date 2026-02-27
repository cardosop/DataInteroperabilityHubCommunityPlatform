/**
 * Topology Visualization Component
 * Minimal viable graph visualization for mesh topology
 */

import { useEffect, useRef, useState } from 'react';
import { useMeshTopology } from '../hooks/useMesh';
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import type { TopologyNode, TopologyEdge } from '../../../shared/types/mesh';
import './TopologyVisualization.css';

interface NodePosition {
  x: number;
  y: number;
}

export function TopologyVisualization() {
  const { data: topology, isLoading, error, refetch } = useMeshTopology(true);
  const svgRef = useRef<SVGSVGElement>(null);
  const [nodePositions, setNodePositions] = useState<Map<string, NodePosition>>(new Map());
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  useEffect(() => {
    if (!topology || !svgRef.current) return;

    const svg = svgRef.current;
    const width = svg.clientWidth || 1200;
    const height = svg.clientHeight || 800;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.3;

    // Calculate positions in a circular layout
    const positions = new Map<string, NodePosition>();
    const nodes = topology.nodes;
    const angleStep = (2 * Math.PI) / nodes.length;

    nodes.forEach((node, index) => {
      const angle = index * angleStep;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      positions.set(node.id, { x, y });
    });

    setNodePositions(positions);
  }, [topology]);

  if (isLoading) {
    return <LoadingSpinner message="Loading topology..." />;
  }

  if (error || !topology) {
    return <ErrorDisplay error={error} title="Failed to load topology" onRetry={() => refetch()} />;
  }

  const renderEdge = (edge: TopologyEdge) => {
    const sourcePos = nodePositions.get(edge.source);
    const targetPos = nodePositions.get(edge.target);
    
    if (!sourcePos || !targetPos) return null;

    return (
      <line
        key={`${edge.source}-${edge.target}`}
        x1={sourcePos.x}
        y1={sourcePos.y}
        x2={targetPos.x}
        y2={targetPos.y}
        stroke="#999"
        strokeWidth={2}
        strokeOpacity={0.5}
        markerEnd="url(#arrowhead)"
      />
    );
  };

  const renderNode = (node: TopologyNode) => {
    const pos = nodePositions.get(node.id);
    if (!pos) return null;

    const isSelected = selectedNode === node.id;
    const healthScore = node.health_metrics?.health_score ?? 0;
    const nodeColor = healthScore >= 80 ? '#4caf50' : healthScore >= 60 ? '#ff9800' : '#f44336';

    return (
      <g key={node.id}>
        <circle
          cx={pos.x}
          cy={pos.y}
          r={isSelected ? 25 : 20}
          fill={nodeColor}
          stroke={isSelected ? '#0066cc' : '#333'}
          strokeWidth={isSelected ? 3 : 2}
          onClick={() => setSelectedNode(isSelected ? null : node.id)}
          style={{ cursor: 'pointer' }}
        />
        <text
          x={pos.x}
          y={pos.y + 35}
          textAnchor="middle"
          fontSize="12"
          fill="#333"
          fontWeight={isSelected ? 'bold' : 'normal'}
        >
          {node.name}
        </text>
        {node.health_metrics && (
          <text
            x={pos.x}
            y={pos.y + 50}
            textAnchor="middle"
            fontSize="10"
            fill="#666"
          >
            Health: {healthScore}
          </text>
        )}
      </g>
    );
  };

  return (
    <div className="topology-visualization">
      <div className="topology-header">
        <h2>Mesh Topology</h2>
        <div className="topology-summary">
          <span>{topology.summary.total_domains} Domains</span>
          <span>{topology.summary.total_relationships} Relationships</span>
          {topology.summary.average_health_score != null && (
            <span>Avg Health: {Number(topology.summary.average_health_score).toFixed(1)}</span>
          )}
        </div>
      </div>

      <div className="topology-canvas">
        <svg ref={svgRef} width="100%" height="800" viewBox="0 0 1200 800">
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="10"
              refX="9"
              refY="3"
              orient="auto"
            >
              <polygon points="0 0, 10 3, 0 6" fill="#999" />
            </marker>
          </defs>
          
          {/* Render edges first (behind nodes) */}
          {topology.edges.map(renderEdge)}
          
          {/* Render nodes */}
          {topology.nodes.map(renderNode)}
        </svg>
      </div>

      {selectedNode && (
        <div className="node-details">
          <h3>Node Details</h3>
          {(() => {
            const node = topology.nodes.find(n => n.id === selectedNode);
            if (!node) return null;
            return (
              <div>
                <p><strong>Name:</strong> {node.name}</p>
                {node.description && <p><strong>Description:</strong> {node.description}</p>}
                <p><strong>Status:</strong> {node.status}</p>
                {node.health_metrics && (
                  <>
                    <p><strong>Health Score:</strong> {node.health_metrics.health_score}</p>
                    <p><strong>Compliance:</strong> {node.health_metrics.compliance_status}</p>
                    <p><strong>Violations:</strong> {node.health_metrics.violation_count}</p>
                  </>
                )}
              </div>
            );
          })()}
        </div>
      )}

      <div className="topology-legend">
        <h4>Legend</h4>
        <div className="legend-items">
          <div className="legend-item">
            <div className="legend-color" style={{ background: '#4caf50' }}></div>
            <span>Health ≥ 80</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ background: '#ff9800' }}></div>
            <span>Health 60-79</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ background: '#f44336' }}></div>
            <span>Health &lt; 60</span>
          </div>
        </div>
      </div>
    </div>
  );
}
