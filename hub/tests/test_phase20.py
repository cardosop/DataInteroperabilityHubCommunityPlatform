"""
Phase 20 — Security Hardening: Static Validation Tests
=======================================================

Validates all 7 security hardening items (20.1–20.7) plus 4 review gap
fixes by statically parsing the relevant config / infrastructure files.

No Docker, AWS, Kubernetes or database runtime needed — every check
inspects the files on disk, confirming the stated implementation.

Test layout
-----------
  TestSESIdentityScoping         — 20.1 SES IAM wildcard removed
  TestALBControllerTagConditions — 20.2 Cluster-ownership conditions
  TestServiceAccountTokenOptOut  — 20.3 automountServiceAccountToken opt-out
  TestPromtailNonRoot            — 20.4 Promtail UID / no docker.sock
  TestDBEgressRemoved            — 20.5 RDS + ElastiCache egress rules gone
  TestTrivyGateHardening         — 20.6 force_deploy bypass removed
  TestTraefikACMEEmail           — 20.7 ACME email externalised
  TestReviewGapFixes             — caller wiring + stale comment fixes
"""

import re
import pathlib

import yaml

# ---------------------------------------------------------------------------
# Repo root — resolves to /app/ inside the Docker test container
# (hub/tests/test_phase20.py → hub/tests/ → hub/ → /app/)
# ---------------------------------------------------------------------------
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(rel: str) -> str:
    """Read a repo-relative file as text."""
    path = REPO_ROOT / rel
    assert path.exists(), f"Expected file not found: {path}"
    return path.read_text(encoding="utf-8")


def _non_comment_lines(text: str, comment_prefix: str = "#") -> str:
    """Return only non-comment, non-blank lines joined as a single string."""
    lines = [
        line for line in text.splitlines()
        if line.strip() and not line.strip().startswith(comment_prefix)
    ]
    return "\n".join(lines)


def _yaml(rel: str):
    """Parse a repo-relative YAML file."""
    return yaml.safe_load(_read(rel))


def _yaml_safe(rel: str):
    """Parse YAML, returning None on parse error (used for complex workflow files)."""
    try:
        return yaml.safe_load(_read(rel))
    except yaml.YAMLError:
        return None


# ===========================================================================
# 20.1 — SES IAM resources scoped to specific identity ARN
# ===========================================================================

class TestSESIdentityScoping:
    TF_MAIN = "infrastructure/terraform/modules/iam-irsa/main.tf"
    TF_VARS = "infrastructure/terraform/modules/iam-irsa/variables.tf"

    def test_ses_sender_identity_variable_declared(self):
        text = _read(self.TF_VARS)
        assert 'variable "ses_sender_identity"' in text, (
            "ses_sender_identity variable must be declared in iam-irsa/variables.tf"
        )

    def test_ses_sender_identity_has_description(self):
        text = _read(self.TF_VARS)
        # The variable block must document what values are accepted
        var_block = re.search(
            r'variable\s+"ses_sender_identity"\s*\{(.*?)\}',
            text,
            re.DOTALL,
        )
        assert var_block, "ses_sender_identity variable block not found"
        assert "description" in var_block.group(1), (
            "ses_sender_identity variable must have a description"
        )

    def test_data_aws_caller_identity_declared(self):
        text = _read(self.TF_MAIN)
        assert 'data "aws_caller_identity" "current"' in text, (
            "data.aws_caller_identity.current must be declared in iam-irsa/main.tf"
        )

    def test_data_aws_region_declared(self):
        text = _read(self.TF_MAIN)
        assert 'data "aws_region" "current"' in text, (
            "data.aws_region.current must be declared in iam-irsa/main.tf"
        )

    def test_ses_identity_arn_local_computed(self):
        text = _read(self.TF_MAIN)
        assert "ses_identity_arn" in text, (
            "local.ses_identity_arn must be computed in iam-irsa/main.tf"
        )

    def test_ses_identity_arn_uses_data_sources(self):
        text = _read(self.TF_MAIN)
        # The ARN must be constructed from account + region data sources
        assert "data.aws_region.current" in text
        assert "data.aws_caller_identity.current" in text
        # And the ARN format must include the identity variable
        assert "var.ses_sender_identity" in text

    def test_ses_identity_arn_format_correct(self):
        text = _read(self.TF_MAIN)
        # The constructed ARN must follow the canonical SES identity ARN format
        arn_pattern = re.search(
            r'ses_identity_arn\s*=\s*"arn:aws:ses:\$\{.*?region.*?\}:\$\{.*?account_id.*?\}:identity/\$\{.*?ses_sender_identity.*?\}"',
            text,
        )
        assert arn_pattern, (
            "ses_identity_arn local must be formatted as "
            "arn:aws:ses:<region>:<account_id>:identity/<ses_sender_identity>"
        )

    def test_api_service_ses_resources_not_wildcard(self):
        text = _read(self.TF_MAIN)
        # Find the api_service_policy SES statement
        ses_blocks = list(re.finditer(
            r'sid\s*=\s*"SESAccess"(.*?)(?=\n\s*\})',
            text,
            re.DOTALL,
        ))
        assert ses_blocks, "At least one SESAccess statement must exist"
        for m in ses_blocks:
            block = m.group(1)
            assert 'resources = ["*"]' not in block, (
                "SESAccess statement must not use wildcard resource '*'"
            )
            assert "ses_identity_arn" in block, (
                "SESAccess statement must use local.ses_identity_arn"
            )

    def test_worker_service_ses_resources_not_wildcard(self):
        """Both api_service_policy and worker_service_policy must scope SES."""
        text = _read(self.TF_MAIN)
        # Count how many times ses_identity_arn appears in resources contexts
        occurrences = text.count("local.ses_identity_arn")
        assert occurrences >= 2, (
            f"local.ses_identity_arn must appear at least twice (api + worker policy), "
            f"found {occurrences}"
        )


