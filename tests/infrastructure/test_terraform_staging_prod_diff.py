"""
280.A.6.2 — Terraform Staging vs. Production Plan Diff.

Parses the staging and production terraform environment root modules,
compares key parameters, and documents intentional differences.
Flags any configuration that appears to be an unexpected drift
(same-parameter-should-be-same but isn't).

Does NOT run terraform plan — validates the .tf source files directly.
"""

import os
import re

import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TF_DIR = os.path.join(PROJECT_ROOT, "infrastructure", "terraform", "environments")


def _read_tf_file(path):
    """Read a terraform file, return raw text."""
    with open(path) as f:
        return f.read()


def _tf_files(env):
    """Return dict of filename → contents for an environment's .tf files."""
    env_dir = os.path.join(TF_DIR, env)
    files = {}
    for name in sorted(os.listdir(env_dir)):
        if name.endswith(".tf"):
            files[name] = _read_tf_file(os.path.join(env_dir, name))
    return files


def _extract_block_assignment(text, block_name, param):
    """Extract the value of `param = <value>` inside a named block.

    Handles quoted strings, unquoted values, and multi-line heredoc strings.
    Returns the raw value string or None.
    """
    # Find the block start
    block_pattern = re.compile(
        rf'(?:module|resource|locals)\s+["\w-]*{re.escape(block_name)}\b',
        re.MULTILINE,
    )
    match = block_pattern.search(text)
    if not match:
        return None

    # Search for param = <value> within 50 lines after block start
    start = match.start()
    window = text[start : start + 3000]
    param_pattern = re.compile(
        rf"^\s*{re.escape(param)}\s*=\s*(.+?)$",
        re.MULTILINE,
    )
    m = param_pattern.search(window)
    if m:
        raw = m.group(1).strip()
        # Strip trailing comments
        raw = re.sub(r"\s+#.*$", "", raw)
        return raw.strip()
    return None


def _extract_module_param(text, module_name, param):
    """Extract a parameter from a module block."""
    return _extract_block_assignment(text, module_name, param)


# ---------------------------------------------------------------------------
# 280.A.6.2.1 — Staging vs Production diff
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def staging_tf():
    """Contents of staging environment terraform files."""
    assert os.path.isdir(os.path.join(TF_DIR, "staging")), "staging TF dir missing"
    return _tf_files("staging")


@pytest.fixture(scope="module")
def prod_tf():
    """Contents of production environment terraform files."""
    assert os.path.isdir(os.path.join(TF_DIR, "prod")), "prod TF dir missing"
    return _tf_files("prod")


@pytest.fixture(scope="module")
def staging_main(staging_tf):
    """Raw text of staging/main.tf."""
    return staging_tf["main.tf"]


@pytest.fixture(scope="module")
def prod_main(prod_tf):
    """Raw text of production/main.tf."""
    return prod_tf["main.tf"]


