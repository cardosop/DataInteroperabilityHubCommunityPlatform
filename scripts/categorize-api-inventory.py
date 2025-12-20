#!/usr/bin/env python3
"""
Comprehensive API Categorization Script

This script categorizes existing APIs by:
1. Feature type (Core, Feature, New Feature)
2. Status (Working, Broken, Deprecated)
3. Completeness (Complete, Incomplete)

It analyzes the codebase to determine actual implementation status.
"""

import re
import ast
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime
import json

@dataclass
class APICategory:
    """API categorization information"""
    feature_type: str  # Core, Feature, New Feature
    status: str  # Working, Broken, Deprecated
    completeness: str  # Complete, Incomplete
    notes: List[str] = field(default_factory=list)
    methods_implemented: Set[str] = field(default_factory=set)
    methods_expected: Set[str] = field(default_factory=set)
    has_schema: bool = False
    has_tests: bool = False
    is_deprecated: bool = False

class APICategorizer:
    """Categorizes APIs from inventory"""
    
    def __init__(self, hub_dir: Path, inventory_file: Path):
        self.hub_dir = hub_dir
        self.inventory_file = inventory_file
        self.categories: Dict[str, APICategory] = {}
        
        # Feature type mappings
        self.core_features = {
            'auth', 'authentication', 'login', 'logout', 'register', 'token', 'refresh',
            'assets', 'asset', 'contracts', 'contract', 'datasets', 'dataset',
            'users', 'user', 'tenants', 'tenant', 'roles', 'role',
            'marketplace', 'listings', 'orders', 'entitlements',
            'compliance', 'dq', 'data-quality', 'jobs', 'job',
            'files', 'file', 'audit', 'health'
        }
        
        self.feature_features = {
            'scheduled-ingestion', 'scheduled_ingestion', 'scheduled-ingestions',
            'observability', 'metrics', 'governance', 'search',
            'semantic', 'sparql', 'webhooks', 'webhook', 'analytics'
        }
        
        self.new_features = {
            'ai', 'ml', 'machine-learning', 'natural-language', 'nlp',
            'schema-matching', 'recommendations', 'classification',
            'transformation', 'transform', 'pipeline', 'pipelines',
            'ratings', 'reviews', 'comments', 'communities', 'social',
            'data-mesh', 'mesh', 'domains', 'federated',
            'virtualization', 'virtual', 'federation',
            'connectors', 'connector', 'plugins', 'plugin',
            'reverse-etl', 'bi-integration', 'cicd'
        }
        
        # Expected CRUD methods for standard resources
        self.expected_methods = {
            'list': {'GET'},
            'create': {'POST'},
            'retrieve': {'GET'},
            'update': {'PUT'},
            'partial_update': {'PATCH'},
            'destroy': {'DELETE'}
        }
    
    def categorize_all(self) -> Dict[str, APICategory]:
        """Categorize all APIs from inventory"""
        # Parse inventory file
        endpoints = self._parse_inventory()
        
        print(f"Found {len(endpoints)} endpoints to categorize")
        
        for endpoint_path, endpoint_info in endpoints.items():
            category = self._categorize_endpoint(endpoint_path, endpoint_info)
            if category:
                self.categories[endpoint_path] = category
        
        return self.categories
    
    def _parse_inventory(self) -> Dict[str, Dict]:
        """Parse the inventory markdown file"""
        endpoints = {}
        
        try:
            content = self.inventory_file.read_text(encoding='utf-8')
            
            # Try to parse table format first (more reliable)
            # Pattern: | Method | Path | View | Action | Description |
            table_pattern = re.compile(
                r'\| (GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+\|\s+`([^`]+)`\s+\|\s+`?([^|`]+)`?\s+\|\s+([^|]+)\s+\|',
                re.MULTILINE
            )
            
            for match in table_pattern.finditer(content):
                method = match.group(1).upper()
                path = match.group(2).strip()
                view = match.group(3).strip()
                action = match.group(4).strip()
                
                # Skip header rows
                if method in ['METHOD', 'GET', 'POST'] and 'Path' in path:
                    continue
                
                key = f"{method}:{path}"
                
                # Extract view class from view string
                view_class = None
                if '.' in view:
                    view_class = view.split('.')[0]
                elif 'ViewSet' in view or 'View' in view:
                    view_class = view
                
                # Determine source file from view/app name
                source_file = self._determine_source_file(path, view_class)
                
                endpoints[key] = {
                    'method': method,
                    'path': path,
                    'view_class': view_class,
                    'view_name': view if not view_class else None,
                    'source_file': source_file,
                    'description': action if action and action != '-' else None,
                    'action': action
                }
            
            # Fallback: parse section format if table not found
            if not endpoints:
                endpoint_pattern = re.compile(
                    r'####\s+(\w+)\s+(.+?)\n\n(.*?)(?=####|##|---\n\n|$)',
                    re.DOTALL
                )
                
                for match in endpoint_pattern.finditer(content):
                    method = match.group(1).upper()
                    path = match.group(2).strip().rstrip('/')
                    details = match.group(3)
                    
                    if path.startswith('**') or 'Count:' in path:
                        continue
                    
                    key = f"{method}:{path}"
                    
                    view_class_match = re.search(r'\*\*View Class:\*\*\s*`([^`]+)`', details)
                    view_name_match = re.search(r'\*\*View Name:\*\*\s*`([^`]+)`', details)
                    source_file_match = re.search(r'\*\*Source File:\*\*\s*`([^`]+)`', details)
                    description_match = re.search(r'\*\*Description:\*\*\s*(.+?)(?:\n|$)', details)
                    
                    endpoints[key] = {
                        'method': method,
                        'path': path,
                        'view_class': view_class_match.group(1) if view_class_match else None,
                        'view_name': view_name_match.group(1) if view_name_match else None,
                        'source_file': source_file_match.group(1) if source_file_match else None,
                        'description': description_match.group(1).strip() if description_match else None
                    }
        
        except Exception as e:
            print(f"Error parsing inventory: {e}")
            import traceback
            traceback.print_exc()
        
        return endpoints
    
    def _determine_source_file(self, path: str, view_class: Optional[str]) -> Optional[str]:
        """Determine source file from path and view class"""
        # Extract app name from path
        path_parts = path.split('/')
        if len(path_parts) > 3 and path_parts[1] == 'api' and path_parts[2] == 'v1':
            app_name = path_parts[3]
            
            # Map app names to file paths
            app_mapping = {
                'assets': 'apps/assets/urls.py',
                'contracts': 'apps/contracts/urls.py',
                'datasets': 'apps/datasets/urls.py',
                'auth': 'apps/auth/urls.py',
                'users': 'apps/users/urls.py',
                'tenants': 'apps/tenants/urls.py',
                'jobs': 'apps/jobs/urls.py',
                'marketplace': 'apps/marketplace/urls.py',
                'compliance': 'apps/compliance/urls.py',
                'dq': 'apps/dq/urls.py',
                'scheduled-ingestions': 'apps/scheduled_ingestion/urls.py',
                'search': 'apps/search/urls.py',
                'semantic': 'apps/semantic/urls.py',
                'webhooks': 'apps/webhooks/urls.py',
                'audit': 'apps/audit/urls.py',
                'files': 'apps/files/urls.py',
                'governance': 'apps/governance/urls.py',
                'observability': 'apps/observability/urls.py',
                'analytics': 'apps/api/analytics/urls.py',
            }
            
            if app_name in app_mapping:
                return app_mapping[app_name]
        
        return None
    
    def _categorize_endpoint(self, endpoint_key: str, endpoint_info: Dict) -> Optional[APICategory]:
        """Categorize a single endpoint"""
        path = endpoint_info['path']
        method = endpoint_info['method']
        view_class = endpoint_info.get('view_class')
        source_file = endpoint_info.get('source_file')
        
        # Determine feature type
        feature_type = self._determine_feature_type(path)
        
        # Determine status
        status = self._determine_status(path, view_class, source_file)
        
        # Determine completeness
        completeness = self._determine_completeness(path, view_class, source_file, method)
        
        # Check for schema
        has_schema = self._check_schema(path, source_file)
        
        # Check for tests
        has_tests = self._check_tests(path, source_file)
        
        # Check if deprecated
        is_deprecated = self._check_deprecated(path, view_class, source_file)
        
        category = APICategory(
            feature_type=feature_type,
            status=status,
            completeness=completeness,
            has_schema=has_schema,
            has_tests=has_tests,
            is_deprecated=is_deprecated
        )
        
        # Add notes
        if not has_schema:
            category.notes.append("Missing OpenAPI schema definition")
        if not has_tests:
            category.notes.append("No tests found")
        if is_deprecated:
            category.notes.append("Marked as deprecated")
        
        return category
    
    def _determine_feature_type(self, path: str) -> str:
        """Determine if endpoint is Core, Feature, or New Feature"""
        path_lower = path.lower()
        
        # Check for new features first (most specific)
        for new_feature in self.new_features:
            if new_feature in path_lower:
                return "New Feature"
        
        # Check for feature features
        for feature in self.feature_features:
            if feature in path_lower:
                return "Feature"
        
        # Check for core features
        for core in self.core_features:
            if core in path_lower:
                return "Core"
        
        # Default to Core for unknown
        return "Core"
    
    def _determine_status(self, path: str, view_class: Optional[str], source_file: Optional[str]) -> str:
        """Determine if endpoint is Working, Broken, or Deprecated"""
        # Check if deprecated
        if self._check_deprecated(path, view_class, source_file):
            return "Deprecated"
        
        # Check if view class exists and is implemented
        if view_class and source_file:
            view_file = self._find_view_file(source_file, view_class)
            if view_file and view_file.exists():
                # Check if view is properly implemented
                if self._check_view_implementation(view_file, view_class):
                    return "Working"
                else:
                    return "Broken"
        
        # If we can't determine, assume working if file exists
        if source_file:
            file_path = self.hub_dir / source_file
            if file_path.exists():
                return "Working"
        
        return "Unknown"
    
    def _determine_completeness(self, path: str, view_class: Optional[str], source_file: Optional[str], method: str) -> str:
        """Determine if endpoint is Complete or Incomplete"""
        # For ViewSets, check if the specific action is implemented
        if view_class and 'ViewSet' in view_class:
            view_file = self._find_view_file(source_file, view_class)
            if view_file and view_file.exists():
                try:
                    content = view_file.read_text(encoding='utf-8')
                    
                    # Extract action name from path (for custom actions)
                    action = self._extract_action_from_path(path, method)
                    
                    # Check if this is a custom action (has action name in path)
                    if action and action not in ['list', 'create', 'retrieve', 'update', 'partial_update', 'destroy']:
                        # Look for @action decorator with this action name
                        action_pattern = rf'@action[^\n]*\n\s*def\s+{action}\s*\('
                        if re.search(action_pattern, content, re.MULTILINE):
                            # Check if method has implementation (not just pass)
                            method_match = re.search(rf'def\s+{action}\s*\([^)]*\)\s*:(.*?)(?=\n\s+def\s+|\n\s+@|\nclass\s+|$)', content, re.DOTALL)
                            if method_match:
                                method_body = method_match.group(1).strip()
                                if method_body and method_body not in ['pass', '...', 'raise NotImplementedError']:
                                    return "Complete"
                    
                    # For standard CRUD actions, check if the ViewSet has the method
                    # List endpoint (no ID in path, GET method)
                    if '{id}' not in path and '{pk}' not in path and method == 'GET':
                        if 'def list' in content:
                            return "Complete"
                    # Create endpoint (no ID, POST method)
                    elif '{id}' not in path and '{pk}' not in path and method == 'POST':
                        if 'def create' in content:
                            return "Complete"
                    # Detail endpoints (has ID in path)
                    elif '{id}' in path or '{pk}' in path:
                        if method == 'GET' and 'def retrieve' in content:
                            return "Complete"
                        elif method == 'PUT' and 'def update' in content:
                            return "Complete"
                        elif method == 'PATCH' and 'def partial_update' in content:
                            return "Complete"
                        elif method == 'DELETE' and 'def destroy' in content:
                            return "Complete"
                    
                    # If ViewSet class exists and is a ModelViewSet, it has all standard methods
                    if 'ModelViewSet' in content or 'viewsets.ModelViewSet' in content:
                        # ModelViewSet has all CRUD methods by default
                        return "Complete"
                    
                    # If ViewSet exists, assume methods are implemented (conservative)
                    if f'class {view_class}' in content:
                        return "Complete"
                except Exception as e:
                    print(f"Error checking completeness for {path}: {e}")
        
        # For function-based views, check if function exists
        if view_class and source_file and 'ViewSet' not in str(view_class):
            view_file = self._find_view_file(source_file, view_class)
            if view_file and view_file.exists():
                try:
                    content = view_file.read_text(encoding='utf-8')
                    # Check if function is defined
                    func_name = view_class.split('.')[-1] if '.' in view_class else view_class
                    if f'def {func_name}' in content or f'def {func_name.lower()}' in content:
                        return "Complete"
                except Exception:
                    pass
        
        # If view file exists and endpoint is documented, assume complete
        if view_class and source_file:
            view_file = self._find_view_file(source_file, view_class)
            if view_file and view_file.exists():
                return "Complete"
        
        return "Incomplete"
    
    def _extract_action_from_path(self, path: str, method: str) -> Optional[str]:
        """Extract action name from path"""
        # Remove base path
        path_parts = path.split('/')
        if len(path_parts) > 3:
            # Get the last meaningful part
            action_part = path_parts[-1].rstrip('/')
            if action_part and '{' not in action_part:
                # Convert kebab-case to snake_case
                action = action_part.replace('-', '_')
                return action
        
        return None
    
    def _check_schema(self, path: str, source_file: Optional[str]) -> bool:
        """Check if endpoint has OpenAPI schema definition"""
        # Look for serializer files
        if source_file:
            app_dir = self.hub_dir / Path(source_file).parent
            serializer_file = app_dir / 'serializers.py'
            
            if serializer_file.exists():
                # Check if serializer is properly defined
                content = serializer_file.read_text(encoding='utf-8')
                # Look for serializer classes
                if re.search(r'class\s+\w+Serializer', content):
                    return True
        
        # Also check if view class has serializer attribute
        if source_file:
            app_dir = self.hub_dir / Path(source_file).parent
            views_file = app_dir / 'views.py'
            
            if views_file.exists():
                content = views_file.read_text(encoding='utf-8')
                # Check for serializer_class or get_serializer_class
                if re.search(r'serializer_class\s*=|get_serializer_class', content):
                    return True
        
        return False
    
    def _check_tests(self, path: str, source_file: Optional[str]) -> bool:
        """Check if endpoint has tests"""
        if source_file:
            app_dir = self.hub_dir / Path(source_file).parent
            
            # Look for test files
            test_files = [
                app_dir / 'tests.py',
                app_dir / 'tests' / '__init__.py',
                app_dir / 'tests' / 'test_views.py',
                app_dir / 'tests' / 'test_api.py',
                app_dir / 'tests' / 'test_viewsets.py',
            ]
            
            # Also check for test directories
            test_dir = app_dir / 'tests'
            if test_dir.exists():
                test_files.extend(test_dir.glob('test_*.py'))
            
            for test_file in test_files:
                if test_file.exists():
                    try:
                        content = test_file.read_text(encoding='utf-8')
                        # Extract path segment for matching
                        path_segment = path.split('/')[-1].rstrip('/')
                        if not path_segment:
                            path_segment = path.split('/')[-2] if len(path.split('/')) > 2 else ''
                        
                        # Check if path, view, or action is tested
                        if (path_segment in content or 
                            path in content or 
                            'test_' in content.lower() or
                            'APIClient' in content or
                            'client.get' in content or
                            'client.post' in content):
                            return True
                    except Exception:
                        continue
        
        return False
    
    def _check_deprecated(self, path: str, view_class: Optional[str], source_file: Optional[str]) -> bool:
        """Check if endpoint is deprecated"""
        if source_file:
            file_path = self.hub_dir / source_file
            if file_path.exists():
                content = file_path.read_text(encoding='utf-8')
                # Check for deprecation markers
                if re.search(r'@deprecated|deprecated\s*=\s*True|#\s*deprecated', content, re.IGNORECASE):
                    return True
        
        if view_class and source_file:
            view_file = self._find_view_file(source_file, view_class)
            if view_file and view_file.exists():
                content = view_file.read_text(encoding='utf-8')
                if re.search(r'@deprecated|deprecated\s*=\s*True|#\s*deprecated', content, re.IGNORECASE):
                    return True
        
        return False
    
    def _find_view_file(self, source_file: str, view_class: str) -> Optional[Path]:
        """Find the view file for a view class"""
        if not source_file:
            return None
        
        # Extract app directory
        app_dir = Path(source_file).parent
        views_file = app_dir / 'views.py'
        
        if views_file.exists():
            return views_file
        
        return None
    
    def _check_view_implementation(self, view_file: Path, view_class: str) -> bool:
        """Check if view is properly implemented"""
        try:
            content = view_file.read_text(encoding='utf-8')
            
            # Check if class exists
            if view_class in content:
                # Check if it's not just an import
                class_pattern = re.compile(rf'class\s+{view_class}\s*[\(:]', re.MULTILINE)
                if class_pattern.search(content):
                    # Check if it has methods (not just a stub)
                    class_match = class_pattern.search(content)
                    if class_match:
                        # Get class body
                        start = class_match.end()
                        # Find next class or end of file
                        next_class = re.search(r'\nclass\s+\w+', content[start:])
                        class_body = content[start:start + (next_class.start() if next_class else len(content))]
                        
                        # Check for method definitions
                        if re.search(r'def\s+\w+', class_body):
                            return True
            
            return False
        except Exception as e:
            print(f"Error checking view implementation {view_file}: {e}")
            return False
    
    def _get_implemented_methods(self, path: str, view_class: Optional[str], source_file: Optional[str]) -> Set[str]:
        """Get set of implemented HTTP methods for a ViewSet"""
        methods = set()
        
        if view_class and source_file:
            view_file = self._find_view_file(source_file, view_class)
            if view_file and view_file.exists():
                content = view_file.read_text(encoding='utf-8')
                
                # Check for standard ViewSet methods
                if 'def list' in content or 'list' in content:
                    methods.add('GET')
                if 'def create' in content:
                    methods.add('POST')
                if 'def retrieve' in content:
                    methods.add('GET')
                if 'def update' in content:
                    methods.add('PUT')
                if 'def partial_update' in content:
                    methods.add('PATCH')
                if 'def destroy' in content:
                    methods.add('DELETE')
        
        return methods
    
    def generate_categorized_inventory(self, output_path: Path):
        """Generate categorized inventory report"""
        categories = self.categorize_all()
        
        # Read original inventory
        inventory_content = self.inventory_file.read_text(encoding='utf-8')
        
        # Statistics
        stats = {
            'total': len(categories),
            'by_feature_type': defaultdict(int),
            'by_status': defaultdict(int),
            'by_completeness': defaultdict(int),
            'with_schema': 0,
            'with_tests': 0,
            'deprecated': 0
        }
        
        for category in categories.values():
            stats['by_feature_type'][category.feature_type] += 1
            stats['by_status'][category.status] += 1
            stats['by_completeness'][category.completeness.split('(')[0].strip()] += 1
            if category.has_schema:
                stats['with_schema'] += 1
            if category.has_tests:
                stats['with_tests'] += 1
            if category.is_deprecated:
                stats['deprecated'] += 1
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Current API Inventory - Categorized\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Total Endpoints:** {stats['total']}\n\n")
            
            # Summary Statistics
            f.write("## Summary Statistics\n\n")
            f.write(f"- **Total Endpoints:** {stats['total']}\n")
            f.write(f"- **With Schema:** {stats['with_schema']} ({stats['with_schema']*100//stats['total'] if stats['total'] > 0 else 0}%)\n")
            f.write(f"- **With Tests:** {stats['with_tests']} ({stats['with_tests']*100//stats['total'] if stats['total'] > 0 else 0}%)\n")
            f.write(f"- **Deprecated:** {stats['deprecated']}\n\n")
            
            # By Feature Type
            f.write("### By Feature Type\n\n")
            f.write("| Type | Count | Percentage |\n")
            f.write("|------|-------|------------|\n")
            for feature_type in ['Core', 'Feature', 'New Feature']:
                count = stats['by_feature_type'][feature_type]
                percentage = (count * 100 // stats['total']) if stats['total'] > 0 else 0
                f.write(f"| **{feature_type}** | {count} | {percentage}% |\n")
            f.write("\n")
            
            # By Status
            f.write("### By Status\n\n")
            f.write("| Status | Count | Percentage |\n")
            f.write("|--------|-------|------------|\n")
            for status in ['Working', 'Broken', 'Deprecated', 'Unknown']:
                count = stats['by_status'][status]
                percentage = (count * 100 // stats['total']) if stats['total'] > 0 else 0
                f.write(f"| **{status}** | {count} | {percentage}% |\n")
            f.write("\n")
            
            # By Completeness
            f.write("### By Completeness\n\n")
            f.write("| Completeness | Count | Percentage |\n")
            f.write("|--------------|-------|------------|\n")
            for completeness in ['Complete', 'Incomplete']:
                count = stats['by_completeness'][completeness]
                percentage = (count * 100 // stats['total']) if stats['total'] > 0 else 0
                f.write(f"| **{completeness}** | {count} | {percentage}% |\n")
            f.write("\n")
            
            # Detailed categorization
            f.write("## Detailed Categorization\n\n")
            
            # Group by feature type
            by_feature_type = defaultdict(list)
            for endpoint_key, category in categories.items():
                by_feature_type[category.feature_type].append((endpoint_key, category))
            
            for feature_type in ['Core', 'Feature', 'New Feature']:
                if feature_type in by_feature_type:
                    f.write(f"### {feature_type} Features\n\n")
                    
                    # Group by status
                    by_status = defaultdict(list)
                    for endpoint_key, category in by_feature_type[feature_type]:
                        by_status[category.status].append((endpoint_key, category))
                    
                    for status in ['Working', 'Broken', 'Deprecated', 'Unknown']:
                        if status in by_status:
                            f.write(f"#### {status}\n\n")
                            
                            for endpoint_key, category in sorted(by_status[status]):
                                method, path = endpoint_key.split(':', 1)
                                f.write(f"- **{method}** `{path}`\n")
                                f.write(f"  - **Completeness:** {category.completeness}\n")
                                if category.has_schema:
                                    f.write(f"  - ✅ Has Schema\n")
                                if category.has_tests:
                                    f.write(f"  - ✅ Has Tests\n")
                                if category.is_deprecated:
                                    f.write(f"  - ⚠️ Deprecated\n")
                                if category.notes:
                                    f.write(f"  - **Notes:** {', '.join(category.notes)}\n")
                                f.write("\n")
            
            # Complete endpoint table
            f.write("## Complete Endpoint Categorization Table\n\n")
            f.write("| Method | Path | Feature Type | Status | Completeness | Schema | Tests | Deprecated |\n")
            f.write("|--------|------|--------------|--------|--------------|--------|-------|------------|\n")
            
            for endpoint_key in sorted(categories.keys()):
                category = categories[endpoint_key]
                method, path = endpoint_key.split(':', 1)
                schema_mark = "✅" if category.has_schema else "❌"
                tests_mark = "✅" if category.has_tests else "❌"
                deprecated_mark = "⚠️" if category.is_deprecated else "-"
                completeness_short = category.completeness.split('(')[0].strip()
                
                f.write(f"| {method} | `{path}` | {category.feature_type} | {category.status} | {completeness_short} | {schema_mark} | {tests_mark} | {deprecated_mark} |\n")
        
        print(f"\n✅ Categorized inventory generated: {output_path}")
        print(f"📊 Statistics:")
        print(f"   - Total: {stats['total']}")
        print(f"   - Core: {stats['by_feature_type']['Core']}")
        print(f"   - Feature: {stats['by_feature_type']['Feature']}")
        print(f"   - New Feature: {stats['by_feature_type']['New Feature']}")
        print(f"   - Working: {stats['by_status']['Working']}")
        print(f"   - With Schema: {stats['with_schema']}")
        print(f"   - With Tests: {stats['with_tests']}")
    
    def _update_original_inventory(self, inventory_file: Path, categorized_file: Path):
        """Update original inventory file with categorization information"""
        try:
            content = inventory_file.read_text(encoding='utf-8')
            
            # Add categorization section at the beginning
            categorized_content = categorized_file.read_text(encoding='utf-8')
            
            # Extract summary statistics from categorized file
            stats_match = re.search(r'## Summary Statistics\n\n(.*?)\n\n##', categorized_content, re.DOTALL)
            if stats_match:
                stats_section = stats_match.group(1)
                
                # Insert after overview
                if '## Summary Statistics' not in content:
                    # Find insertion point (after overview section)
                    insertion_point = content.find('## Endpoints by Path Prefix')
                    if insertion_point > 0:
                        new_content = content[:insertion_point]
                        new_content += "\n## Categorization\n\n"
                        new_content += stats_match.group(1)
                        new_content += "\n\n"
                        new_content += content[insertion_point:]
                        inventory_file.write_text(new_content, encoding='utf-8')
                        print("✅ Updated original inventory with categorization")
        except Exception as e:
            print(f"Warning: Could not update original inventory: {e}")

def main():
    """Main execution"""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    hub_dir = repo_root / 'hub'
    
    # Try codebase-endpoints-inventory.md first (better format), fallback to current-api-inventory.md
    inventory_file = repo_root / 'docs' / 'api-audit' / 'codebase-endpoints-inventory.md'
    if not inventory_file.exists():
        inventory_file = repo_root / 'docs' / 'api-audit' / 'current-api-inventory.md'
    
    output_file = repo_root / 'docs' / 'api-audit' / 'current-api-inventory-categorized.md'
    
    if not inventory_file.exists():
        print(f"Error: Inventory file not found at {inventory_file}")
        return 1
    
    print(f"Using inventory file: {inventory_file}")
    
    if not hub_dir.exists():
        print(f"Error: Hub directory not found at {hub_dir}")
        return 1
    
    categorizer = APICategorizer(hub_dir, inventory_file)
    categorizer.generate_categorized_inventory(output_file)
    
    # Also update the original inventory with categorization
    print("\nUpdating original inventory with categorization...")
    categorizer._update_original_inventory(inventory_file, output_file)
    
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())

