#!/usr/bin/env python
"""
Script to fix test database lock issues by terminating connections and cleaning up.

Usage:
    python scripts/fix_test_db_lock.py
"""
import os
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
django.setup()

from django.conf import settings
import psycopg2
from psycopg2 import sql

def fix_test_database_lock():
    """Terminate connections to test database and optionally drop it."""
    db_config = settings.DATABASES['default']
    
    # Get test database name (Django appends _test)
    test_db_name = db_config['TEST'].get('NAME') or f"{db_config['NAME']}_test"
    
    print(f"Fixing test database lock: {test_db_name}")
    print(f"Host: {db_config.get('HOST', 'localhost')}")
    print(f"Port: {db_config.get('PORT', '5432')}")
    print(f"User: {db_config.get('USER')}")
    
    # Connect to postgres database to manage test database
    try:
        # Get connection parameters
        # Try to detect staging port (5433) if default port fails
        default_port = db_config.get('PORT', '5432')
        conn_params = {
            'host': db_config.get('HOST', 'localhost'),
            'port': default_port,
            'user': db_config.get('USER', 'postgres'),
            'password': db_config.get('PASSWORD', ''),
            'database': 'postgres'  # Connect to postgres to manage other databases
        }
        
        # If staging detected, try port 5433
        if 'staging' in db_config.get('NAME', '').lower() or 'staging' in db_config.get('USER', '').lower():
            conn_params['port'] = '5433'
        
        # Connect
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True  # Required for DROP DATABASE
        cursor = conn.cursor()
        
        # First, terminate all connections to the test database
        print(f"\nTerminating connections to {test_db_name}...")
        terminate_query = sql.SQL("""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = %s
            AND pid <> pg_backend_pid();
        """)
        cursor.execute(terminate_query, (test_db_name,))
        terminated = cursor.rowcount
        print(f"Terminated {terminated} connection(s)")
        
        # Wait a moment for connections to close
        import time
        time.sleep(0.5)
        
        # Drop test database if it exists
        print(f"\nDropping test database {test_db_name}...")
        drop_query = sql.SQL("DROP DATABASE IF EXISTS {}").format(
            sql.Identifier(test_db_name)
        )
        cursor.execute(drop_query)
        print(f"Successfully dropped test database: {test_db_name}")
        
        cursor.close()
        conn.close()
        
        print("\n✓ Test database lock fixed!")
        print("You can now run tests without database lock errors.")
        
    except psycopg2.OperationalError as e:
        print(f"\n✗ Could not connect to PostgreSQL: {e}")
        print("\nTrying alternative connection methods...")
        
        # Try connecting to template1 or other databases
        for alt_db in ['template1', 'postgres', db_config.get('NAME', 'hub')]:
            try:
                conn_params['database'] = alt_db
                conn = psycopg2.connect(**conn_params)
                conn.autocommit = True
                cursor = conn.cursor()
                
                print(f"Connected via {alt_db} database")
                
                # Terminate connections
                terminate_query = sql.SQL("""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = %s
                    AND pid <> pg_backend_pid();
                """)
                cursor.execute(terminate_query, (test_db_name,))
                terminated = cursor.rowcount
                print(f"Terminated {terminated} connection(s)")
                
                # Drop database
                drop_query = sql.SQL("DROP DATABASE IF EXISTS {}").format(
                    sql.Identifier(test_db_name)
                )
                cursor.execute(drop_query)
                print(f"Successfully dropped test database: {test_db_name}")
                
                cursor.close()
                conn.close()
                print("\n✓ Test database lock fixed!")
                return
                
            except Exception as alt_e:
                print(f"  Failed with {alt_db}: {alt_e}")
                continue
        
        # Try Docker exec as fallback
        print("\nTrying Docker exec method...")
        import subprocess
        docker_container = os.getenv('POSTGRES_CONTAINER', 'hub-postgres-staging')
        
        try:
            # Terminate connections via Docker
            cmd1 = [
                'docker', 'exec', docker_container,
                'psql', '-U', conn_params['user'], '-d', 'postgres',
                '-c', f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '{test_db_name}' AND pid <> pg_backend_pid();"
            ]
            result1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=10)
            if result1.returncode == 0:
                print(f"✓ Terminated connections via Docker")
            else:
                print(f"  Docker exec warning: {result1.stderr}")
            
            # Drop database via Docker
            cmd2 = [
                'docker', 'exec', docker_container,
                'psql', '-U', conn_params['user'], '-d', 'postgres',
                '-c', f'DROP DATABASE IF EXISTS "{test_db_name}";'
            ]
            result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=10)
            if result2.returncode == 0:
                print(f"✓ Dropped test database via Docker")
                print("\n✓ Test database lock fixed via Docker!")
                return
            else:
                print(f"  Docker exec warning: {result2.stderr}")
                
        except FileNotFoundError:
            print("  Docker not found, skipping Docker method")
        except Exception as docker_e:
            print(f"  Docker exec failed: {docker_e}")
        
        print("\n✗ Could not fix database lock. Manual steps:")
        print(f"  Option 1 - Via Docker:")
        print(f"    docker exec {docker_container} psql -U {conn_params['user']} -d postgres -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{test_db_name}' AND pid <> pg_backend_pid();\"")
        print(f"    docker exec {docker_container} psql -U {conn_params['user']} -d postgres -c 'DROP DATABASE IF EXISTS \"{test_db_name}\";'")
        print(f"  Option 2 - Direct connection:")
        print(f"    psql -h {conn_params['host']} -p {conn_params['port']} -U {conn_params['user']} -d postgres")
        print(f"    Then run: SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{test_db_name}' AND pid <> pg_backend_pid();")
        print(f"    Then run: DROP DATABASE IF EXISTS \"{test_db_name}\";")
        sys.exit(1)
        
    except Exception as e:
        print(f"\n✗ Error fixing test database lock: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    fix_test_database_lock()

