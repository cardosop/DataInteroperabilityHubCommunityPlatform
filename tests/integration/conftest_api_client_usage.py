"""
Pytest configuration for API Client Usage Search tests.

This conftest ensures these tests can run without Django dependencies.
"""

# This file exists to prevent pytest from loading the main conftest.py
# which requires Django. These tests only validate JSON structure.

