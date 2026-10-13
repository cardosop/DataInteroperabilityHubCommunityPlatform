"""Phase 9 (openspec add-databricks-live-ci-sandbox) — the Databricks live
E2E sandbox suites.

Task 9.3 lands the ordered journey here; task 9.4 the contract tests
(`test_contracts.py`). The contract suite has three layers: the STATIC
write-coverage matrix (the shipped executor's REST pins vs the
``api_paths.py`` registry — always on), the LOCAL real-server contract
pins (the shipped pagination + statement-submit machinery driven over a
real threaded local HTTP server — always on), and the LIVE probes (the
real-sandbox round-trips, W16-gated — CI raises, local runs skip).
"""
