"""
Impact Visualization

Generates visual representations of impact analysis results with severity highlighting
and export formats (JSON, CSV, DOT, Mermaid).
"""
from typing import Any, Dict, List, Optional
from .impact_analysis import ImpactNode, ImpactAnalyzer


class ImpactVisualizer:
    """
    Generates visual representations of impact analysis results.
    """
    
    @staticmethod
    def generate_impact_json(impact_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate impact graph in JSON format (for D3.js visualization).
        
        Includes severity-based color coding.
        """
        impact_graph = impact_result.get("impact_graph", {})
        
        nodes = []
        edges = []
        
        def process_node(node_data: Dict[str, Any], parent_id: Optional[str] = None):
            """Recursively process nodes"""
            node_id = node_data.get("resource_id")
            resource_type = node_data.get("resource_type", "CONTRACT")
            severity = node_data.get("severity", "LOW")
            impact_score = node_data.get("impact_score", 0.0)
            
            # Determine color based on severity
            color_map = {
                "CRITICAL": "#FF0000",  # Red
                "HIGH": "#FF8800",      # Orange
                "MEDIUM": "#FFAA00",    # Yellow
                "LOW": "#00AA00"        # Green
            }
            color = color_map.get(severity, "#CCCCCC")
            
            # Create node
            node = {
                "id": node_id,
                "type": resource_type,
                "label": node_data.get("metadata", {}).get("contract_name", node_id),
                "severity": severity,
                "impact_score": impact_score,
                "color": color,
                "depth": node_data.get("depth", 0),
                "metadata": node_data.get("metadata", {})
            }
            
            # Add model/field info if present
            if node_data.get("model_name"):
                node["model_name"] = node_data.get("model_name")
            if node_data.get("field_name"):
                node["field_name"] = node_data.get("field_name")
            
            nodes.append(node)
            
            # Add edge from parent
            if parent_id:
                edges.append({
                    "source": parent_id,
                    "target": node_id,
                    "type": "impact",
                    "severity": severity,
                    "color": color
                })
            
            # Process children
            for child in node_data.get("children", []):
                process_node(child, node_id)
        
        # Process root node
        if impact_graph:
            process_node(impact_graph)
        
        return {
            "nodes": nodes,
            "links": edges,
            "summary": impact_result.get("summary", {}),
            "source": impact_result.get("source", {})
        }
    
    @staticmethod
    def generate_impact_dot(impact_result: Dict[str, Any]) -> str:
        """
        Generate impact graph in DOT format (for Graphviz).
        
        Includes severity-based color coding.
        """
        graph_data = ImpactVisualizer.generate_impact_json(impact_result)
        
        lines = ["digraph ImpactAnalysis {"]
        lines.append("  rankdir=LR;")
        lines.append("  node [shape=box, style=rounded];")
        
        # Add nodes with colors
        for node in graph_data["nodes"]:
            node_id = node["id"].replace(":", "_").replace("-", "_")
            node_label = node.get("label", node.get("id", "Unknown"))
            severity = node.get("severity", "LOW")
            color = node.get("color", "#CCCCCC")
            
            # Escape label for DOT
            node_label = node_label.replace('"', '\\"')
            
            lines.append(f'  {node_id} [label="{node_label}\\n{severity}", fillcolor="{color}", style="filled,rounded"];')
        
        # Add edges with colors
        for edge in graph_data["links"]:
            source = edge["source"].replace(":", "_").replace("-", "_")
            target = edge["target"].replace(":", "_").replace("-", "_")
            color = edge.get("color", "#CCCCCC")
            
            lines.append(f'  {source} -> {target} [color="{color}", style="bold"];')
        
        lines.append("}")
        
        return "\n".join(lines)
    
    @staticmethod
    def generate_impact_mermaid(impact_result: Dict[str, Any]) -> str:
        """
        Generate impact graph in Mermaid format.
        
        Includes severity-based styling.
        """
        graph_data = ImpactVisualizer.generate_impact_json(impact_result)
        
        lines = ["graph LR"]
        
        # Add nodes with styling
        for node in graph_data["nodes"]:
            node_id = node["id"].replace(":", "_").replace("-", "_")
            node_label = node.get("label", node.get("id", "Unknown"))
            severity = node.get("severity", "LOW")
            
            # Mermaid styling based on severity
            if severity == "CRITICAL":
                lines.append(f'  {node_id}["{node_label}<br/>{severity}"]:::critical')
            elif severity == "HIGH":
                lines.append(f'  {node_id}["{node_label}<br/>{severity}"]:::high')
            elif severity == "MEDIUM":
                lines.append(f'  {node_id}["{node_label}<br/>{severity}"]:::medium')
            else:
                lines.append(f'  {node_id}["{node_label}<br/>{severity}"]:::low')
        
        # Add edges
        for edge in graph_data["links"]:
            source = edge["source"].replace(":", "_").replace("-", "_")
            target = edge["target"].replace(":", "_").replace("-", "_")
            
            lines.append(f'  {source} --> {target}')
        
        # Add style definitions
        lines.append("")
        lines.append("  classDef critical fill:#FF0000,stroke:#000,stroke-width:3px")
        lines.append("  classDef high fill:#FF8800,stroke:#000,stroke-width:2px")
        lines.append("  classDef medium fill:#FFAA00,stroke:#000,stroke-width:1px")
        lines.append("  classDef low fill:#00AA00,stroke:#000,stroke-width:1px")
        
        return "\n".join(lines)
    
    @staticmethod
    def generate_impact_csv(impact_result: Dict[str, Any]) -> str:
        """
        Generate impact report in CSV format.
        
        Returns CSV string with all affected resources and their impact scores.
        """
        import csv
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Resource Type",
            "Contract ID",
            "Contract Name",
            "Model Name",
            "Field Name",
            "Depth",
            "Impact Score",
            "Severity",
            "Criticality",
            "Usage Frequency"
        ])
        
        def write_node(node_data: Dict[str, Any]):
            """Recursively write nodes"""
            metadata = node_data.get("metadata", {})
            
            writer.writerow([
                node_data.get("resource_type", ""),
                node_data.get("contract_id", ""),
                metadata.get("contract_name", ""),
                node_data.get("model_name", ""),
                node_data.get("field_name", ""),
                node_data.get("depth", 0),
                f"{node_data.get('impact_score', 0.0):.2f}",
                node_data.get("severity", "LOW"),
                metadata.get("asset_criticality", "MEDIUM"),
                metadata.get("asset_usage_frequency", "MEDIUM")
            ])
            
            # Write children
            for child in node_data.get("children", []):
                write_node(child)
        
        # Write root node
        impact_graph = impact_result.get("impact_graph", {})
        if impact_graph:
            write_node(impact_graph)
        
        return output.getvalue()
    
    @staticmethod
    def generate_impact_paths(impact_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate impact paths (all paths from source to affected resources).
        
        Returns list of paths with severity information.
        """
        paths = []
        
        def extract_paths(node_data: Dict[str, Any], current_path: List[Dict[str, Any]]):
            """Recursively extract paths"""
            path_entry = {
                "resource_id": node_data.get("resource_id"),
                "contract_id": node_data.get("contract_id"),
                "contract_name": node_data.get("metadata", {}).get("contract_name"),
                "resource_type": node_data.get("resource_type"),
                "model_name": node_data.get("model_name"),
                "field_name": node_data.get("field_name"),
                "depth": node_data.get("depth", 0),
                "impact_score": node_data.get("impact_score", 0.0),
                "severity": node_data.get("severity", "LOW")
            }
            
            new_path = current_path + [path_entry]
            
            # If no children, this is a complete path
            if not node_data.get("children"):
                paths.append({
                    "path": new_path,
                    "length": len(new_path),
                    "max_severity": max((entry["severity"] for entry in new_path), key=lambda s: ["LOW", "MEDIUM", "HIGH", "CRITICAL"].index(s)),
                    "total_impact_score": sum(entry["impact_score"] for entry in new_path)
                })
            else:
                # Continue with children
                for child in node_data.get("children", []):
                    extract_paths(child, new_path)
        
        impact_graph = impact_result.get("impact_graph", {})
        if impact_graph:
            extract_paths(impact_graph, [])
        
        # Sort by severity and impact score
        paths.sort(key=lambda p: (
            ["LOW", "MEDIUM", "HIGH", "CRITICAL"].index(p["max_severity"]),
            -p["total_impact_score"]
        ), reverse=True)
        
        return paths

