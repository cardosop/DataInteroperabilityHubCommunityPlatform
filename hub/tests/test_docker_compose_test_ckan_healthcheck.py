"""
Regression: CKAN test Postgres/Solr healthchecks must survive slow recovery/first boot.

docker compose marks dependent services blocked when healthchecks fail too early; see
docker-compose.test.yml comments on ckan-test-db-test.
"""

import os
import unittest

import yaml

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _compose_path():
    return os.path.join(_REPO_ROOT, "docker-compose.test.yml")


def _duration_seconds(value) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip().lower()
    if s.endswith("ms"):
        return max(1, int(s[:-2]) // 1000)
    if s.endswith("s"):
        return int(s[:-1])
    if s.endswith("m"):
        return int(s[:-1]) * 60
    if s.endswith("h"):
        return int(s[:-1]) * 3600
    return int(s)


class DockerComposeTestCkanHealthcheckTest(unittest.TestCase):
    def test_ckan_test_db_healthcheck_allows_crash_recovery_window(self):
        path = _compose_path()
        if not os.path.isfile(path):
            self.skipTest("docker-compose.test.yml not in repo root")
        with open(path) as f:
            doc = yaml.safe_load(f)
        hc = doc["services"]["ckan-test-db-test"]["healthcheck"]
        self.assertGreaterEqual(_duration_seconds(hc.get("start_period")), 300)
        self.assertGreaterEqual(int(hc.get("retries", 0)), 10)
        test_cmd = hc.get("test")
        self.assertIsInstance(test_cmd, list)
        joined = " ".join(str(x) for x in test_cmd)
        self.assertIn("pg_isready", joined)
        self.assertIn("-t 5", joined)

    def test_ckan_test_solr_healthcheck_allows_slow_cold_start(self):
        path = _compose_path()
        if not os.path.isfile(path):
            self.skipTest("docker-compose.test.yml not in repo root")
        with open(path) as f:
            doc = yaml.safe_load(f)
        hc = doc["services"]["ckan-test-solr-test"]["healthcheck"]
        self.assertGreaterEqual(_duration_seconds(hc.get("start_period")), 60)
        self.assertGreaterEqual(int(hc.get("retries", 0)), 8)