# ===========================================================================
# 20.2 — ALB Controller cluster-ownership tag conditions
# ===========================================================================

class TestALBControllerTagConditions:
    TF_MAIN = "infrastructure/terraform/modules/iam-irsa/main.tf"

    def test_request_tag_condition_present(self):
        text = _read(self.TF_MAIN)
        assert "aws:RequestTag/kubernetes.io/cluster/" in text, (
            "Create* statements must carry aws:RequestTag/kubernetes.io/cluster/ condition"
        )

    def test_resource_tag_condition_present(self):
        text = _read(self.TF_MAIN)
        assert "aws:ResourceTag/kubernetes.io/cluster/" in text, (
            "Delete/Modify statements must carry aws:ResourceTag/kubernetes.io/cluster/ condition"
        )

    def test_create_listener_and_rule_sid_exists(self):
        text = _read(self.TF_MAIN)
        assert '"CreateListenerAndRule"' in text, (
            "CreateListenerAndRule Sid must exist (separated from Delete)"
        )

    def test_delete_listener_and_rule_sid_exists(self):
        text = _read(self.TF_MAIN)
        assert '"DeleteListenerAndRule"' in text, (
            "DeleteListenerAndRule Sid must exist (separated from Create)"
        )

    def test_describe_all_sid_unrestricted(self):
        text = _read(self.TF_MAIN)
        assert '"DescribeAll"' in text, (
            "DescribeAll Sid must exist (read-only, no cluster condition needed)"
        )

    def test_describe_ancillary_sid_unrestricted(self):
        text = _read(self.TF_MAIN)
        assert '"DescribeAncillary"' in text

    def test_required_create_sids_present(self):
        text = _read(self.TF_MAIN)
        for sid in ('"CreateSLR"', '"CreateSG"', '"CreateLBAndTG"'):
            assert sid in text, f"Required Sid {sid} missing from ALB controller policy"

    def test_required_modify_delete_sids_present(self):
        text = _read(self.TF_MAIN)
        for sid in ('"ModifyDeleteLBAndTG"', '"RegisterDeregisterTargets"',
                    '"ModifyListenerAndRule"', '"DeleteSG"'):
            assert sid in text, f"Required Sid {sid} missing from ALB controller policy"

    def test_create_sids_use_request_tag(self):
        """CreateLBAndTG and CreateSG blocks must use RequestTag (not ResourceTag)."""
        text = _read(self.TF_MAIN)
        # Find CreateLBAndTG block and assert it has RequestTag
        create_block = re.search(
            r'"CreateLBAndTG".*?(?=\n\s*\{?\s*Sid\s*=|\Z)',
            text,
            re.DOTALL,
        )
        assert create_block, "CreateLBAndTG block not found"
        assert "RequestTag" in create_block.group(0), (
            "CreateLBAndTG must use aws:RequestTag condition (not ResourceTag)"
        )

    def test_delete_sids_use_resource_tag(self):
        """ModifyDeleteLBAndTG block must use ResourceTag (not RequestTag)."""
        text = _read(self.TF_MAIN)
        delete_block = re.search(
            r'"ModifyDeleteLBAndTG".*?(?=\n\s*\{?\s*Sid\s*=|\Z)',
            text,
            re.DOTALL,
        )
        assert delete_block, "ModifyDeleteLBAndTG block not found"
        assert "ResourceTag" in delete_block.group(0), (
            "ModifyDeleteLBAndTG must use aws:ResourceTag condition"
        )


