"""
Version Comparison

Provides comparison functionality between dataset versions, including
schema diff visualization, data diff (statistical analysis), and side-by-side comparison.
"""
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from .models import Dataset
from .schema_evolution import SchemaEvolutionTracker, SchemaDiff, CompatibilityLevel


@dataclass
class DataDiff:
    """Statistical analysis of data differences between versions"""
    row_count_diff: int
    row_count_percent_change: float
    field_statistics: Dict[str, Dict[str, Any]]  # Field name -> statistics
    sample_data_diff: Dict[str, Any]  # Sample data comparison


@dataclass
class VersionComparison:
    """Complete comparison between two dataset versions"""
    old_version: Dataset
    new_version: Dataset
    schema_diff: SchemaDiff
    data_diff: Optional[DataDiff]
    side_by_side: Dict[str, Any]


class VersionComparisonService:
    """
    Service for comparing dataset versions.
    """
    
    @staticmethod
    def compare_versions(
        old_version: Dataset,
        new_version: Dataset,
        include_data_diff: bool = True
    ) -> VersionComparison:
        """
        Compare two dataset versions.
        
        Args:
            old_version: Old dataset version
            new_version: New dataset version
            include_data_diff: Whether to include data diff analysis
        
        Returns:
            VersionComparison object
        """
        # Calculate schema diff
        schema_diff = SchemaEvolutionTracker.calculate_schema_diff(
            old_version.schema_json or {},
            new_version.schema_json or {}
        )
        
        # Calculate data diff if requested
        data_diff = None
        if include_data_diff:
            data_diff = VersionComparisonService._calculate_data_diff(
                old_version,
                new_version
            )
        
        # Generate side-by-side comparison
        side_by_side = VersionComparisonService._generate_side_by_side(
            old_version,
            new_version,
            schema_diff
        )
        
        return VersionComparison(
            old_version=old_version,
            new_version=new_version,
            schema_diff=schema_diff,
            data_diff=data_diff,
            side_by_side=side_by_side
        )
    
    @staticmethod
    def _calculate_data_diff(
        old_version: Dataset,
        new_version: Dataset
    ) -> DataDiff:
        """
        Calculate statistical differences in data between versions.
        
        Args:
            old_version: Old dataset version
            new_version: New dataset version
        
        Returns:
            DataDiff object
        """
        old_row_count = old_version.row_count or 0
        new_row_count = new_version.row_count or 0
        
        row_count_diff = new_row_count - old_row_count
        row_count_percent_change = (
            (row_count_diff / old_row_count * 100) if old_row_count > 0 else 0.0
        )
        
        # Calculate field statistics
        field_statistics = {}
        
        old_fields = {f.get('name'): f for f in (old_version.schema_json or {}).get('fields', [])}
        new_fields = {f.get('name'): f for f in (new_version.schema_json or {}).get('fields', [])}
        
        all_field_names = set(old_fields.keys()) | set(new_fields.keys())
        
        for field_name in all_field_names:
            old_field = old_fields.get(field_name)
            new_field = new_fields.get(field_name)
            
            stats = {
                'exists_in_old': old_field is not None,
                'exists_in_new': new_field is not None,
            }
            
            if old_field and new_field:
                # Compare field properties
                old_type = old_field.get('data_type')
                new_type = new_field.get('data_type')
                stats['type_changed'] = old_type != new_type
                stats['old_type'] = old_type
                stats['new_type'] = new_type
                
                # Compare sample values
                old_samples = old_field.get('sample_values', [])
                new_samples = new_field.get('sample_values', [])
                stats['sample_values_changed'] = old_samples != new_samples
                stats['old_sample_count'] = len(old_samples)
                stats['new_sample_count'] = len(new_samples)
            
            field_statistics[field_name] = stats
        
        # Compare sample data
        old_sample_data = old_version.sample_data_json or []
        new_sample_data = new_version.sample_data_json or []
        
        sample_data_diff = {
            'old_sample_count': len(old_sample_data),
            'new_sample_count': len(new_sample_data),
            'samples_changed': old_sample_data != new_sample_data,
            'first_row_changed': (
                old_sample_data[0] != new_sample_data[0]
                if old_sample_data and new_sample_data
                else False
            )
        }
        
        return DataDiff(
            row_count_diff=row_count_diff,
            row_count_percent_change=row_count_percent_change,
            field_statistics=field_statistics,
            sample_data_diff=sample_data_diff
        )
    
    @staticmethod
    def _generate_side_by_side(
        old_version: Dataset,
        new_version: Dataset,
        schema_diff: SchemaDiff
    ) -> Dict[str, Any]:
        """
        Generate side-by-side comparison view.
        
        Args:
            old_version: Old dataset version
            new_version: New dataset version
            schema_diff: Schema difference
        
        Returns:
            Side-by-side comparison dictionary
        """
        old_fields = {f.get('name'): f for f in (old_version.schema_json or {}).get('fields', [])}
        new_fields = {f.get('name'): f for f in (new_version.schema_json or {}).get('fields', [])}
        
        all_field_names = sorted(set(old_fields.keys()) | set(new_fields.keys()))
        
        fields_comparison = []
        for field_name in all_field_names:
            old_field = old_fields.get(field_name)
            new_field = new_fields.get(field_name)
            
            fields_comparison.append({
                'field_name': field_name,
                'old': old_field,
                'new': new_field,
                'status': (
                    'unchanged' if old_field == new_field
                    else 'added' if not old_field
                    else 'removed' if not new_field
                    else 'modified'
                )
            })
        
        return {
            'metadata': {
                'old': {
                    'id': str(old_version.id),
                    'version': old_version.version,
                    'semantic_version': old_version.semantic_version,
                    'format': old_version.format,
                    'row_count': old_version.row_count,
                    'created_at': old_version.created_at.isoformat()
                },
                'new': {
                    'id': str(new_version.id),
                    'version': new_version.version,
                    'semantic_version': new_version.semantic_version,
                    'format': new_version.format,
                    'row_count': new_version.row_count,
                    'created_at': new_version.created_at.isoformat()
                }
            },
            'fields': fields_comparison,
            'schema_changes': {
                'compatibility_level': schema_diff.compatibility_level.value,
                'summary': schema_diff.summary,
                'changes': [
                    {
                        'type': change.change_type.value,
                        'field_name': change.field_name,
                        'description': change.description,
                        'breaking': change.breaking
                    }
                    for change in schema_diff.changes
                ]
            }
        }
    
    @staticmethod
    def visualize_schema_diff(
        schema_diff: SchemaDiff,
        format: str = "json"
    ) -> Any:
        """
        Visualize schema differences in various formats.
        
        Args:
            schema_diff: SchemaDiff object
            format: Output format (json, markdown, html)
        
        Returns:
            Visualization in requested format
        """
        if format == "json":
            return {
                'compatibility_level': schema_diff.compatibility_level.value,
                'summary': schema_diff.summary,
                'changes': [
                    {
                        'type': change.change_type.value,
                        'field_name': change.field_name,
                        'description': change.description,
                        'breaking': change.breaking,
                        'old_value': change.old_value,
                        'new_value': change.new_value
                    }
                    for change in schema_diff.changes
                ]
            }
        elif format == "markdown":
            lines = [
                f"# Schema Diff",
                f"",
                f"**Compatibility Level:** {schema_diff.compatibility_level.value}",
                f"",
                f"## Summary",
                f""
            ]
            
            for change_type, count in schema_diff.summary.items():
                if count > 0:
                    lines.append(f"- {change_type}: {count}")
            
            lines.extend([
                f"",
                f"## Changes",
                f""
            ])
            
            for change in schema_diff.changes:
                breaking_marker = " ⚠️ BREAKING" if change.breaking else ""
                lines.append(f"### {change.change_type.value}{breaking_marker}")
                lines.append(f"- **Field:** {change.field_name or 'N/A'}")
                lines.append(f"- **Description:** {change.description}")
                if change.old_value is not None:
                    lines.append(f"- **Old Value:** {change.old_value}")
                if change.new_value is not None:
                    lines.append(f"- **New Value:** {change.new_value}")
                lines.append("")
            
            return "\n".join(lines)
        elif format == "html":
            # Simple HTML visualization
            html = f"""
            <div class="schema-diff">
                <h2>Schema Diff</h2>
                <p><strong>Compatibility Level:</strong> {schema_diff.compatibility_level.value}</p>
                <h3>Summary</h3>
                <ul>
            """
            
            for change_type, count in schema_diff.summary.items():
                if count > 0:
                    html += f"<li>{change_type}: {count}</li>"
            
            html += """
                </ul>
                <h3>Changes</h3>
                <ul>
            """
            
            for change in schema_diff.changes:
                breaking_class = "breaking" if change.breaking else ""
                html += f"""
                    <li class="{breaking_class}">
                        <strong>{change.change_type.value}</strong>
                        {f' - {change.field_name}' if change.field_name else ''}
                        <br>{change.description}
                    </li>
                """
            
            html += """
                </ul>
            </div>
            """
            return html
        
        return schema_diff

    @staticmethod
    def visualize_data_diff(
        data_diff: DataDiff,
        format: str = "json"
    ) -> Any:
        """
        Visualize data differences in various formats.
        
        Args:
            data_diff: DataDiff object
            format: Output format (json, markdown, html)
        
        Returns:
            Visualization in requested format
        """
        if format == "json":
            return {
                'row_count_diff': data_diff.row_count_diff,
                'row_count_percent_change': data_diff.row_count_percent_change,
                'field_statistics': data_diff.field_statistics,
                'sample_data_diff': data_diff.sample_data_diff
            }
        elif format == "markdown":
            lines = [
                f"# Data Diff",
                f"",
                f"## Row Count Changes",
                f"",
                f"- **Difference:** {data_diff.row_count_diff:+d} rows",
                f"- **Percent Change:** {data_diff.row_count_percent_change:.2f}%",
                f"",
                f"## Field Statistics",
                f""
            ]
            
            for field_name, stats in data_diff.field_statistics.items():
                lines.append(f"### {field_name}")
                lines.append(f"- **Exists in Old:** {stats.get('exists_in_old', False)}")
                lines.append(f"- **Exists in New:** {stats.get('exists_in_new', False)}")
                if stats.get('type_changed'):
                    lines.append(f"- **Type Changed:** {stats.get('old_type')} → {stats.get('new_type')}")
                if stats.get('sample_values_changed'):
                    lines.append(f"- **Sample Values Changed:** Yes")
                lines.append("")
            
            lines.extend([
                f"## Sample Data Changes",
                f"",
                f"- **Old Sample Count:** {data_diff.sample_data_diff.get('old_sample_count', 0)}",
                f"- **New Sample Count:** {data_diff.sample_data_diff.get('new_sample_count', 0)}",
                f"- **Samples Changed:** {data_diff.sample_data_diff.get('samples_changed', False)}",
                f"- **First Row Changed:** {data_diff.sample_data_diff.get('first_row_changed', False)}"
            ])
            
            return "\n".join(lines)
        elif format == "html":
            html = f"""
            <div class="data-diff">
                <h2>Data Diff</h2>
                <h3>Row Count Changes</h3>
                <ul>
                    <li><strong>Difference:</strong> {data_diff.row_count_diff:+d} rows</li>
                    <li><strong>Percent Change:</strong> {data_diff.row_count_percent_change:.2f}%</li>
                </ul>
                <h3>Field Statistics</h3>
                <ul>
            """
            
            for field_name, stats in data_diff.field_statistics.items():
                html += f"""
                    <li>
                        <strong>{field_name}</strong>
                        <ul>
                            <li>Exists in Old: {stats.get('exists_in_old', False)}</li>
                            <li>Exists in New: {stats.get('exists_in_new', False)}</li>
                """
                if stats.get('type_changed'):
                    html += f"<li>Type Changed: {stats.get('old_type')} → {stats.get('new_type')}</li>"
                html += "</ul></li>"
            
            html += """
                </ul>
                <h3>Sample Data Changes</h3>
                <ul>
            """
            html += f"""
                    <li>Old Sample Count: {data_diff.sample_data_diff.get('old_sample_count', 0)}</li>
                    <li>New Sample Count: {data_diff.sample_data_diff.get('new_sample_count', 0)}</li>
                    <li>Samples Changed: {data_diff.sample_data_diff.get('samples_changed', False)}</li>
                    <li>First Row Changed: {data_diff.sample_data_diff.get('first_row_changed', False)}</li>
                </ul>
            </div>
            """
            return html
        
        return data_diff
    
    @staticmethod
    def visualize_version_diff(
        comparison: VersionComparison,
        format: str = "json"
    ) -> Any:
        """
        Visualize complete version diff (schema + data) in various formats.
        
        Args:
            comparison: VersionComparison object
            format: Output format (json, markdown, html)
        
        Returns:
            Complete visualization in requested format
        """
        if format == "json":
            result = {
                'metadata': comparison.side_by_side.get('metadata', {}),
                'schema_diff': VersionComparisonService.visualize_schema_diff(
                    comparison.schema_diff,
                    format="json"
                ),
                'side_by_side_fields': comparison.side_by_side.get('fields', [])
            }
            
            if comparison.data_diff:
                result['data_diff'] = VersionComparisonService.visualize_data_diff(
                    comparison.data_diff,
                    format="json"
                )
            
            return result
        elif format == "markdown":
            lines = [
                f"# Version Comparison",
                f"",
                f"## Metadata",
                f"",
                f"**Old Version:** {comparison.old_version.semantic_version} (v{comparison.old_version.version})",
                f"**New Version:** {comparison.new_version.semantic_version} (v{comparison.new_version.version})",
                f"",
                f"## Schema Diff",
                f"",
                VersionComparisonService.visualize_schema_diff(
                    comparison.schema_diff,
                    format="markdown"
                ),
                f""
            ]
            
            if comparison.data_diff:
                lines.extend([
                    f"## Data Diff",
                    f"",
                    VersionComparisonService.visualize_data_diff(
                        comparison.data_diff,
                        format="markdown"
                    ),
                    f""
                ])
            
            lines.extend([
                f"## Side-by-Side Field Comparison",
                f""
            ])
            
            for field in comparison.side_by_side.get('fields', []):
                status_emoji = {
                    'added': '➕',
                    'removed': '➖',
                    'modified': '🔄',
                    'unchanged': '✓'
                }.get(field.get('status', ''), '')
                
                lines.append(f"### {field.get('field_name')} {status_emoji}")
                lines.append(f"- **Status:** {field.get('status', 'unknown')}")
                if field.get('old'):
                    lines.append(f"- **Old:** {field.get('old')}")
                if field.get('new'):
                    lines.append(f"- **New:** {field.get('new')}")
                lines.append("")
            
            return "\n".join(lines)
        elif format == "html":
            html = f"""
            <div class="version-diff">
                <h1>Version Comparison</h1>
                <div class="metadata">
                    <h2>Metadata</h2>
                    <p><strong>Old Version:</strong> {comparison.old_version.semantic_version} (v{comparison.old_version.version})</p>
                    <p><strong>New Version:</strong> {comparison.new_version.semantic_version} (v{comparison.new_version.version})</p>
                </div>
                <div class="schema-diff">
                    {VersionComparisonService.visualize_schema_diff(comparison.schema_diff, format="html")}
                </div>
            """
            
            if comparison.data_diff:
                html += f"""
                <div class="data-diff">
                    {VersionComparisonService.visualize_data_diff(comparison.data_diff, format="html")}
                </div>
                """
            
            html += """
                <div class="side-by-side">
                    <h2>Side-by-Side Field Comparison</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>Field Name</th>
                                <th>Status</th>
                                <th>Old</th>
                                <th>New</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            
            for field in comparison.side_by_side.get('fields', []):
                html += f"""
                            <tr class="field-{field.get('status', 'unknown')}">
                                <td>{field.get('field_name')}</td>
                                <td>{field.get('status', 'unknown')}</td>
                                <td>{field.get('old', 'N/A')}</td>
                                <td>{field.get('new', 'N/A')}</td>
                            </tr>
                """
            
            html += """
                        </tbody>
                    </table>
                </div>
            </div>
            """
            return html
        
        return comparison

