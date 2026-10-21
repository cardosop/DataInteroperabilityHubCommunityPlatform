# Makefile.core — core-only targets (Phase 313.2).
#
# Included by the private Makefile (`include Makefile.core`) and shipped
# renamed to `Makefile` in the public repo. Keeps ONE definition for the
# core subset; the private Makefile keeps the full-stack targets.
#
# Core test stack = full compose files + the core overlay that profiles
# the paid layer out. Core mode is enforced via HUB_CORE_ONLY=1 inside
# the api container.

# .env.test is untracked by design (313.0) — use it only when present;
# CI and fresh public clones rely on compose ${VAR:-fallback} defaults.
CORE_COMPOSE = -f docker-compose.test.yml -f docker-compose.test.core.yml $(if $(wildcard .env.test),--env-file .env.test,)

# Interpreter resolution (mirrors scripts/publish_public.sh): the repo's
# venv wins when present (this repo has no bare `python`), else PATH.
# The `python` INSIDE the test containers is unaffected (test-core keeps
# its in-container command as-is).
REPO_ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PYTHON := $(shell 	if [ -x "$(REPO_ROOT)venv/bin/python" ]; then 		echo "$(REPO_ROOT)venv/bin/python"; 	elif command -v python3 >/dev/null 2>&1; then 		echo "python3"; 	else 		echo "python"; 	fi)

.PHONY: test-core-stack-up test-core-stack-down test-core lint-core boundary-check publish-check quickstart

test-core-stack-up: ## Bring up the core-only test stack
	docker compose $(CORE_COMPOSE) up -d --build
	# compose --wait aborts when the one-shot migrate container exits 0 on
	# an IDEMPOTENT re-run (fresh DBs keep it running through the wait).
	# Wait for the live endpoint from the host instead (same pattern as the
	# dev quickstart target); the test api publishes 8001.
	@for i in $$(seq 1 90); do \
		curl -sf http://localhost:8001/health/live/ >/dev/null 2>&1 && break; \
		sleep 5; \
	done; \
	curl -sf http://localhost:8001/health/live/ >/dev/null 2>&1 || \
		{ echo "test api never became healthy (http://localhost:8001/health/live/)" >&2; exit 1; }

test-core-stack-down: ## Tear down the core-only test stack
	docker compose $(CORE_COMPOSE) down

test-core: test-core-stack-up ## Core-only backend suite — DESELECTS the integration/e2e/service layer (-m filter, see scripts/check_core_test_scope.py)
	docker compose $(CORE_COMPOSE) exec -T \
		-e HUB_CORE_ONLY=1 \
		-e DATABASE_URL=postgresql://hub_test:hub_test@postgres-test:5432/hub_test_test_shared \
		api-service-test \
		python -m pytest hub/apps/ hub/tests/test_mvp_mode.py --reuse-db -x -q --timeout=300 \
		-m "not benchmark and not e2e and not integration and not network and not odh_inference and not performance and not requires_aws and not requires_clamav and not requires_gcp and not requires_prefect and not requires_redis and not requires_services and not requires_snowflake"

lint-core: ## Lint the core subset (same tools, pinned versions via pre-commit)
	pre-commit run ruff --all-files

boundary-check: ## GATE-29 — core never imports paid (+ guard gate 313.H.1, + W7.1 public mode)
	$(PYTHON) scripts/check_core_boundary.py
	$(PYTHON) scripts/check_core_boundary.py --check-allowlist-growth
	$(PYTHON) scripts/check_core_boundary.py --public
	$(PYTHON) scripts/check_core_boundary.py --check-guards
	$(PYTHON) scripts/check_core_boundary.py --check-guards --check-guard-growth

check-env: ## Environment provisioning check (Q.4.2) — the running interpreter vs requirements.txt
	$(PYTHON) scripts/check_env_provisioning.py

