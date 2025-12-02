#!/bin/bash
# Script to ensure test database is clean before running tests

# Drop and recreate test database
python3 << EOF
import psycopg2
import os

postgres_host = os.getenv('POSTGRES_HOST', 'localhost')
postgres_db = os.getenv('POSTGRES_DB', 'hub')
postgres_user = os.getenv('POSTGRES_USER', 'hub')
postgres_password = os.getenv('POSTGRES_PASSWORD', 'hub')
postgres_port = os.getenv('POSTGRES_PORT', '5432')

try:
    conn = psycopg2.connect(
        host=postgres_host,
        port=postgres_port,
        database=postgres_db,
        user=postgres_user,
        password=postgres_password
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    # Terminate all connections to test database
    cur.execute("""
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = 'hub_test'
        AND pid <> pg_backend_pid();
    """)
    
    # Drop test database
    cur.execute('DROP DATABASE IF EXISTS hub_test')
    print("✅ Dropped test database")
    
    # Create fresh test database
    cur.execute('CREATE DATABASE hub_test')
    print("✅ Created fresh test database")
    
    conn.close()
except Exception as e:
    print(f"⚠️  Could not clean test database: {e}")
    print("   This is OK if database doesn't exist yet")
EOF

