#!/usr/bin/env python
"""
Verify that all required services are running before tests.

This script checks if all microservices are healthy and available.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Initialize Django
import django
django.setup()

from hub.apps.testing.service_utils import check_service_health

services = {
    'COMPLIANCE_SERVICE_URL': 'http://localhost:8082',
    'DQ_SERVICE_URL': 'http://localhost:8083',
    'DATACONTRACT_SERVICE_URL': 'http://localhost:8080',
    'SEMANTIC_SERVICE_URL': 'http://localhost:8081'
}

missing = []
for name, default_url in services.items():
    url = os.getenv(name, default_url)
    if not check_service_health(url, timeout=5):
        missing.append(f"{name} ({url})")

if missing:
    print("ERROR: Required services are not available:", file=sys.stderr)
    for service in missing:
        print(f"  - {service}", file=sys.stderr)
    print("\nPlease start services with:", file=sys.stderr)
    print("  docker-compose up -d compliance-service dq-service datacontract-service semantic-service", file=sys.stderr)
    sys.exit(1)

print("✓ All required services are available")
sys.exit(0)