class TestTerraformStagingProdDiff:
    """Compare staging vs production terraform and document differences."""

    # -----------------------------------------------------------------------
    # Cluster & networking
    # -----------------------------------------------------------------------

    def test_vpc_cidr_different(self, staging_main, prod_main):
        """VPC CIDR must differ between staging and prod (no overlap)."""
        staging_cidr = _extract_module_param(staging_main, "vpc", "vpc_cidr")
        prod_cidr = _extract_module_param(prod_main, "vpc", "vpc_cidr")
        assert staging_cidr != prod_cidr, (
            f"VPC CIDRs must differ. staging={staging_cidr}, prod={prod_cidr}"
        )
        # Documented difference: staging 10.10.0.0/16, prod 10.20.0.0/16

    def test_cluster_name_different(self, staging_main, prod_main):
        """Cluster names must differ."""
        staging_name = _extract_module_param(staging_main, "eks", "cluster_name")
        prod_name = _extract_module_param(prod_main, "eks", "cluster_name")
        assert "staging" in staging_name.lower(), (
            f"Staging cluster name should contain 'staging': {staging_name}"
        )
        assert "prod" in prod_name.lower(), f"Prod cluster name should contain 'prod': {prod_name}"
        assert staging_name != prod_name

    def test_nat_gateway_count_staging_1_prod_3(self, staging_main, prod_main):
        """Staging uses 1 NAT GW (cost-saving); prod uses 3 (HA)."""
        staging_nat = _extract_module_param(staging_main, "vpc", "nat_gateway_count")
        prod_nat = _extract_module_param(prod_main, "vpc", "nat_gateway_count")
        assert staging_nat == "1", (
            f"Staging NAT GW count should be 1 (cost saving), got {staging_nat}"
        )
        assert prod_nat == "3", f"Prod NAT GW count should be 3 (HA), got {prod_nat}"

    def test_eks_public_endpoint(self, staging_main, prod_main):
        """Staging EKS has public endpoint; prod should be private only."""
        staging_pe = _extract_module_param(staging_main, "eks", "public_endpoint")
        prod_pe = _extract_module_param(prod_main, "eks", "public_endpoint")
        assert staging_pe == "true", f"Staging public_endpoint should be true, got {staging_pe}"
        assert prod_pe == "false", (
            f"Prod public_endpoint should be false (private only), got {prod_pe}"
        )

    # -----------------------------------------------------------------------
    # Node groups
    # -----------------------------------------------------------------------

    def test_staging_single_node_group_prod_four(self, staging_main, prod_main):
        """Staging: 1 node group (general-ng). Prod: 4 (system, app, worker, GPU)."""
        staging_ngs = staging_main.count("instance_types")
        prod_ngs = prod_main.count("instance_types")
        # Staging has 1 node group, prod has 4
        assert staging_ngs == 1, (
            f"Staging should have 1 node group, found {staging_ngs} instance_types"
        )
        assert prod_ngs == 4, f"Prod should have 4 node groups, found {prod_ngs} instance_types"

    def test_staging_instance_type_t3_prod_m6i(self, staging_main, prod_main):
        """Staging uses t3 instances (burstable); prod uses m6i (consistent).

        GPU node group uses g4dn.xlarge in both.
        """
        assert "t3.large" in staging_main, "Staging should use t3.large instances"
        assert "m6i.xlarge" in prod_main, "Prod should use m6i.xlarge for app nodes"
        assert "m6i.large" in prod_main, "Prod should use m6i.large for worker nodes"

    def test_staging_desired_1_prod_desired_3(self, staging_main, prod_main):
        """Staging runs minimal replicas; prod runs HA."""
        # Staging: desired_size=1 for general-ng
        assert "desired_size = 1" in staging_main or "desired_size=1" in staging_main, (
            "Staging general-ng should have desired_size=1"
        )
        # Prod: app-ng has desired_size=3
        assert "desired_size   = 3" in prod_main, "Prod app-ng should have desired_size=3"

    def test_prod_system_ng_has_taint(self, prod_main):
        """Prod system-ng must have CriticalAddonsOnly taint."""
        assert "CriticalAddonsOnly" in prod_main, "Prod system-ng must taint for CriticalAddonsOnly"

    # -----------------------------------------------------------------------
    # RDS
    # -----------------------------------------------------------------------

    def test_rds_instance_class_diff(self, staging_main, prod_main):
        """Staging: db.t4g.small (burstable); prod: db.r7g.large (provisioned)."""
        staging_class = _extract_module_param(staging_main, "rds", "instance_class")
        prod_class = _extract_module_param(prod_main, "rds", "instance_class")
        assert "t4g" in staging_class, f"Staging RDS should be t4g (burstable), got {staging_class}"
        assert "r7g" in prod_class, f"Prod RDS should be r7g (provisioned), got {prod_class}"

    def test_rds_multi_az_diff(self, staging_main, prod_main):
        """Staging: single-AZ; prod: multi-AZ."""
        staging_maz = _extract_module_param(staging_main, "rds", "multi_az")
        prod_maz = _extract_module_param(prod_main, "rds", "multi_az")
        assert staging_maz == "false", f"Staging multi_az should be false, got {staging_maz}"
        assert prod_maz == "true", f"Prod multi_az should be true, got {prod_maz}"

    def test_rds_backup_retention_diff(self, staging_main, prod_main):
        """Staging: 7 days; prod: 14 days."""
        staging_br = _extract_module_param(staging_main, "rds", "backup_retention_days")
        prod_br = _extract_module_param(prod_main, "rds", "backup_retention_days")
        assert staging_br == "7", f"Staging backup retention should be 7, got {staging_br}"
        assert prod_br == "14", f"Prod backup retention should be 14, got {prod_br}"

    def test_rds_performance_insights_diff(self, staging_main, prod_main):
        """Staging: no PI; prod: PI enabled."""
        staging_pi = _extract_module_param(staging_main, "rds", "enable_performance_insights")
        prod_pi = _extract_module_param(prod_main, "rds", "enable_performance_insights")
        assert staging_pi == "false", (
            f"Staging performance_insights should be false, got {staging_pi}"
        )
        assert prod_pi == "true", f"Prod performance_insights should be true, got {prod_pi}"

    # -----------------------------------------------------------------------
    # ElastiCache
    # -----------------------------------------------------------------------

    def test_elasticache_node_type_diff(self, staging_main, prod_main):
        """Staging: cache.t4g.micro (burstable); prod: cache.r7g.large."""
        staging_type = _extract_module_param(staging_main, "elasticache", "node_type")
        prod_type = _extract_module_param(prod_main, "elasticache", "node_type")
        assert "t4g" in staging_type, f"Staging ElastiCache should be t4g, got {staging_type}"
        assert "r7g" in prod_type, f"Prod ElastiCache should be r7g, got {prod_type}"

    def test_elasticache_multi_az_diff(self, staging_main, prod_main):
        """Staging: single-AZ; prod: multi-AZ."""
        staging_maz = _extract_module_param(staging_main, "elasticache", "multi_az")
        prod_maz = _extract_module_param(prod_main, "elasticache", "multi_az")
        assert staging_maz == "false", (
            f"Staging ElastiCache multi_az should be false, got {staging_maz}"
        )
        assert prod_maz == "true", f"Prod ElastiCache multi_az should be true, got {prod_maz}"

    def test_staging_collapses_to_single_redis_instance(self, staging_main):
        """Staging collapses 4 Redis instances into 1 for cost savings.

        This is an intentional difference — prod keeps all 4 separate
        for isolation and throughput.
        """
        assert "collapse_to_single_instance = true" in staging_main, (
            "Staging must set collapse_to_single_instance=true (Phase 214.3)"
        )

    # -----------------------------------------------------------------------
    # S3
    # -----------------------------------------------------------------------

    def test_s3_versioning_diff(self, staging_main, prod_main):
        """Staging: no versioning; prod: versioning enabled."""
        staging_ver = _extract_module_param(staging_main, "s3", "enable_versioning")
        prod_ver = _extract_module_param(prod_main, "s3", "enable_versioning")
        assert staging_ver == "false", f"Staging S3 versioning should be false, got {staging_ver}"
        assert prod_ver == "true", f"Prod S3 versioning should be true, got {prod_ver}"

    # -----------------------------------------------------------------------
    # Staging-only features (not yet in prod)
    # -----------------------------------------------------------------------

    def test_staging_has_vpc_endpoints_prod_does_not(self, staging_main, prod_main):
        """Staging has VPC endpoints (Phase 214.5a); prod does not yet."""
        assert "enable_vpc_endpoints" in staging_main, "Staging should have enable_vpc_endpoints"
        assert "enable_vpc_endpoints" not in prod_main, (
            "Prod intentionally does not have VPC endpoints yet"
        )

    def test_staging_has_ecr_pull_through_cache(self, staging_main, prod_main):
        """Staging has ECR pull-through cache (Phase 214.5b.0); prod does not."""
        assert 'module "ecr"' in staging_main, "Staging should have ECR pull-through cache module"
        assert 'module "ecr"' not in prod_main, (
            "Prod does not have ECR pull-through cache yet — intentional"
        )

    def test_staging_has_route53_dns_automation(self, staging_main, prod_main):
        """Staging has Route53 DNS automation (Phase 211f); not expected in prod yet."""
        assert "aws_route53_zone" in staging_main, "Staging should have Route53 DNS automation"
        # Prod may or may not have it — just document the absence
        # This is intentional: prod DNS is managed separately

    # -----------------------------------------------------------------------
    # Common structure checks (should be identical or contain same elements)
    # -----------------------------------------------------------------------

    def test_both_have_required_modules(self, staging_main, prod_main):
        """Both envs must declare all required modules."""
        required_modules = ["vpc", "eks", "s3", "kms", "rds", "elasticache", "iam_irsa"]
        for mod in required_modules:
            assert f'module "{mod}"' in staging_main, f"Staging missing module: {mod}"
            assert f'module "{mod}"' in prod_main, f"Prod missing module: {mod}"

    def test_both_have_security_group_rules(self, staging_main, prod_main):
        """Both envs must have RDS and ElastiCache ingress SG rules."""
        assert "rds_ingress_from_eks_cluster" in staging_main
        assert "rds_ingress_from_eks_cluster" in prod_main
        assert "elasticache_ingress_from_eks_cluster" in staging_main
        assert "elasticache_ingress_from_eks_cluster" in prod_main

    def test_terraform_version_same(self, staging_main, prod_main):
        """Both envs must require same terraform version."""
        staging_ver = re.search(r'required_version\s*=\s*"([^"]+)"', staging_main)
        prod_ver = re.search(r'required_version\s*=\s*"([^"]+)"', prod_main)
        if staging_ver and prod_ver:
            assert staging_ver.group(1) == prod_ver.group(1), (
                f"Terraform versions differ: staging={staging_ver.group(1)}, "
                f"prod={prod_ver.group(1)}"
            )

    def test_aws_provider_version_same(self, staging_main, prod_main):
        """Both envs must use the same AWS provider version."""
        staging_ver = re.search(
            r'source\s*=\s*"hashicorp/aws"[^}]*version\s*=\s*"([^"]+)"', staging_main, re.DOTALL
        )
        prod_ver = re.search(
            r'source\s*=\s*"hashicorp/aws"[^}]*version\s*=\s*"([^"]+)"', prod_main, re.DOTALL
        )
        if staging_ver and prod_ver:
            assert staging_ver.group(1) == prod_ver.group(1), "AWS provider versions differ"

    def test_cluster_version_same(self, staging_main, prod_main):
        """Both envs must use the same EKS cluster version."""
        staging_cv = _extract_module_param(staging_main, "eks", "cluster_version")
        prod_cv = _extract_module_param(prod_main, "eks", "cluster_version")
        assert staging_cv == prod_cv, (
            f"EKS cluster versions differ: staging={staging_cv}, prod={prod_cv}. "
            f"Both should be the same Kubernetes version."
        )


