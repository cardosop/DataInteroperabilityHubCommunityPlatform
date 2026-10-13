#!/usr/bin/env python3
"""
Wait for Prefect DB to accept authenticated connections (not just TCP).
Used by prefect-server-test so the server starts only when the DB is ready.
Exits 0 when connected, 1 after timeout, 2 if asyncpg not installed.

Phase U.6: the DB URL is env-driven (PREFECT_DB_URL) — the previous
hardcoded prefect-db-test hostname broke the compose STAGING stack, whose
service is named prefect-db (150 DNS failures, server never started). The
default keeps the test stack working unchanged.
"""

import asyncio
import os
import sys

try:
    import asyncpg
except ImportError:
    sys.exit(2)


async def main() -> int:
    url = os.environ.get(
        "PREFECT_DB_URL",
        "postgresql://prefect:prefect@prefect-db-test:5432/prefect",
    )
    for attempt in range(150):
        try:
            conn = await asyncpg.connect(url)
            await conn.close()
            return 0
        except Exception as e:
            if attempt < 3 or attempt % 10 == 0:
                print(f"Waiting for prefect-db ({attempt + 1}/150): {e}", flush=True)
            await asyncio.sleep(2)
    print("Timeout waiting for prefect-db after 150 attempts", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