# ===========================================================================
# 20.3 — automountServiceAccountToken global opt-out + Prefect opt-in
# ===========================================================================

class TestServiceAccountTokenOptOut:
    SA_YAML = "helm/templates/serviceaccount.yaml"
    PREFECT_YAML = "helm/templates/prefect/worker-deployment.yaml"

    def test_serviceaccount_opts_out(self):
        text = _read(self.SA_YAML)
        assert "automountServiceAccountToken: false" in text, (
            "Global ServiceAccount must have automountServiceAccountToken: false"
        )

    def test_serviceaccount_does_not_opt_in(self):
        # Strip comment lines — the explanatory comment intentionally mentions
        # "automountServiceAccountToken: true" as guidance for opt-in callers.
        code = _non_comment_lines(_read(self.SA_YAML))
        assert "automountServiceAccountToken: true" not in code, (
            "Global ServiceAccount must NOT contain automountServiceAccountToken: true"
            " outside of comments"
        )

    def test_prefect_worker_opts_in(self):
        text = _read(self.PREFECT_YAML)
        assert "automountServiceAccountToken: true" in text, (
            "Prefect worker deployment must explicitly opt in with automountServiceAccountToken: true"
        )

    def test_only_prefect_worker_opts_in(self):
        """Scan all helm templates — only the prefect worker may opt in."""
        helm_dir = REPO_ROOT / "helm" / "templates"
        prefect_worker = REPO_ROOT / self.PREFECT_YAML
        violations = []
        for tf in helm_dir.rglob("*.yaml"):
            if tf.resolve() == prefect_worker.resolve():
                continue
            # Use non-comment lines: SA file has the string in an explanatory comment
            code = _non_comment_lines(tf.read_text())
            if "automountServiceAccountToken: true" in code:
                violations.append(str(tf.relative_to(REPO_ROOT)))
        assert not violations, (
            "Only the Prefect worker should opt in to token mounting. "
            f"Unexpected opt-ins found in: {violations}"
        )

    def test_prefect_worker_has_rbac_sa(self):
        """The Prefect worker must reference a dedicated service account."""
        text = _read(self.PREFECT_YAML)
        assert "serviceAccountName" in text, (
            "Prefect worker pod spec must set serviceAccountName"
        )


# ===========================================================================
# 20.4 — Promtail non-root, no Docker socket, static file targets
# ===========================================================================

