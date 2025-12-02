#!/usr/bin/env python
"""
Validation script for performance tests

This script validates that all performance test files are properly structured
and can be imported without errors.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

def validate_imports():
    """Validate that all test modules can be imported"""
    errors = []
    
    try:
        from tests.performance.helpers import PerformanceTestHelper
        print("✅ helpers.py imports OK")
    except Exception as e:
        errors.append(f"helpers.py: {e}")
        print(f"❌ helpers.py import failed: {e}")
    
    try:
        from tests.performance.test_file_upload_download import FileUploadDownloadUser
        print("✅ test_file_upload_download.py imports OK")
    except Exception as e:
        errors.append(f"test_file_upload_download.py: {e}")
        print(f"❌ test_file_upload_download.py import failed: {e}")
    
    try:
        from tests.performance.test_job_queue_throughput import JobQueueThroughputUser
        print("✅ test_job_queue_throughput.py imports OK")
    except Exception as e:
        errors.append(f"test_job_queue_throughput.py: {e}")
        print(f"❌ test_job_queue_throughput.py import failed: {e}")
    
    try:
        from tests.performance.test_database_query_performance import DatabaseQueryPerformanceUser
        print("✅ test_database_query_performance.py imports OK")
    except Exception as e:
        errors.append(f"test_database_query_performance.py: {e}")
        print(f"❌ test_database_query_performance.py import failed: {e}")
    
    try:
        from tests.performance.test_api_endpoints_availability import APIEndpointsAvailabilityUser
        print("✅ test_api_endpoints_availability.py imports OK")
    except Exception as e:
        errors.append(f"test_api_endpoints_availability.py: {e}")
        print(f"❌ test_api_endpoints_availability.py import failed: {e}")
    
    try:
        from tests.performance.locustfile import (
            FileUploadDownloadUser,
            JobQueueThroughputUser,
            DatabaseQueryPerformanceUser,
            APIEndpointsAvailabilityUser
        )
        print("✅ locustfile.py imports OK")
    except Exception as e:
        errors.append(f"locustfile.py: {e}")
        print(f"❌ locustfile.py import failed: {e}")
    
    return errors

def validate_user_classes():
    """Validate that user classes have required attributes"""
    errors = []
    
    try:
        from tests.performance.test_file_upload_download import FileUploadDownloadUser
        if not hasattr(FileUploadDownloadUser, 'wait_time'):
            errors.append("FileUploadDownloadUser missing wait_time")
        if not hasattr(FileUploadDownloadUser, 'on_start'):
            errors.append("FileUploadDownloadUser missing on_start")
        print("✅ FileUploadDownloadUser structure OK")
    except Exception as e:
        errors.append(f"FileUploadDownloadUser validation: {e}")
    
    try:
        from tests.performance.test_job_queue_throughput import JobQueueThroughputUser
        if not hasattr(JobQueueThroughputUser, 'wait_time'):
            errors.append("JobQueueThroughputUser missing wait_time")
        print("✅ JobQueueThroughputUser structure OK")
    except Exception as e:
        errors.append(f"JobQueueThroughputUser validation: {e}")
    
    try:
        from tests.performance.test_database_query_performance import DatabaseQueryPerformanceUser
        if not hasattr(DatabaseQueryPerformanceUser, 'wait_time'):
            errors.append("DatabaseQueryPerformanceUser missing wait_time")
        print("✅ DatabaseQueryPerformanceUser structure OK")
    except Exception as e:
        errors.append(f"DatabaseQueryPerformanceUser validation: {e}")
    
    try:
        from tests.performance.test_api_endpoints_availability import APIEndpointsAvailabilityUser
        if not hasattr(APIEndpointsAvailabilityUser, 'wait_time'):
            errors.append("APIEndpointsAvailabilityUser missing wait_time")
        print("✅ APIEndpointsAvailabilityUser structure OK")
    except Exception as e:
        errors.append(f"APIEndpointsAvailabilityUser validation: {e}")
    
    return errors

if __name__ == '__main__':
    print("=" * 60)
    print("Performance Tests Validation")
    print("=" * 60)
    print()
    
    print("1. Validating imports...")
    import_errors = validate_imports()
    print()
    
    if not import_errors:
        print("2. Validating user class structure...")
        structure_errors = validate_user_classes()
        print()
        
        if not structure_errors:
            print("=" * 60)
            print("✅ All validations passed!")
            print("=" * 60)
            print()
            print("Next steps:")
            print("1. Ensure API server is running: python manage.py runserver")
            print("2. Pre-create test users or set PERF_TEST_USER_EMAIL/PASSWORD")
            print("3. Run tests: ./tests/performance/run_performance_tests.sh")
            sys.exit(0)
        else:
            print("=" * 60)
            print("❌ Structure validation failed:")
            for error in structure_errors:
                print(f"  - {error}")
            print("=" * 60)
            sys.exit(1)
    else:
        print("=" * 60)
        print("❌ Import validation failed:")
        for error in import_errors:
            print(f"  - {error}")
        print("=" * 60)
        sys.exit(1)

