#!/usr/bin/env python3
"""
Validate Error Responses in OpenAPI Specifications

This script validates that all OpenAPI specs have complete error response documentation.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict

class ErrorResponseValidator:
    """Validates error responses in OpenAPI specs"""
    
    def __init__(self):
        # Required error codes by endpoint type
        self.required_errors = {
            'all': [400, 500, 503],
            'authenticated': [401, 403],
            'with_id': [404],
            'mutating': [409],
            'auth_endpoints': [429],
        }
        
        # Required fields in ErrorResponse schema
        self.required_schema_fields = [
            'code', 'message', 'http_status', 'request_id', 'timestamp'
        ]
    
    def validate_spec(self, spec_path: Path) -> Dict:
        """Validate error responses in a spec file"""
        results = {
            'file': str(spec_path),
            'valid': True,
            'errors': [],
            'warnings': [],
            'error_responses_found': set(),
            'missing_errors': [],
            'schema_valid': False,
        }
        
        try:
            with open(spec_path, 'r', encoding='utf-8') as f:
                spec = yaml.safe_load(f)
            
            if not spec or 'paths' not in spec:
                results['errors'].append("Invalid OpenAPI spec structure")
                results['valid'] = False
                return results
            
            # Check ErrorResponse schema
            if 'components' in spec and 'schemas' in spec['components']:
                if 'ErrorResponse' in spec['components']['schemas']:
                    schema = spec['components']['schemas']['ErrorResponse']
                    results['schema_valid'] = self._validate_error_schema(schema, results)
                else:
                    results['errors'].append("ErrorResponse schema not found in components/schemas")
                    results['valid'] = False
            
            # Validate each endpoint
            for path, path_item in spec['paths'].items():
                for method in ['get', 'post', 'put', 'patch', 'delete']:
                    if method not in path_item:
                        continue
                    
                    operation = path_item[method]
                    endpoint_results = self._validate_endpoint_error_responses(
                        path, method.upper(), operation, spec
                    )
                    
                    results['error_responses_found'].update(endpoint_results['found'])
                    results['missing_errors'].extend(endpoint_results['missing'])
                    
                    if endpoint_results['errors']:
                        results['errors'].extend(endpoint_results['errors'])
                        results['valid'] = False
                    
                    if endpoint_results['warnings']:
                        results['warnings'].extend(endpoint_results['warnings'])
        
        except Exception as e:
            results['errors'].append(f"Error reading spec: {e}")
            results['valid'] = False
        
        return results
    
    def _validate_error_schema(self, schema: Dict, results: Dict) -> bool:
        """Validate ErrorResponse schema structure"""
        if 'properties' not in schema or 'error' not in schema['properties']:
            results['errors'].append("ErrorResponse schema missing 'error' property")
            return False
        
        error_props = schema['properties']['error']
        if 'properties' not in error_props:
            results['errors'].append("ErrorResponse.error missing properties")
            return False
        
        error_fields = error_props['properties']
        missing_fields = [f for f in self.required_schema_fields if f not in error_fields]
        
        if missing_fields:
            results['errors'].append(f"ErrorResponse schema missing fields: {', '.join(missing_fields)}")
            return False
        
        return True
    
    def _validate_endpoint_error_responses(
        self, path: str, method: str, operation: Dict, spec: Dict
    ) -> Dict:
        """Validate error responses for a single endpoint"""
        results = {
            'found': set(),
            'missing': [],
            'errors': [],
            'warnings': [],
        }
        
        if 'responses' not in operation:
            results['errors'].append(f"{method} {path}: No responses section")
            return results
        
        responses = operation['responses']
        
        # Determine required errors
        required = set(self.required_errors['all'])
        
        # Check if authenticated
        requires_auth = self._requires_auth(operation, spec)
        if requires_auth:
            required.update(self.required_errors['authenticated'])
        
        # Check if has ID parameter
        if '{id}' in path or '{pk}' in path:
            required.add(404)
        
        # Check if mutating
        if method in ['POST', 'PUT', 'PATCH']:
            required.add(409)
        
        # Check if auth endpoint
        if 'auth' in path or 'register' in path or 'login' in path:
            required.add(429)
        
        # Validate each required error
        for status_code in required:
            status_str = str(status_code)
            
            if status_str in responses:
                results['found'].add(status_code)
                
                # Validate response structure
                response = responses[status_str]
                if 'content' not in response:
                    results['warnings'].append(
                        f"{method} {path}: {status_code} response missing content"
                    )
                elif 'application/json' in response['content']:
                    content = response['content']['application/json']
                    if 'schema' not in content:
                        results['warnings'].append(
                            f"{method} {path}: {status_code} response missing schema"
                        )
                    elif '$ref' not in content['schema']:
                        results['warnings'].append(
                            f"{method} {path}: {status_code} response schema not using $ref"
                        )
                    elif 'ErrorResponse' not in content['schema']['$ref']:
                        results['warnings'].append(
                            f"{method} {path}: {status_code} response schema not referencing ErrorResponse"
                        )
            else:
                results['missing'].append({
                    'status_code': status_code,
                    'endpoint': f"{method} {path}",
                })
        
        return results
    
    def _requires_auth(self, operation: Dict, spec: Dict) -> bool:
        """Determine if operation requires authentication"""
        if 'security' in operation:
            return operation['security'] != []
        if 'security' in spec:
            return spec['security'] != []
        return True
    
    def validate_all_specs(self, contracts_dir: Path) -> Dict:
        """Validate all OpenAPI specs"""
        results = {
            'total': 0,
            'valid': 0,
            'invalid': 0,
            'specs': [],
            'summary': defaultdict(int),
        }
        
        yaml_files = list(contracts_dir.rglob('*.yaml')) + list(contracts_dir.rglob('*.yml'))
        
        for spec_file in yaml_files:
            if spec_file.name in ['README.md']:
                continue
            
            results['total'] += 1
            spec_results = self.validate_spec(spec_file)
            results['specs'].append(spec_results)
            
            if spec_results['valid']:
                results['valid'] += 1
            else:
                results['invalid'] += 1
            
            # Count error responses
            results['summary']['total_error_responses'] += len(spec_results['error_responses_found'])
            results['summary']['missing_error_responses'] += len(spec_results['missing_errors'])
            results['summary']['total_errors'] += len(spec_results['errors'])
            results['summary']['total_warnings'] += len(spec_results['warnings'])
        
        return results

def main():
    """Main execution"""
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    contracts_dir = repo_root / 'docs' / 'api-contracts' / 'missing'
    
    if not contracts_dir.exists():
        print(f"Error: Contracts directory not found at {contracts_dir}")
        return 1
    
    validator = ErrorResponseValidator()
    results = validator.validate_all_specs(contracts_dir)
    
    print(f"\n📊 Validation Results")
    print(f"   - Total Specs: {results['total']}")
    print(f"   - Valid: {results['valid']}")
    print(f"   - Invalid: {results['invalid']}")
    print(f"   - Total Error Responses: {results['summary']['total_error_responses']}")
    print(f"   - Missing Error Responses: {results['summary']['missing_error_responses']}")
    print(f"   - Total Errors: {results['summary']['total_errors']}")
    print(f"   - Total Warnings: {results['summary']['total_warnings']}")
    
    # Print errors and warnings
    for spec_result in results['specs']:
        if spec_result['errors'] or spec_result['warnings']:
            print(f"\n📄 {Path(spec_result['file']).name}")
            if spec_result['errors']:
                print("   ❌ Errors:")
                for error in spec_result['errors']:
                    print(f"      - {error}")
            if spec_result['warnings']:
                print("   ⚠️  Warnings:")
                for warning in spec_result['warnings'][:5]:  # Limit to first 5
                    print(f"      - {warning}")
    
    return 0 if results['invalid'] == 0 else 1

if __name__ == '__main__':
    import sys
    sys.exit(main())

