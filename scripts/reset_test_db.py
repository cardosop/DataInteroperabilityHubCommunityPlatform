#!/usr/bin/env python
"""
Script to clean/reset the test database for pytest.

Usage:
    python scripts/reset_test_db.py
"""

import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
django.setup()

import psycopg2
from django.conf import settings


def reset_test_database():
    """Reset the test database by dropping and recreating it."""
    db_config = settings.DATABASES["default"]
    db_name = db_config["NAME"]
    test_db_name = f"{db_name}_test"

    print(f"Resetting test database: {test_db_name}")

    # Connect to postgres database to drop test database
    try:
        # Get connection parameters
        conn_params = {
            "host": db_config.get("HOST", "localhost"),
            "port": db_config.get("PORT", "5432"),
            "user": db_config.get("USER", "postgres"),
            "password": db_config.get("PASSWORD", ""),
            "database": "postgres",  # Connect to postgres to drop other databases
        }

        # Connect and drop test database
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True  # Required for DROP DATABASE
        cursor = conn.cursor()

        # Terminate connections to test database first
        cursor.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{test_db_name}'
            AND pid <> pg_backend_pid();
        """)

        # Drop test database
        cursor.execute(f'DROP DATABASE IF EXISTS "{test_db_name}";')
        cursor.close()
        conn.close()

        print(f"Successfully dropped test database: {test_db_name}")
        print(
            "Run tests with: pytest hub/apps/orchestration/workflows/tests/test_contract_creation.py -v"
        )

    except psycopg2.OperationalError as e:
        print(f"Could not connect to PostgreSQL: {e}")
        print("Make sure PostgreSQL is running and credentials are correct.")
        print("You can also manually drop the database:")
        print(
            f"  psql -U {conn_params['user']} -d postgres -c 'DROP DATABASE IF EXISTS \"{test_db_name}\";'"
        )
        sys.exit(1)
    except Exception as e:
        print(f"Error resetting test database: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    reset_test_database()