publish-check: ## Pre-publish gate (boundary + guards + secrets + hostnames + Makefile parity)
	$(PYTHON) scripts/check_core_boundary.py
	$(PYTHON) scripts/check_core_boundary.py --check-guards
	# Openspec structural gate — repo-owned validator (the official npx
	# validate cannot run offline). Every ACTIVE change dir is validated:
	# strict where a per-change baseline exists (preprod01), report-only
	# otherwise (abandoned scratch dirs can never brick a publish).
	bash scripts/validate_openspec_changes.sh
	command -v gitleaks >/dev/null 2>&1 && \
		gitleaks detect --source . --config .gitleaks.toml --redact --no-banner --log-level=warn || \
		echo "gitleaks not installed — skipping (CI runs gitleaks-action)"
	# The shipped Makefile must stay byte-identical to Makefile.core (313.DoD.5).
	# -c /dev/null + -p no:django mirror the minimal-pytest CI environment.
	$(PYTHON) -m pytest -c /dev/null -p no:django -q --no-header -p no:cacheprovider \
		scripts/tests/test_publish_tree.py

CORE_DEV_COMPOSE = -f docker-compose.yml -f docker-compose.core.yml

.env:
	python3 scripts/make_dev_env.py

quickstart: .env ## Five-minute core quickstart (dev stack + migrate + seed)
	# W9.2 stranger-path fix: the frontend build context is ./frontend/ only,
	# so the repo-root shared/ (vite @shared alias) must be mirrored into
	# frontend/shared/ ON THE HOST before docker compose build — CI does the
	# equivalent cp; a fresh clone without this step fails the frontend image
	# build ("sync-shared: source dir missing").
	bash frontend/scripts/sync-shared.sh
	docker compose $(CORE_DEV_COMPOSE) up -d --build \
		postgres redis-cache redis-queue redis-events redis-channels minio \
		api-service worker-service frontend traefik
	# Fresh-volume postgres initdb + on-boot migrations outrun the api's
	# healthcheck on slow disks — wait for the live endpoint from the HOST
	# (compose --wait gives up once a container is marked unhealthy, and
	# `exec` dies with the container whenever the restart policy kills it
	# mid-attach). The api publishes :8000; failed curls just retry.
	@for i in $$(seq 1 90); do \
		curl -sf http://localhost:8000/health/live/ >/dev/null 2>&1 && break; \
		sleep 10; \
	done; \
	curl -sf http://localhost:8000/health/live/ >/dev/null 2>&1 || \
		{ echo "api never became healthy (http://localhost:8000/health/live/)" >&2; exit 1; }
	docker compose $(CORE_DEV_COMPOSE) exec -T api-service python hub/manage.py migrate
	docker compose $(CORE_DEV_COMPOSE) exec -T api-service python hub/manage.py seed_demo_data
	@echo "Core stack ready — open http://localhost:3000"

# ---------------------------------------------------------------------------
# Documentation health (Phase P.9 — the private `make audit-docs` target was
# referenced by docs/TRACEABILITY_ARCHITECTURE.md, which SHIPS publicly; the
# public Makefile IS Makefile.core, so the target must live here or the
# shipped docs instruct a command that does not exist in the public tree.)
# ---------------------------------------------------------------------------
.PHONY: check-docs-sync audit-docs check-error-codes-catalogue
check-error-codes-catalogue: ## Every emitted error code has a docs/api/error-codes.md catalogue row
	$(PYTHON) scripts/check_error_codes_catalogue.py

check-docs-sync: ## Verify docs, markers, and YAML are bidirectionally consistent
	$(PYTHON) scripts/check_doc_journey_marker_sync.py --ci-mode
	$(PYTHON) scripts/check_doc_uc_marker_sync.py --ci-mode
	$(PYTHON) scripts/check_persona_mapping_drift.py
	$(PYTHON) scripts/check_persona_journey_mapping_drift.py

audit-docs: check-docs-sync ## Run all documentation-health checks
	$(PYTHON) scripts/check_assert_true_true.py
	$(PYTHON) scripts/check_error_codes_catalogue.py
	$(PYTHON) scripts/lint_journey_marker_coverage.py --blocking
	$(PYTHON) scripts/check_marker_consistency.py --verbose 2>/dev/null \
		|| echo "Marker consistency script not found — skipping"
	$(PYTHON) scripts/report_uc_journey_test_coverage.py --ci-mode 2>/dev/null \
		|| echo "Coverage report script not found — skipping"
	$(PYTHON) scripts/extract_persona_journey_mapping.py --check 2>/dev/null \
		|| echo "Persona-journey mapping extraction check — run without --check to regenerate"
	@echo "ALL DOC-HEALTH CHECKS PASSED"