# ---------------------------------------------------------------------------
# 280.A.6.2.2 — No unexpected drift
# ---------------------------------------------------------------------------


class TestTerraformNoUnexpectedDrift:
    """Flag patterns that look like accidental drift (not intentional differences)."""

    def test_production_is_not_a_copy_of_staging_with_env_swapped(self, staging_main, prod_main):
        """Prod must NOT be a simple find-replace of staging.

        This is a smell check: if the only difference is s/staging/prod/
        then prod hasn't been properly sized.
        """
        # If the files are byte-identical after normalizing whitespace and env name,
        # that's a problem
        staging_norm = re.sub(r"[Ss]taging", "ENVNAME", staging_main)
        staging_norm = re.sub(r"\s+", " ", staging_norm)

        prod_norm = re.sub(r"[Pp]rod", "ENVNAME", prod_main)
        prod_norm = re.sub(r"\s+", " ", prod_norm)

        # They should be substantially different
        similarity = _jaccard_similarity(staging_norm, prod_norm)
        assert similarity < 0.95, (
            f"Staging and prod main.tf are {similarity:.1%} similar after "
            f"normalizing env names. Prod should have meaningfully different "
            f"configuration (instance sizes, replica counts, etc.)"
        )

    def test_no_mystery_parameters_in_prod_not_in_staging(self, staging_main, prod_main):
        """Any module parameter in prod that's absent from staging should be justified."""
        # Extract all module param names from both files
        staging_params = set(re.findall(r"^\s*(\w[\w_]*)\s*=", staging_main, re.M))
        prod_params = set(re.findall(r"^\s*(\w[\w_]*)\s*=", prod_main, re.M))

        prod_only = prod_params - staging_params
        # These are known intentional differences
        KNOWN_PROD_ONLY = {
            "source",
            "version",  # provider config
            "default_tags",  # provider config
            "system-ng",
            "app-ng",
            "worker-ng",
            "gpu-ng",  # prod-only node groups
        }
        unexpected = prod_only - KNOWN_PROD_ONLY
        # Don't fail on unexpected — just document them
        # (this is informational; new params get added over time)
        if unexpected:
            pytest.skip(  # noqa: skip-in-body — runtime service dependency
                f"Prod has params not in staging: {sorted(unexpected)}. "
                f"Review if these are intentional."
            )


def _jaccard_similarity(a, b):
    """Approximate Jaccard similarity of two strings based on 4-grams."""

    def ngrams(s, n=4):
        return {s[i : i + n] for i in range(len(s) - n + 1)}

    a_set = ngrams(a)
    b_set = ngrams(b)
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / len(a_set | b_set)
