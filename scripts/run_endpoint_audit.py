#!/usr/bin/env python3
"""
Wrapper script to run endpoint audit with proper Django setup
"""
import os
import sys
from pathlib import Path

# Redirect stderr to suppress Django logs (optional, can be controlled via env var)
if os.environ.get('SUPPRESS_DJANGO_LOGS', '1') == '1':
    import logging
    logging.disable(logging.CRITICAL)

# Ensure we're in the right directory and Django can find hub module
project_root = Path('/app')
if (project_root / 'hub' / 'apps' / 'api' / 'urls.py').exists():
    os.chdir(project_root)
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Now import and setup Django
import django
# Suppress Django startup messages
import warnings
warnings.filterwarnings('ignore')
django.setup()

# Import and run the audit script using importlib (hyphenated filename)
import importlib.util
script_path = project_root / 'scripts' / 'audit-api-endpoints.py'
spec = importlib.util.spec_from_file_location('audit_api_endpoints', script_path)
audit_api_endpoints = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_api_endpoints)

EndpointAuditor = audit_api_endpoints.EndpointAuditor
import json

if __name__ == '__main__':
    urls_file = 'hub/apps/api/urls.py'
    auditor = EndpointAuditor()
    
    results = auditor.audit(
        urls_file,
        check_duplicates=True,
        check_naming=True,
    )
    
    # Output JSON to stdout (only JSON, no other output)
    output = auditor.output_json(results)
    sys.stdout.write(output)
    sys.stdout.flush()