class TestPromtailNonRoot:
    COMPOSE = "docker-compose.production.yml"
    PROMTAIL_CFG = "monitoring/promtail/promtail.yaml"

    def _compose(self):
        return _yaml(self.COMPOSE)

    def _promtail_svc(self):
        return self._compose()["services"]["promtail"]

    def test_promtail_user_is_non_root(self):
        user = self._promtail_svc().get("user", "")
        assert user == "10001:10001", (
            f"Promtail must run as user 10001:10001, got: {user!r}"
        )

    def test_promtail_no_docker_sock_volume(self):
        volumes = self._promtail_svc().get("volumes", [])
        docker_sock = [v for v in volumes if "docker.sock" in str(v)]
        assert not docker_sock, (
            f"Promtail must not mount docker.sock; found: {docker_sock}"
        )

    def test_promtail_no_docker_containers_dir(self):
        volumes = self._promtail_svc().get("volumes", [])
        docker_containers = [v for v in volumes if "/var/lib/docker/containers" in str(v)]
        assert not docker_containers, (
            f"Promtail must not mount /var/lib/docker/containers; found: {docker_containers}"
        )

    def test_promtail_log_dir_mounted_readonly(self):
        volumes = self._promtail_svc().get("volumes", [])
        log_mounts = [v for v in volumes if "/var/log/containers" in str(v)]
        assert log_mounts, "Promtail must bind-mount /var/log/containers"
        assert any(":ro" in str(v) for v in log_mounts), (
            "Promtail /var/log/containers bind-mount must be read-only (:ro)"
        )

    def test_promtail_positions_volume_present(self):
        volumes = self._promtail_svc().get("volumes", [])
        pos = [v for v in volumes if "/var/lib/promtail" in str(v)]
        assert pos, "Promtail must mount the positions volume at /var/lib/promtail"

    def test_promtail_positions_volume_named_at_top_level(self):
        top_volumes = self._compose().get("volumes", {})
        assert "promtail_positions" in top_volumes, (
            "promtail_positions named volume must be declared at the top-level volumes section"
        )

    def test_promtail_config_no_docker_sd_configs(self):
        # Strip comment lines: the header comment says "Replaces docker_sd_configs"
        # to document the migration; the actual config must not reference it.
        code = _non_comment_lines(_read(self.PROMTAIL_CFG))
        assert "docker_sd_configs" not in code, (
            "Promtail must not use docker_sd_configs — requires Docker socket"
        )

    def test_promtail_config_uses_static_configs_for_containers(self):
        cfg = _yaml(self.PROMTAIL_CFG)
        jobs = cfg.get("scrape_configs", [])
        containers_job = next(
            (j for j in jobs if j.get("job_name") == "containers"), None
        )
        assert containers_job is not None, "Promtail must have a 'containers' scrape_config job"
        assert "static_configs" in containers_job, (
            "Promtail 'containers' job must use static_configs"
        )

    def test_promtail_config_targets_log_dir(self):
        cfg = _yaml(self.PROMTAIL_CFG)
        jobs = cfg.get("scrape_configs", [])
        containers_job = next(
            (j for j in jobs if j.get("job_name") == "containers"), None
        )
        assert containers_job is not None
        static_cfgs = containers_job.get("static_configs", [])
        all_paths = " ".join(
            str(sc.get("labels", {}).get("__path__", ""))
            for sc in static_cfgs
        )
        assert "/var/log/containers" in all_paths, (
            "Promtail static_configs must target /var/log/containers"
        )

    def test_promtail_positions_file_not_in_tmp(self):
        cfg = _yaml(self.PROMTAIL_CFG)
        pos_file = cfg.get("positions", {}).get("filename", "")
        assert "/tmp" not in pos_file, (
            f"Promtail positions file must not use /tmp; got {pos_file!r}"
        )
        assert "/var/lib/promtail" in pos_file, (
            f"Promtail positions file must be under /var/lib/promtail; got {pos_file!r}"
        )

    def test_promtail_pipeline_unwraps_docker_json_envelope(self):
        """The pipeline must parse the Docker json-file outer envelope {log, stream, time}."""
        cfg = _yaml(self.PROMTAIL_CFG)
        jobs = cfg.get("scrape_configs", [])
        containers_job = next(
            (j for j in jobs if j.get("job_name") == "containers"), None
        )
        assert containers_job is not None
        stages = containers_job.get("pipeline_stages", [])
        # First json stage must extract the 'log' field from the Docker envelope
        json_stages = [s for s in stages if "json" in s]
        assert json_stages, "Pipeline must have at least one json stage"
        first_json_exprs = json_stages[0]["json"].get("expressions", {})
        # The Docker envelope keys must be present
        assert any("log" in str(v) for v in first_json_exprs.values()), (
            "First pipeline json stage must extract the 'log' field from Docker json-file envelope"
        )


# ===========================================================================
# 20.5 — Wildcard egress removed from RDS and ElastiCache SGs
# ===========================================================================

