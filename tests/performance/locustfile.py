"""
Main Locust file for running all performance tests

Usage:
    # Load testing
    locust -f tests/performance/locustfile.py --host=http://localhost:8000

    # Stress testing
    locust -f tests/performance/locustfile.py StressTestUser --host=http://localhost:8000 -u 200 -r 20

    # Endurance testing (run for extended period)
    locust -f tests/performance/locustfile.py EnduranceTestUser --host=http://localhost:8000 -u 50 -r 5 -t 2h

    # Spike testing
    locust -f tests/performance/locustfile.py SpikeTestUser --host=http://localhost:8000 -u 500 -r 100

    Or run specific test:
    locust -f tests/performance/locustfile.py FileUploadDownloadUser --host=http://localhost:8000
"""

import os
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Import load test user classes (existing)
try:
    from tests.performance.locust_file_upload_download import FileUploadDownloadUser
except ImportError:
    try:
        from tests.performance.test_file_upload_download import FileUploadDownloadUser
    except ImportError:
        FileUploadDownloadUser = None

try:
    from tests.performance.locust_job_queue_throughput import JobQueueThroughputUser
except ImportError:
    try:
        from tests.performance.test_job_queue_throughput import JobQueueThroughputUser
    except ImportError:
        JobQueueThroughputUser = None

try:
    from tests.performance.locust_database_query_performance import DatabaseQueryPerformanceUser
except ImportError:
    try:
        from tests.performance.test_database_query_performance import DatabaseQueryPerformanceUser
    except ImportError:
        DatabaseQueryPerformanceUser = None

try:
    from tests.performance.locust_api_endpoints_availability import APIEndpointsAvailabilityUser
except ImportError:
    try:
        from tests.performance.test_api_endpoints_availability import APIEndpointsAvailabilityUser
    except ImportError:
        APIEndpointsAvailabilityUser = None

# Import new test user classes
try:
    from tests.performance.locust_endurance_test import (
        EnduranceTestMemoryMonitor,
        EnduranceTestUser,
    )
except ImportError:
    EnduranceTestUser = None
    EnduranceTestMemoryMonitor = None

try:
    from tests.performance.locust_spike_test import SpikeTestRapidUser, SpikeTestUser
except ImportError:
    SpikeTestUser = None
    SpikeTestRapidUser = None

try:
    from tests.performance.locust_stress_test import StressTestOverloadUser, StressTestUser
except ImportError:
    StressTestUser = None
    StressTestOverloadUser = None

# Export all users for Locust
__all__ = [
    # Load testing
    "FileUploadDownloadUser",
    "JobQueueThroughputUser",
    "DatabaseQueryPerformanceUser",
    "APIEndpointsAvailabilityUser",
    # Stress testing
    "StressTestUser",
    "StressTestOverloadUser",
    # Endurance testing
    "EnduranceTestUser",
    "EnduranceTestMemoryMonitor",
    # Spike testing
    "SpikeTestUser",
    "SpikeTestRapidUser",
]

# Filter out None values (for missing imports)
__all__ = [user for user in __all__ if user is not None]
