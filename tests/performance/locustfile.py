"""
Main Locust file for running all performance tests

Usage:
    locust -f tests/performance/locustfile.py --host=http://localhost:8000
    
    Or run specific test:
    locust -f tests/performance/locustfile.py FileUploadDownloadUser --host=http://localhost:8000
"""
import sys
import os
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Import all test user classes using absolute imports
from tests.performance.test_file_upload_download import FileUploadDownloadUser
from tests.performance.test_job_queue_throughput import JobQueueThroughputUser
from tests.performance.test_database_query_performance import DatabaseQueryPerformanceUser
from tests.performance.test_api_endpoints_availability import APIEndpointsAvailabilityUser

# Export all users for Locust
__all__ = [
    'FileUploadDownloadUser',
    'JobQueueThroughputUser',
    'DatabaseQueryPerformanceUser',
    'APIEndpointsAvailabilityUser'
]