class TestDBEgressRemoved:
    TF_VPC = "infrastructure/terraform/modules/vpc/main.tf"

    def test_rds_egress_all_resource_removed(self):
        # Strip comment lines: the removal comment retains the resource name
        # as documentation of what was removed, e.g.:
        #   # resource "aws_security_group_rule" "rds_egress_all" { ... }  ← REMOVED
        code = _non_comment_lines(_read(self.TF_VPC))
        assert 'resource "aws_security_group_rule" "rds_egress_all"' not in code, (
            "rds_egress_all security group rule must be removed (20.5)"
        )

    def test_elasticache_egress_all_resource_removed(self):
        code = _non_comment_lines(_read(self.TF_VPC))
        assert (
            'resource "aws_security_group_rule" "elasticache_egress_all"'
            not in code
        ), "elasticache_egress_all security group rule must be removed (20.5)"

    def test_no_wildcard_egress_cidr_on_rds_sg(self):
        """Ensure 0.0.0.0/0 egress does not appear in any rule scoped to the RDS SG."""
        text = _read(self.TF_VPC)
        # Find any resource block that references rds SG and has 0.0.0.0/0
        match = re.search(
            r'aws_security_group\.rds\.id[^}]*?0\.0\.0\.0/0',
            text,
            re.DOTALL,
        )
        assert match is None, (
            "No rule referencing the RDS security group may use 0.0.0.0/0 CIDR"
        )

    def test_no_wildcard_egress_cidr_on_elasticache_sg(self):
        """Ensure 0.0.0.0/0 egress does not appear in any rule scoped to the ElastiCache SG."""
        text = _read(self.TF_VPC)
        match = re.search(
            r'aws_security_group\.elasticache\.id[^}]*?0\.0\.0\.0/0',
            text,
            re.DOTALL,
        )
        assert match is None, (
            "No rule referencing the ElastiCache security group may use 0.0.0.0/0 CIDR"
        )

    def test_rds_ingress_rule_still_present(self):
        """Sanity: removing egress must not remove the ingress rule."""
        text = _read(self.TF_VPC)
        assert "rds_ingress_postgres" in text, (
            "RDS ingress rule must still exist after removing the egress rule"
        )

    def test_elasticache_ingress_rule_still_present(self):
        text = _read(self.TF_VPC)
        assert "elasticache_ingress_redis" in text, (
            "ElastiCache ingress rule must still exist after removing the egress rule"
        )


# ===========================================================================
# 20.6 — Trivy gate hardening: no force_deploy bypass
# ===========================================================================

class TestTrivyGateHardening:
    DEPLOY_YML = ".github/workflows/deploy.yml"

    def _workflow(self):
        cfg = _yaml_safe(self.DEPLOY_YML)
        assert cfg is not None, f"Failed to parse {self.DEPLOY_YML} as YAML"
        return cfg

    def test_no_force_deploy_workflow_input(self):
        cfg = self._workflow()
        on_section = cfg.get("on") or cfg.get(True) or {}  # 'on' can be parsed as True in PyYAML
        # Try both 'on' (string) and True (bool — PyYAML quirk with bare 'on')
        if isinstance(on_section, dict):
            wd = on_section.get("workflow_dispatch", {}) or {}
        else:
            # 'on' key might have been parsed as True
            on_section = cfg.get(True, {}) or {}
            wd = on_section.get("workflow_dispatch", {}) or {}
        inputs = wd.get("inputs", {}) or {}
        assert "force_deploy" not in inputs, (
            "force_deploy workflow input must not exist in deploy.yml workflow_dispatch"
        )

    def test_force_deploy_only_appears_in_comments(self):
        """Every line containing 'force_deploy' must be a YAML comment."""
        text = _read(self.DEPLOY_YML)
        violations = []
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if "force_deploy" in stripped and not stripped.startswith("#"):
                violations.append(f"  line {lineno}: {line!r}")
        assert not violations, (
            "force_deploy must only appear in comments (# lines). Violations:\n"
            + "\n".join(violations)
        )

    def test_no_force_deploy_conditional_in_exit_code(self):
        """The old conditional expression must be completely gone."""
        text = _read(self.DEPLOY_YML)
        # Old pattern: ${{ (github.event.inputs.force_deploy == 'true') && '0' || '1' }}
        assert "force_deploy == 'true'" not in text, (
            "Old force_deploy conditional must not appear in exit-code expressions"
        )
        assert "force_deploy == \"true\"" not in text

    def test_all_trivy_gate_steps_use_exit_code_1(self):
        """All gate steps (one per service) must use the literal string '1', not a conditional."""
        cfg = self._workflow()
        scan_steps = cfg.get("jobs", {}).get("scan", {}).get("steps", [])
        gate_steps = [
            s for s in scan_steps
            if isinstance(s.get("name"), str) and s["name"].startswith("Trivy gate")
        ]
        assert len(gate_steps) == 7, (
            f"Expected exactly 7 Trivy gate steps (one per service), found {len(gate_steps)}"
        )
        for step in gate_steps:
            ec = str(step.get("with", {}).get("exit-code", ""))
            assert ec == "1", (
                f"Trivy gate step '{step['name']}' must have exit-code: '1', got {ec!r}"
            )

    def test_failure_notification_step_present(self):
        """A step with if: failure() must exist in the scan job."""
        cfg = self._workflow()
        scan_steps = cfg.get("jobs", {}).get("scan", {}).get("steps", [])
        notify = [
            s for s in scan_steps
            if s.get("if") == "failure()"
            and "notify" in s.get("name", "").lower()
        ]
        assert notify, (
            "The scan job must contain an if:failure() notification step"
        )

    def test_notification_step_references_slack_secret(self):
        """The notification step must reference the Slack webhook secret."""
        text = _read(self.DEPLOY_YML)
        assert "SLACK_SECURITY_WEBHOOK_URL" in text, (
            "Notification step must reference secrets.SLACK_SECURITY_WEBHOOK_URL"
        )

    def test_notification_step_creates_github_issue(self):
        """The notification step must create a GitHub issue as durable audit trail."""
        text = _read(self.DEPLOY_YML)
        assert "gh issue create" in text, (
            "Notification step must create a GitHub issue for durable audit trail"
        )

    def test_job5_comment_no_stale_force_deploy(self):
        """The Job 5 header comment must not instruct using force_deploy=true."""
        text = _read(self.DEPLOY_YML)
        assert "set force_deploy=true input to downgrade exit-code to 0" not in text, (
            "Stale Job-5 comment referencing force_deploy bypass must be removed"
        )


