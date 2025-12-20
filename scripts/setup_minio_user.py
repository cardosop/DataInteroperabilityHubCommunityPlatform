#!/usr/bin/env python3
"""
Setup MinIO user for staging environment.

Creates the minio_staging user in MinIO if it doesn't exist.
Uses Docker to run mc (MinIO Client) since it's not available in all containers.
"""
import subprocess
import sys
import os

def setup_minio_user():
    """Create minio_staging user in MinIO using Docker to run mc"""
    minio_host = os.environ.get('MINIO_HOST', 'minio')
    minio_port = os.environ.get('MINIO_PORT', '9000')
    root_user = os.environ.get('MINIO_ROOT_USER', 'minio')
    root_password = os.environ.get('MINIO_ROOT_PASSWORD', 'minio123')
    staging_user = os.environ.get('MINIO_STAGING_USER', 'minio_staging')
    staging_password = os.environ.get('MINIO_STAGING_PASSWORD', 'minio_staging_secure')

    print(f"Setting up MinIO user '{staging_user}'...")
    print(f"Connecting to MinIO at {minio_host}:{minio_port}...")

    # Use Docker to run mc in a container that has it
    # We'll use a minio/mc image or install mc in a temporary container
    # First, try to detect the network name
    network_name = 'hub-net'  # Default, will try to detect
    try:
        result = subprocess.run(
            ['docker', 'network', 'ls', '--format', '{{.Name}}'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if 'hub' in result.stdout.lower():
            # Find network with 'hub' in name
            for line in result.stdout.strip().split('\n'):
                if 'hub' in line.lower():
                    network_name = line.strip()
                    break
    except Exception:
        pass  # Use default

    docker_cmd = [
        'docker', 'run', '--rm', '--network', network_name,
        'minio/mc:latest',
        'mc', 'alias', 'set', 'local', f'http://{minio_host}:{minio_port}', root_user, root_password,
        '&&', 'mc', 'admin', 'user', 'add', 'local', staging_user, staging_password
    ]

    try:
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            print(f"✅ User '{staging_user}' created successfully")

            # Attach readwrite policy
            policy_cmd = [
                'docker', 'run', '--rm', '--network', 'hub-net',
                '-e', f'MC_HOST_local=http://{root_user}:{root_password}@{minio_host}:{minio_port}',
                'minio/mc:latest',
                'mc', 'admin', 'policy', 'attach', 'local', 'readwrite', '--user', staging_user
            ]

            policy_result = subprocess.run(
                policy_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if policy_result.returncode == 0:
                print(f"✅ Policy 'readwrite' attached to user '{staging_user}'")
                return True
            else:
                print(f"⚠️  Could not attach policy: {policy_result.stderr}")
                # User was created, so this is still a partial success
                return True
        else:
            # Check if user already exists
            if 'already exists' in result.stderr.lower() or 'user already exists' in result.stderr.lower():
                print(f"✅ User '{staging_user}' already exists")
                return True
            else:
                print(f"❌ Failed to create user: {result.stderr}")
                return False

    except subprocess.TimeoutExpired:
        print("❌ Command timed out")
        return False
    except FileNotFoundError:
        print("❌ Docker not found. Please install Docker or run this script in an environment with Docker.")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == '__main__':
    success = setup_minio_user()
    sys.exit(0 if success else 1)

