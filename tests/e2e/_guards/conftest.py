"""
E2E _guards conftest — makes guard fixtures discoverable by pytest.

Pytest discovers fixtures from conftest.py files in the test directory
or its ancestors; __init__.py re-exports are NOT sufficient.

Autouse fixtures registered here run for every test in tests/e2e/ and its
subdirectories.
"""