# ===========================================================================
# 20.7 — Traefik ACME email externalised via env var
# ===========================================================================

class TestTraefikACMEEmail:
    TRAEFIK_CFG = "infrastructure/traefik/traefik.yml"
    COMPOSE = "docker-compose.production.yml"
    ENV_TEMPLATE = ".env.production.template"

    def test_no_hardcoded_hub_example_email_in_traefik_cfg(self):
        text = _read(self.TRAEFIK_CFG)
        assert "admin@hub.example.com" not in text, (
            "traefik.yml must not contain the hardcoded admin@hub.example.com placeholder"
        )

    def test_no_hardcoded_email_in_acme_section(self):
        cfg = _yaml(self.TRAEFIK_CFG)
        # Traefik YAML: certificatesResolvers.letsencrypt.acme.email
        resolvers = cfg.get("certificatesResolvers", {})
        le = resolvers.get("letsencrypt", {})
        acme = le.get("acme", {})
        email_value = acme.get("email", "")
        # Must use an env var placeholder, not a literal email address
        assert "@" not in email_value or "${" in email_value, (
            f"ACME email must use an env var placeholder, got literal: {email_value!r}"
        )

    def test_traefik_acme_email_uses_env_var_placeholder(self):
        text = _read(self.TRAEFIK_CFG)
        assert "${TRAEFIK_ACME_EMAIL}" in text, (
            "traefik.yml ACME email must use ${TRAEFIK_ACME_EMAIL} for Traefik env var expansion"
        )

    def test_compose_traefik_service_passes_acme_email(self):
        dc = _yaml(self.COMPOSE)
        env_block = dc["services"]["traefik"].get("environment", [])
        # environment can be list (- KEY=VAL) or dict (KEY: VAL)
        if isinstance(env_block, list):
            env_keys = [entry.split("=")[0] for entry in env_block if isinstance(entry, str)]
        else:
            env_keys = list((env_block or {}).keys())
        assert "TRAEFIK_ACME_EMAIL" in env_keys, (
            "docker-compose.production.yml traefik service must set TRAEFIK_ACME_EMAIL env var"
        )

    def test_env_template_has_acme_email_placeholder(self):
        text = _read(self.ENV_TEMPLATE)
        assert "TRAEFIK_ACME_EMAIL=" in text, (
            ".env.production.template must contain a TRAEFIK_ACME_EMAIL= placeholder"
        )

    def test_env_template_acme_email_is_not_example_com(self):
        text = _read(self.ENV_TEMPLATE)
        # Find the TRAEFIK_ACME_EMAIL line
        for line in text.splitlines():
            if line.startswith("TRAEFIK_ACME_EMAIL="):
                value = line.split("=", 1)[1].strip()
                assert "hub.example.com" not in value, (
                    f"TRAEFIK_ACME_EMAIL must not use hub.example.com placeholder: {value!r}"
                )
                break


