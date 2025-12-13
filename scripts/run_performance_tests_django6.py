#!/usr/bin/env python3
"""
Run Performance Tests with Django 6

This script runs all performance tests and generates a performance report.

Usage:
    python scripts/run_performance_tests_django6.py [--output OUTPUT_FILE]

Example:
    python scripts/run_performance_tests_django6.py --output performance_django6.json
"""

import argparse
import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime


def run_performance_tests(output_file: str) -> int:
    """Run performance tests and save results"""
    print("=" * 60)
    print("Running Performance Tests (Django 6)")
    print("=" * 60)
    print()
    
    # Run pytest with performance tests
    test_files = [
        'tests/performance/test_performance_django6.py',
        'tests/performance/test_performance.py',
        'tests/performance/test_otel_metrics_performance.py',
    ]
    
    results = {
        'django_version': '6.0',
        'timestamp': datetime.now().isoformat(),
        'test_results': {}
    }
    
    exit_code = 0
    
    for test_file in test_files:
        test_path = Path(test_file)
        if not test_path.exists():
            print(f"⚠️  Test file not found: {test_file}")
            continue
        
        print(f"Running: {test_file}")
        result = subprocess.run(
            ['pytest', str(test_path), '-v', '--tb=short', '--json-report', '--json-report-file=/tmp/pytest_report.json'],
            capture_output=True,
            text=True
        )
        
        # Parse results
        if result.returncode == 0:
            print(f"✅ {test_file}: All tests passed")
        else:
            print(f"⚠️  {test_file}: Some tests failed")
            exit_code = 1
        
        # Try to load JSON report if available
        try:
            with open('/tmp/pytest_report.json') as f:
                report = json.load(f)
                results['test_results'][test_file] = {
                    'summary': report.get('summary', {}),
                    'exitcode': result.returncode
                }
        except FileNotFoundError:
            results['test_results'][test_file] = {
                'exitcode': result.returncode,
                'note': 'JSON report not available'
            }
    
    # Save results
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print()
    print(f"✅ Performance test results saved to: {output_path}")
    
    return exit_code


def main():
    parser = argparse.ArgumentParser(description='Run performance tests with Django 6')
    parser.add_argument('--output', default='performance_django6.json',
                       help='Output file path (default: performance_django6.json)')
    
    args = parser.parse_args()
    
    exit_code = run_performance_tests(args.output)
    
    if exit_code == 0:
        print("\n✅ All performance tests completed successfully")
    else:
        print("\n⚠️  Some performance tests failed - review output above")
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())

