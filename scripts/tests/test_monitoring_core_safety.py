"""Core-mode observability no-data-safety pin (Phase P.8).

The shipped ``prometheus.yml`` defines scrape jobs for paid-only services
(semantic/dq/compliance/datacontract/prefect/search + k8s-only sidecars).
In the OSS tree those targets do not exist, so Prometheus marks them down,
``up{job=...} == 0`` holds, and the ServiceDown / SemanticFusekiDown /
PrefectDown rules fire continuously for services the OSS deployment does
not have — alert noise with no data. The core overlay therefore must
switch monitoring onto a core-safe config the way it already switches
traefik onto ``traefik.core.yml``.

This suite pins, with the REAL files:

1. ``monitoring/prometheus/prometheus.core.yml`` — parses; its scrape jobs
   are a subset of the full config's (no drift/typos) and contain no
   paid-only jobs (no-data-safety).
2. Every paid-only job referenced by an ``up{...}`` alert rule in the
   shipped rule set is ABSENT from the core scrape config — the precise
   mechanism by which the paid ``up`` rules stay inert in the OSS tree.
3. ``monitoring/alertmanager/alertmanager.core.yml`` — parses; no
   unresolved ``${VAR}`` placeholders; every route references a defined
   receiver; no receiver declares a delivery channel (no-op, so nothing
   can mis-deliver when a rule has no data or an alert has no route).
4. ``docker-compose.core.yml`` overrides the prometheus/alertmanager
   config mounts onto the ``.core.yml`` variants (mirroring the
   traefik.core.yml precedent).

Runs in the private repo AND in the public CI (all files it reads ship).
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MONITORING = REPO_ROOT / "monitoring" / "prometheus"
PROMETHEUS_YML = MONITORING / "prometheus.yml"
PROMETHEUS_CORE_YML = MONITORING / "prometheus.core.yml"
ALERTMANAGER_CORE_YML = REPO_ROOT / "monitoring" / "alertmanager" / "alertmanager.core.yml"
COMPOSE_CORE_YML = REPO_ROOT / "docker-compose.core.yml"

# The jobs the full dev scrape config defines for services that the OSS
# core stack does not deploy (paid layer or k8s-only sidecars). Must match
# the job names in prometheus.yml; a rename there must fail here too
# (test_core_config_is_a_subset_of_the_full_config).
PAID_ONLY_JOBS = frozenset(
    {
        "semantic-service",
        "dq-service",
        "compliance-service",
        "datacontract-service",
        "prefect-integration-service",
        "search-service",
        "event-bus-health-service",
        "workflow-engine-service",
        "workflow-registry-service",
        "event-schema-registry-service",
    }
)


class _ComposeSafeLoader(yaml.SafeLoader):
    """SafeLoader that understands compose's ``!reset`` tag (the core
    overlay nulls keys like ``build: !reset null``)."""


def _construct_reset(loader, node):
    # `!reset X` in compose semantics replaces the key's inherited value
    # with X (or the default when bare). Structurally, resolve the tag to
    # X of whatever node type it wraps (scalar/sequence/mapping/null).
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    return loader.construct_scalar(node)


_ComposeSafeLoader.add_constructor("!reset", _construct_reset)


def _load_yaml(path: Path) -> dict:
    doc = yaml.load(path.read_text(encoding="utf-8"), Loader=_ComposeSafeLoader)
    assert doc is not None, f"{path} is empty or unparsable"
    return doc


def scrape_job_names(path: Path) -> set[str]:
    return {job["job_name"] for job in _load_yaml(path).get("scrape_configs", [])}


def _up_rule_jobs(path: Path) -> set[str]:
    """Job names referenced by `up{job=...}` selectors in a rule file."""
    import re

    text = path.read_text(encoding="utf-8")
    return set(re.findall(r'up\{job=~?"([^"]+)"', text)) | {
        m for expr in re.findall(r"up\{job=([^}]+)\}", text) for m in re.findall(r'"([^"]+)"', expr)
    }


class TestCoreScrapeConfig:
    def test_core_config_exists_and_parses(self):
        assert PROMETHEUS_CORE_YML.exists(), (
            "monitoring/prometheus/prometheus.core.yml is missing — the core "
            "overlay cannot switch monitoring onto a core-safe scrape config"
        )
        _load_yaml(PROMETHEUS_CORE_YML)

    def test_core_config_scrapes_no_paid_only_jobs(self):
        core_jobs = scrape_job_names(PROMETHEUS_CORE_YML)
        leaked = core_jobs & PAID_ONLY_JOBS
        assert leaked == set(), (
            f"prometheus.core.yml scrapes paid-only jobs {sorted(leaked)} — in "
            "the OSS tree those targets do not exist, `up == 0` holds, and "
            "the ServiceDown/SemanticFusekiDown/PrefectDown rules page for "
            "services the deployment does not have"
        )

    def test_core_config_is_a_subset_of_the_full_config(self):
        """No drift/typos: every core job must exist in the full config."""
        core_jobs = scrape_job_names(PROMETHEUS_CORE_YML)
        full_jobs = scrape_job_names(PROMETHEUS_YML)
        assert core_jobs <= full_jobs, (
            f"core scrape jobs not present in prometheus.yml: {sorted(core_jobs - full_jobs)}"
        )

    def test_every_paid_up_rule_is_inert_in_the_core_config(self):
        """For every alert rule that watches `up{job=X}` for a PAID job X,
        X must be absent from the core scrape config — otherwise the rule
        fires with no data in the OSS tree."""
        core_jobs = scrape_job_names(PROMETHEUS_CORE_YML)
        paid_rule_jobs: set[str] = set()
        for rule_file in [
            MONITORING / "alerts.yml",
            *sorted((MONITORING / "alerts").glob("*.yml")),
        ]:
            paid_rule_jobs |= _up_rule_jobs(rule_file) & PAID_ONLY_JOBS
        assert paid_rule_jobs, "sanity: paid up{} rules must exist for this pin to mean anything"
        assert paid_rule_jobs & core_jobs == set(), (
            f"paid jobs {sorted(paid_rule_jobs & core_jobs)} are scraped by the "
            "core config AND watched by up{} rules — they fire with no data"
        )

    def test_rule_files_referenced_by_the_core_config_exist(self):
        doc = _load_yaml(PROMETHEUS_CORE_YML)
        for rule_file in doc.get("rule_files", []):
            assert (MONITORING / rule_file).exists(), (
                f"prometheus.core.yml references missing rule file {rule_file!r}"
            )

    def test_red_drill_paid_job_in_core_config_is_detected(self, tmp_path):
        """Guard-the-guard: the paid-job scan must bite when a paid job is
        (re-)added to the core config."""
        doc = _load_yaml(PROMETHEUS_CORE_YML)
        doc["scrape_configs"].append(
            {"job_name": "semantic-service", "static_configs": [{"targets": ["x:1"]}]}
        )
        drilled = tmp_path / "drilled.core.yml"
        drilled.write_text(yaml.safe_dump(doc))
        leaked = scrape_job_names(drilled) & PAID_ONLY_JOBS
        assert leaked == {"semantic-service"}


class TestCoreAlertmanagerConfig:
    def test_core_config_exists_and_parses(self):
        assert ALERTMANAGER_CORE_YML.exists(), (
            "monitoring/alertmanager/alertmanager.core.yml is missing — the "
            "shipped base compose mounts ./monitoring/alertmanager/"
            "alertmanager.yml, which does NOT ship; the core overlay must "
            "provide a mountable core-safe config"
        )
        _load_yaml(ALERTMANAGER_CORE_YML)

    def test_no_unresolved_placeholders(self):
        import re

        text = ALERTMANAGER_CORE_YML.read_text(encoding="utf-8")
        placeholders = re.findall(r"\$\{[A-Za-z0-9_]+\}", text)
        assert placeholders == [], (
            f"alertmanager.core.yml carries env placeholders {placeholders} — "
            "the OSS tree has no deploy pipeline to substitute them"
        )

    def test_every_route_references_a_defined_receiver(self):
        doc = _load_yaml(ALERTMANAGER_CORE_YML)
        receivers = {r["name"] for r in doc.get("receivers", [])}
        route = doc.get("route", {})
        assert route.get("receiver") in receivers
        for child in route.get("routes", []):
            assert child.get("receiver") in receivers, (
                f"route to undefined receiver {child.get('receiver')!r}"
            )

    def test_receivers_declare_no_delivery_channel(self):
        """No-op delivery: nothing can mis-deliver when a rule has no data
        or an alert has no matching route."""
        doc = _load_yaml(ALERTMANAGER_CORE_YML)
        channels = (
            "webhook_configs",
            "email_configs",
            "pagerduty_configs",
            "slack_configs",
            "opsgenie_configs",
            "victorops_configs",
            "pushover_configs",
            "telegram_configs",
            "wechat_configs",
            "sns_configs",
            "discord_configs",
            "webex_configs",
        )
        for receiver in doc.get("receivers", []):
            declared = [c for c in channels if receiver.get(c)]
            assert declared == [], (
                f"receiver {receiver['name']!r} declares delivery channels "
                f"{declared} — the core config must not deliver anywhere"
            )


class TestCoreComposeOverrides:
    def _service_volumes(self, service: str) -> list[str]:
        doc = _load_yaml(COMPOSE_CORE_YML)
        volumes = doc.get("services", {}).get(service, {}).get("volumes", [])
        return [str(v) for v in volumes]

    def test_core_overlay_mounts_the_core_prometheus_config(self):
        volumes = self._service_volumes("prometheus")
        assert any("prometheus.core.yml:/etc/prometheus/prometheus.yml" in v for v in volumes), (
            f"docker-compose.core.yml does not override the prometheus config "
            f"mount ({volumes}) — the traefik.core.yml precedent requires the "
            "core-safe scrape config whenever monitoring is enabled in the "
            "core stack"
        )

    def test_core_overlay_mounts_the_core_alertmanager_config(self):
        volumes = self._service_volumes("alertmanager")
        assert any(
            "alertmanager.core.yml:/etc/alertmanager/alertmanager.yml" in v for v in volumes
        ), (
            f"docker-compose.core.yml does not override the alertmanager config "
            f"mount ({volumes}) — the base compose mounts alertmanager.yml, "
            "which does not ship in the public tree"
        )