# ===========================================================================
# Review gap fixes — 20.1 caller wiring + stale comment
# ===========================================================================

class TestReviewGapFixes:
    STAGING_MAIN = "infrastructure/terraform/environments/staging/main.tf"
    PROD_MAIN = "infrastructure/terraform/environments/prod/main.tf"
    STAGING_VARS = "infrastructure/terraform/environments/staging/variables.tf"
    PROD_VARS = "infrastructure/terraform/environments/prod/variables.tf"
    TF_WORKFLOW = ".github/workflows/terraform.yml"
    DEPLOY_YML = ".github/workflows/deploy.yml"

    # ---- Gap 1 & 2: module caller wiring ----

    def test_staging_main_passes_ses_sender_identity(self):
        text = _read(self.STAGING_MAIN)
        assert "ses_sender_identity" in text, (
            "environments/staging/main.tf must pass ses_sender_identity to module.iam_irsa"
        )

    def test_prod_main_passes_ses_sender_identity(self):
        text = _read(self.PROD_MAIN)
        assert "ses_sender_identity" in text, (
            "environments/prod/main.tf must pass ses_sender_identity to module.iam_irsa"
        )

    def test_staging_main_ses_identity_assignment(self):
        """The assignment must forward the variable value (not be a literal)."""
        text = _read(self.STAGING_MAIN)
        assert "ses_sender_identity = var.ses_sender_identity" in text, (
            "environments/staging/main.tf must assign ses_sender_identity = var.ses_sender_identity"
        )

    def test_prod_main_ses_identity_assignment(self):
        text = _read(self.PROD_MAIN)
        assert "ses_sender_identity = var.ses_sender_identity" in text, (
            "environments/prod/main.tf must assign ses_sender_identity = var.ses_sender_identity"
        )

    def test_staging_variables_declares_ses_sender_identity(self):
        text = _read(self.STAGING_VARS)
        assert 'variable "ses_sender_identity"' in text, (
            "environments/staging/variables.tf must declare ses_sender_identity variable"
        )

    def test_prod_variables_declares_ses_sender_identity(self):
        text = _read(self.PROD_VARS)
        assert 'variable "ses_sender_identity"' in text, (
            "environments/prod/variables.tf must declare ses_sender_identity variable"
        )

    # ---- Gap 3: terraform.yml CI passes the variable ----

    def test_terraform_workflow_staging_plan_uses_ses_secret(self):
        text = _read(self.TF_WORKFLOW)
        assert "TF_STAGING_SES_SENDER_IDENTITY" in text, (
            "terraform.yml staging plan step must pass TF_STAGING_SES_SENDER_IDENTITY secret"
        )

    def test_terraform_workflow_prod_plan_uses_ses_secret(self):
        text = _read(self.TF_WORKFLOW)
        assert "TF_PROD_SES_SENDER_IDENTITY" in text, (
            "terraform.yml prod plan step must pass TF_PROD_SES_SENDER_IDENTITY secret"
        )

    def test_terraform_workflow_staging_passes_var_flag(self):
        """The secret must be passed as a -var flag, not just referenced."""
        text = _read(self.TF_WORKFLOW)
        assert 'ses_sender_identity=${{ secrets.TF_STAGING_SES_SENDER_IDENTITY }}' in text, (
            "terraform.yml staging plan must include "
            "-var=\"ses_sender_identity=${{ secrets.TF_STAGING_SES_SENDER_IDENTITY }}\""
        )

    def test_terraform_workflow_prod_passes_var_flag(self):
        text = _read(self.TF_WORKFLOW)
        assert 'ses_sender_identity=${{ secrets.TF_PROD_SES_SENDER_IDENTITY }}' in text, (
            "terraform.yml prod plan must include "
            "-var=\"ses_sender_identity=${{ secrets.TF_PROD_SES_SENDER_IDENTITY }}\""
        )

    # ---- Gap 4: stale force_deploy comment in deploy.yml job header ----

    def test_job5_header_does_not_reference_force_deploy_bypass(self):
        text = _read(self.DEPLOY_YML)
        assert (
            "set force_deploy=true input to downgrade exit-code to 0" not in text
        ), (
            "Job 5 comment header must not retain the old force_deploy bypass instruction"
        )
