#!/usr/bin/env python
"""
Script to clean up old test databases that are causing WAL lock contention.

This script:
1. Lists all test databases matching 'hub_test%' pattern
2. Terminates active connections to those databases
3. Drops the databases
4. Reports cleanup statistics

Usage:
    python scripts/cleanup_test_databases.py [--dry-run] [--pattern PATTERN]

Environment Variables:
    POSTGRES_HOST: Database host (default: localhost)
    POSTGRES_PORT: Database port (default: 5432)
    POSTGRES_USER: Database user (default: hub)
    POSTGRES_PASSWORD: Database password (default: hub)
"""
import argparse
import os
import sys
from typing import List, Tuple

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    print("ERROR: psycopg2 is required. Install it with: pip install psycopg2-binary")
    sys.exit(1)


def get_db_connection_params() -> dict:
    """Get database connection parameters from environment or defaults."""
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "user": os.getenv("POSTGRES_USER", "hub"),
        "password": os.getenv("POSTGRES_PASSWORD", "hub"),
        "database": "postgres",  # Connect to postgres to manage other databases
    }


def get_test_databases(conn, pattern: str = "hub_test%") -> List[str]:
    """
    Get list of test databases matching the pattern.

    Args:
        conn: PostgreSQL connection
        pattern: Database name pattern (default: 'hub_test%')

    Returns:
        List of database names
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT datname
            FROM pg_database
            WHERE datname LIKE %s
            AND datname != 'hub_test'  -- Exclude main test database if it exists
            ORDER BY datname;
        """,
            (pattern,),
        )
        databases = [row[0] for row in cursor.fetchall()]
        return databases
    finally:
        cursor.close()


def terminate_connections(conn, database_name: str) -> int:
    """
    Terminate all active connections to a database.

    Args:
        conn: PostgreSQL connection
        database_name: Name of the database

    Returns:
        Number of connections terminated
    """
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = %s
            AND pid <> pg_backend_pid();
        """,
            (database_name,),
        )
        terminated = cursor.rowcount
        return terminated
    finally:
        cursor.close()


def drop_database(conn, database_name: str) -> bool:
    """
    Drop a database.

    Args:
        conn: PostgreSQL connection (must have autocommit enabled)
        database_name: Name of the database to drop

    Returns:
        True if successful, False otherwise
    """
    cursor = conn.cursor()
    try:
        # Escape database name for safety
        cursor.execute('DROP DATABASE IF EXISTS "{}";'.format(database_name.replace('"', '""')))
        return True
    except Exception as e:
        print(f"  ⚠️  Error dropping {database_name}: {e}")
        return False
    finally:
        cursor.close()


def cleanup_test_databases(
    pattern: str = "hub_test%", dry_run: bool = False, verbose: bool = True
) -> Tuple[int, int, int]:
    """
    Clean up test databases matching the pattern.

    Args:
        pattern: Database name pattern (default: 'hub_test%')
        dry_run: If True, only report what would be done
        verbose: If True, print detailed output

    Returns:
        Tuple of (total_found, terminated_connections, dropped_databases)
    """
    conn_params = get_db_connection_params()

    if verbose:
        print(f"Connecting to PostgreSQL at {conn_params['host']}:{conn_params['port']}...")
        if dry_run:
            print("🔍 DRY RUN MODE - No databases will be dropped")
        print()

    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(**conn_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

        # Get list of test databases
        test_databases = get_test_databases(conn, pattern)
        total_found = len(test_databases)

        if verbose:
            print(f"Found {total_found} test database(s) matching pattern '{pattern}'")
            if total_found == 0:
                print("✅ No test databases to clean up")
                conn.close()
                return (0, 0, 0)
            print()

        if dry_run:
            print("Databases that would be dropped:")
            for db_name in test_databases:
                print(f"  - {db_name}")
            conn.close()
            return (total_found, 0, 0)

        # Clean up databases
        # First, terminate all connections to test databases in bulk
        if verbose:
            print("Terminating connections to all test databases...")
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname LIKE %s
                AND pid <> pg_backend_pid();
            """, (pattern.replace("%", "%%"),))
            terminated_total = cursor.rowcount
            if verbose:
                print(f"  ✓ Terminated {terminated_total} connection(s)")
        finally:
            cursor.close()

        # Drop databases - use bulk SQL for efficiency
        dropped_count = 0
        failed_count = 0

        if verbose:
            print(f"Dropping {total_found} databases...")

        # Build bulk DROP DATABASE commands
        cursor = conn.cursor()
        for db_name in test_databases:
            try:
                # Escape database name for safety
                escaped_name = db_name.replace('"', '""')
                cursor.execute(f'DROP DATABASE IF EXISTS "{escaped_name}";')
                dropped_count += 1
                if verbose and dropped_count % 50 == 0:
                    print(f"  Dropped {dropped_count}/{total_found} databases...")
            except Exception as e:
                failed_count += 1
                if verbose:
                    print(f"  ⚠️  Error dropping {db_name}: {e}")
        cursor.close()

        conn.close()

        # Summary
        if verbose:
            print()
            print("=" * 60)
            print("Cleanup Summary")
            print("=" * 60)
            print(f"Total databases found: {total_found}")
            print(f"Connections terminated: {terminated_total}")
            print(f"Databases dropped: {dropped_count}")
            if failed_count > 0:
                print(f"⚠️  Failed to drop: {failed_count}")
            print("=" * 60)

        return (total_found, terminated_total, dropped_count)

    except psycopg2.OperationalError as e:
        print(f"❌ ERROR: Could not connect to PostgreSQL: {e}")
        print(f"\nConnection parameters:")
        print(f"  Host: {conn_params['host']}")
        print(f"  Port: {conn_params['port']}")
        print(f"  User: {conn_params['user']}")
        print(f"  Database: {conn_params['database']}")
        print("\nMake sure PostgreSQL is running and credentials are correct.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Clean up old test databases causing WAL lock contention"
    )
    parser.add_argument(
        "--pattern",
        default="hub_test%",
        help="Database name pattern to match (default: hub_test%%)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually dropping databases",
    )
    parser.add_argument("--quiet", action="store_true", help="Reduce output verbosity")

    args = parser.parse_args()

    total_found, terminated, dropped = cleanup_test_databases(
        pattern=args.pattern, dry_run=args.dry_run, verbose=not args.quiet
    )

    if args.dry_run:
        sys.exit(0)

    # Exit with error if cleanup failed
    if total_found > 0 and dropped == 0:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
