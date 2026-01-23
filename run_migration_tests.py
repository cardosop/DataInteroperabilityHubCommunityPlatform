#!/usr/bin/env python
"""
Simple test runner for migration validation tests.
Runs tests using Django's test framework directly.
"""
import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

if __name__ == "__main__":
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
    django.setup()
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False, keepdb=False)
    
    # Run specific test files
    test_modules = [
        'hub.apps.contracts.tests.test_migration_validation_comprehensive',
        'hub.apps.contracts.tests.test_migration_rollback_comprehensive',
        'hub.apps.contracts.tests.test_data_setup_teardown',
        'hub.apps.contracts.tests.test_data_seeding',
        'hub.apps.contracts.tests.test_environment_validation_comprehensive',
    ]
    
    failures = test_runner.run_tests(test_modules)
    sys.exit(bool(failures))
