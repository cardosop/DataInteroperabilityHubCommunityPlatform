#!/usr/bin/env python3
"""
Comprehensive API Effort Estimation

Estimates effort for all APIs in the development backlog considering:
- Complexity (simple CRUD vs complex business logic)
- Dependencies (database changes, external services, infrastructure)
- Integration requirements
- Testing requirements
- Documentation requirements
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent


class ComplexityLevel(Enum):
    """API complexity levels."""

    SIMPLE = "simple"  # Basic CRUD, 2-4 hours
    MEDIUM = "medium"  # CRUD with validation, 4-8 hours
    COMPLEX = "complex"  # Business logic, 1-2 days
    VERY_COMPLEX = "very_complex"  # Multi-service integration, 2-5 days


class GapType(Enum):
    """Gap types."""

    MISSING = "missing"
    INCOMPLETE = "incomplete"
    ENHANCEMENT = "enhancement"


@dataclass
class EffortEstimate:
    """Effort estimate for an API."""

    # Base effort (hours)
    base_effort: float = 0.0
    complexity_multiplier: float = 1.0

    # Dependency effort (hours)
    database_effort: float = 0.0
    external_service_effort: float = 0.0
    infrastructure_effort: float = 0.0

    # Integration effort (hours)
    service_integration_effort: float = 0.0
    workflow_integration_effort: float = 0.0

    # Testing effort (hours)
    unit_test_effort: float = 0.0
    integration_test_effort: float = 0.0
    e2e_test_effort: float = 0.0

    # Documentation effort (hours)
    api_doc_effort: float = 0.0
    code_doc_effort: float = 0.0

    def calculate_total(self) -> tuple[float, float]:
        """Calculate total effort in hours and days."""
        development = (
            self.base_effort * self.complexity_multiplier
            + self.database_effort
            + self.external_service_effort
            + self.infrastructure_effort
            + self.service_integration_effort
            + self.workflow_integration_effort
        )

        testing = self.unit_test_effort + self.integration_test_effort + self.e2e_test_effort

        documentation = self.api_doc_effort + self.code_doc_effort

        total_hours = development + testing + documentation
        total_days = total_hours / 8.0

        return total_hours, total_days, development, testing, documentation


class APIEffortEstimator:
    """Estimates effort for API development tasks."""

    # Base effort by gap type (hours)
    BASE_EFFORT = {
        GapType.MISSING: {
            ComplexityLevel.SIMPLE: 3.0,
            ComplexityLevel.MEDIUM: 6.0,
            ComplexityLevel.COMPLEX: 12.0,
            ComplexityLevel.VERY_COMPLEX: 24.0,
        },
        GapType.INCOMPLETE: {
            ComplexityLevel.SIMPLE: 1.5,
            ComplexityLevel.MEDIUM: 3.0,
            ComplexityLevel.COMPLEX: 6.0,
            ComplexityLevel.VERY_COMPLEX: 12.0,
        },
        GapType.ENHANCEMENT: {
            ComplexityLevel.SIMPLE: 1.5,
            ComplexityLevel.MEDIUM: 3.0,
            ComplexityLevel.COMPLEX: 6.0,
            ComplexityLevel.VERY_COMPLEX: 12.0,
        },
    }

    COMPLEXITY_MULTIPLIERS = {
        ComplexityLevel.SIMPLE: 1.0,
        ComplexityLevel.MEDIUM: 1.5,
        ComplexityLevel.COMPLEX: 2.0,
        ComplexityLevel.VERY_COMPLEX: 3.0,
    }

    # Dependency effort (hours)
    DATABASE_EFFORT = {"none": 0.0, "simple": 2.0, "medium": 4.0, "complex": 8.0}
    EXTERNAL_SERVICE_EFFORT = {"none": 0.0, "simple": 4.0, "medium": 8.0, "complex": 16.0}
    INFRASTRUCTURE_EFFORT = {"none": 0.0, "simple": 2.0, "medium": 4.0, "complex": 8.0}
    SERVICE_INTEGRATION_EFFORT = {"none": 0.0, "single": 2.0, "multiple": 4.0, "complex": 8.0}
    WORKFLOW_INTEGRATION_EFFORT = {"none": 0.0, "simple": 4.0, "complex": 8.0}

    # Testing effort (hours)
    UNIT_TEST_EFFORT = {
        ComplexityLevel.SIMPLE: 1.0,
        ComplexityLevel.MEDIUM: 2.0,
        ComplexityLevel.COMPLEX: 4.0,
        ComplexityLevel.VERY_COMPLEX: 8.0,
    }
    INTEGRATION_TEST_EFFORT = {
        ComplexityLevel.SIMPLE: 1.0,
        ComplexityLevel.MEDIUM: 2.0,
        ComplexityLevel.COMPLEX: 4.0,
        ComplexityLevel.VERY_COMPLEX: 8.0,
    }
    E2E_TEST_EFFORT = {
        ComplexityLevel.SIMPLE: 0.5,
        ComplexityLevel.MEDIUM: 1.0,
        ComplexityLevel.COMPLEX: 2.0,
        ComplexityLevel.VERY_COMPLEX: 4.0,
    }

    # Documentation effort (hours)
    API_DOC_EFFORT = 0.5  # OpenAPI spec exists
    CODE_DOC_EFFORT = {
        ComplexityLevel.SIMPLE: 0.5,
        ComplexityLevel.MEDIUM: 0.5,
        ComplexityLevel.COMPLEX: 1.0,
        ComplexityLevel.VERY_COMPLEX: 2.0,
    }

    def estimate(
        self,
        gap_type: GapType,
        complexity: ComplexityLevel,
        database: str = "none",
        external_service: str = "none",
        infrastructure: str = "none",
        service_integration: str = "none",
        workflow_integration: str = "none",
        has_ai_ml: bool = False,
    ) -> EffortEstimate:
        """Estimate effort for an API."""
        est = EffortEstimate()

        est.base_effort = self.BASE_EFFORT[gap_type][complexity]
        est.complexity_multiplier = self.COMPLEXITY_MULTIPLIERS[complexity]

        if has_ai_ml:
            est.complexity_multiplier *= 1.5

        est.database_effort = self.DATABASE_EFFORT.get(database, 0.0)
        est.external_service_effort = self.EXTERNAL_SERVICE_EFFORT.get(external_service, 0.0)
        est.infrastructure_effort = self.INFRASTRUCTURE_EFFORT.get(infrastructure, 0.0)
        est.service_integration_effort = self.SERVICE_INTEGRATION_EFFORT.get(
            service_integration, 0.0
        )
        est.workflow_integration_effort = self.WORKFLOW_INTEGRATION_EFFORT.get(
            workflow_integration, 0.0
        )

        est.unit_test_effort = self.UNIT_TEST_EFFORT[complexity]
        est.integration_test_effort = self.INTEGRATION_TEST_EFFORT[complexity]
        est.e2e_test_effort = self.E2E_TEST_EFFORT[complexity]

        est.api_doc_effort = self.API_DOC_EFFORT
        est.code_doc_effort = self.CODE_DOC_EFFORT[complexity]

        return est


def determine_complexity(
    gap_type: GapType,
    category: str,
    description: str,
    has_workflow: bool,
    has_ai_ml: bool,
    integration_count: int,
) -> ComplexityLevel:
    """Determine complexity based on API characteristics."""
    desc_lower = description.lower()

    # Very complex indicators
    if (
        has_ai_ml
        or has_workflow
        or integration_count > 2
        or ("workflow" in desc_lower and "orchestration" in desc_lower)
        or "multi-service" in desc_lower
    ):
        return ComplexityLevel.VERY_COMPLEX

    # Complex indicators
    if (
        has_workflow
        or integration_count > 0
        or ("validation" in desc_lower and "service" in desc_lower)
        or "integration" in desc_lower
        or "orchestration" in desc_lower
        or category in ["AI/ML", "Credential Management"]
    ):
        return ComplexityLevel.COMPLEX

    # Medium indicators
    if (
        gap_type == GapType.MISSING
        or "filtering" in desc_lower
        or "search" in desc_lower
        or "validation" in desc_lower
    ):
        return ComplexityLevel.MEDIUM

    # Simple
    return ComplexityLevel.SIMPLE


def estimate_all_apis() -> dict[str, dict[str, Any]]:
    """Estimate effort for all APIs in the backlog."""
    estimator = APIEffortEstimator()
    estimates = {}

    # Define API characteristics - comprehensive mapping
    api_configs = {
        # P0 - Missing Endpoints
        "POST /api/v1/auth/register/": {
            "gap_type": GapType.MISSING,
            "category": "Authentication",
            "description": "Register new user account with email, password, and name",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "simple",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "GET /api/v1/auth/me/": {
            "gap_type": GapType.MISSING,
            "category": "Authentication",
            "description": "Get current authenticated user information",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        # P0 - Incomplete Endpoints
        "GET /api/v1/assets/": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Asset Management",
            "description": "List assets with filtering, sorting, and search",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "POST /api/v1/assets/{id}/activate/": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Asset Management",
            "description": "Activate asset with validation and workflow execution",
            "has_workflow": True,
            "has_ai_ml": False,
            "integration_count": 3,  # Contract, DQ, Compliance
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "multiple",
            "workflow_integration": "complex",
        },
        "GET /api/v1/auth/api-keys/": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Authentication",
            "description": "List API keys with pagination support",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "POST /api/v1/contracts/{id}/validate/": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Contract Management",
            "description": "Validate contract with detailed results",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 1,  # Validation service
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "single",
            "workflow_integration": "none",
        },
        # P0 - Enhancements
        "POST /api/v1/assets/ (enhancement)": {
            "gap_type": GapType.ENHANCEMENT,
            "category": "Asset Management",
            "description": "Create asset with performance optimization",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "simple",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "POST /api/v1/assets/{id}/activate/ (enhancement)": {
            "gap_type": GapType.ENHANCEMENT,
            "category": "Asset Management",
            "description": "Activate asset with performance optimization",
            "has_workflow": True,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "simple",
            "service_integration": "none",
            "workflow_integration": "simple",
        },
        # P1 - Incomplete Endpoints
        "GET /api/v1/marketplace/listings/": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Marketplace",
            "description": "List marketplace listings with search, filtering, and sorting",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "GET /api/v1/search/search/": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Search",
            "description": "Execute search with advanced filtering, faceting, and highlighting",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "GET /api/v1/scheduled-ingestions/{id}/credentials/": {
            "gap_type": GapType.MISSING,
            "category": "Credential Management",
            "description": "Get credentials for scheduled ingestion (masked)",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "POST /api/v1/scheduled-ingestions/{id}/credentials/test/": {
            "gap_type": GapType.MISSING,
            "category": "Credential Management",
            "description": "Test connection with stored credentials",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 1,  # Connector service
            "database": "none",
            "external_service": "medium",
            "infrastructure": "none",
            "service_integration": "single",
            "workflow_integration": "none",
        },
        "GET /api/v1/compliance/compliance-runs/{id}/results/": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Compliance",
            "description": "Get compliance run results with detailed violation information",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "GET /api/v1/dq/dq-runs/": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Data Quality",
            "description": "List DQ runs with filtering capabilities",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "GET /api/v1/dq/dq-runs/{id}/results/": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Data Quality",
            "description": "Get DQ run results with detailed check information",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        # P1 - Enhancements
        "GET /api/v1/marketplace/listings/ (enhancement)": {
            "gap_type": GapType.ENHANCEMENT,
            "category": "Marketplace",
            "description": "Enhance marketplace listings endpoint with performance optimization",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "simple",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "GET /api/v1/search/search/ (enhancement)": {
            "gap_type": GapType.ENHANCEMENT,
            "category": "Search",
            "description": "Enhance search endpoint with performance optimization",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "simple",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "GET /api/v1/dq/dq-runs/{id}/results/ (enhancement)": {
            "gap_type": GapType.ENHANCEMENT,
            "category": "Data Quality",
            "description": "Enhance DQ results endpoint with performance optimization",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "simple",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        # P2 - Missing Endpoints
        "POST /api/v1/ai/natural-language-search/": {
            "gap_type": GapType.MISSING,
            "category": "AI/ML",
            "description": "Execute natural language search with AI-powered query understanding",
            "has_workflow": False,
            "has_ai_ml": True,
            "integration_count": 1,  # LLM service
            "database": "none",
            "external_service": "complex",
            "infrastructure": "simple",
            "service_integration": "single",
            "workflow_integration": "none",
        },
        "POST /api/v1/ai/schema-matching/": {
            "gap_type": GapType.MISSING,
            "category": "AI/ML",
            "description": "Generate AI-powered schema matching suggestions",
            "has_workflow": False,
            "has_ai_ml": True,
            "integration_count": 1,  # AI service
            "database": "none",
            "external_service": "complex",
            "infrastructure": "simple",
            "service_integration": "single",
            "workflow_integration": "none",
        },
        "POST /api/v1/social/ratings/": {
            "gap_type": GapType.MISSING,
            "category": "Social Features",
            "description": "Submit rating for a data asset",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "simple",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "POST /api/v1/social/reviews/": {
            "gap_type": GapType.MISSING,
            "category": "Social Features",
            "description": "Submit written review for a data asset",
            "has_workflow": True,  # Moderation workflow
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "simple",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "simple",
        },
        "POST /api/v1/social/comments/": {
            "gap_type": GapType.MISSING,
            "category": "Social Features",
            "description": "Submit comment on a data asset (supports threading)",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "simple",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "POST /api/v1/social/communities/": {
            "gap_type": GapType.MISSING,
            "category": "Social Features",
            "description": "Create or join a data community",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "medium",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        # P2 - Incomplete Endpoints
        "POST /api/v1/ai/natural-language-search/ (incomplete)": {
            "gap_type": GapType.INCOMPLETE,
            "category": "AI/ML",
            "description": "Natural language search with advanced features",
            "has_workflow": False,
            "has_ai_ml": True,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "POST /api/v1/ai/schema-matching/ (incomplete)": {
            "gap_type": GapType.INCOMPLETE,
            "category": "AI/ML",
            "description": "Schema matching with advanced features",
            "has_workflow": False,
            "has_ai_ml": True,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "POST /api/v1/social/ratings/ (incomplete)": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Social Features",
            "description": "Ratings with advanced features",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "POST /api/v1/social/reviews/ (incomplete)": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Social Features",
            "description": "Reviews with advanced features",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        # P2 - Enhancements
        "GET /api/v1/datasets/ (enhancement)": {
            "gap_type": GapType.ENHANCEMENT,
            "category": "Dataset Management",
            "description": "Enhance dataset listing with versioning support",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "GET /api/v1/scheduled-ingestions/ (enhancement)": {
            "gap_type": GapType.ENHANCEMENT,
            "category": "Scheduled Ingestion",
            "description": "Enhance scheduled ingestion listing with credential management indicators",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        # P3 - Missing Endpoints
        "GET /api/v1/marketplace/listings/{id}/preview/": {
            "gap_type": GapType.MISSING,
            "category": "Advanced Marketplace",
            "description": "Get data preview before purchase",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 1,  # DQ service
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "single",
            "workflow_integration": "none",
        },
        "GET /api/v1/developer/plugins/": {
            "gap_type": GapType.MISSING,
            "category": "Developer Experience",
            "description": "List available plugins",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "GET /api/v1/developer/sdk/": {
            "gap_type": GapType.MISSING,
            "category": "Developer Experience",
            "description": "Get SDK documentation and examples",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        # P3 - Incomplete Endpoints
        "GET /api/v1/marketplace/listings/ (incomplete)": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Marketplace",
            "description": "Marketplace listings with advanced features",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        "GET /api/v1/developer/plugins/ (incomplete)": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Developer Experience",
            "description": "Plugins listing with advanced features",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "none",
            "service_integration": "none",
            "workflow_integration": "none",
        },
        # P3 - Enhancements
        "GET /api/v1/marketplace/listings/{id}/preview/ (enhancement)": {
            "gap_type": GapType.ENHANCEMENT,
            "category": "Advanced Marketplace",
            "description": "Enhance preview endpoint with performance optimization",
            "has_workflow": False,
            "has_ai_ml": False,
            "integration_count": 0,
            "database": "none",
            "external_service": "none",
            "infrastructure": "simple",
            "service_integration": "none",
            "workflow_integration": "none",
        },
    }

    # Estimate for each API
    for endpoint, config in api_configs.items():
        complexity = determine_complexity(
            gap_type=config["gap_type"],
            category=config["category"],
            description=config["description"],
            has_workflow=config["has_workflow"],
            has_ai_ml=config["has_ai_ml"],
            integration_count=config["integration_count"],
        )

        estimate = estimator.estimate(
            gap_type=config["gap_type"],
            complexity=complexity,
            database=config["database"],
            external_service=config["external_service"],
            infrastructure=config["infrastructure"],
            service_integration=config["service_integration"],
            workflow_integration=config["workflow_integration"],
            has_ai_ml=config["has_ai_ml"],
        )

        total_hours, total_days, dev, test, doc = estimate.calculate_total()

        estimates[endpoint] = {
            "complexity": complexity.value,
            "gap_type": config["gap_type"].value,
            "category": config["category"],
            "total_hours": round(total_hours, 1),
            "total_days": round(total_days, 1),
            "development_hours": round(dev, 1),
            "testing_hours": round(test, 1),
            "documentation_hours": round(doc, 1),
            "breakdown": {
                "base_effort": round(estimate.base_effort * estimate.complexity_multiplier, 1),
                "database": round(estimate.database_effort, 1),
                "external_service": round(estimate.external_service_effort, 1),
                "infrastructure": round(estimate.infrastructure_effort, 1),
                "service_integration": round(estimate.service_integration_effort, 1),
                "workflow_integration": round(estimate.workflow_integration_effort, 1),
                "unit_tests": round(estimate.unit_test_effort, 1),
                "integration_tests": round(estimate.integration_test_effort, 1),
                "e2e_tests": round(estimate.e2e_test_effort, 1),
            },
        }

    return estimates


def main():
    """Main entry point."""
    print("=" * 80)
    print("Comprehensive API Effort Estimation")
    print("=" * 80)

    estimates = estimate_all_apis()

    # Calculate totals
    total_hours = sum(e["total_hours"] for e in estimates.values())
    total_days = sum(e["total_days"] for e in estimates.values())
    total_dev = sum(e["development_hours"] for e in estimates.values())
    total_test = sum(e["testing_hours"] for e in estimates.values())
    total_doc = sum(e["documentation_hours"] for e in estimates.values())

    print("\nTotal Estimated Effort:")
    print(f"  Hours: {total_hours:.1f}")
    print(f"  Days: {total_days:.1f} ({total_days / 5:.1f} weeks)")
    print(f"  Development: {total_dev:.1f}h ({total_dev / 8:.1f} days)")
    print(f"  Testing: {total_test:.1f}h ({total_test / 8:.1f} days)")
    print(f"  Documentation: {total_doc:.1f}h ({total_doc / 8:.1f} days)")

    # Group by priority (simplified)
    print("\nEffort by Complexity:")
    for complexity in ["simple", "medium", "complex", "very_complex"]:
        comp_apis = [e for e in estimates.values() if e["complexity"] == complexity]
        if comp_apis:
            comp_hours = sum(e["total_hours"] for e in comp_apis)
            print(
                f"  {complexity}: {len(comp_apis)} APIs, {comp_hours:.1f}h ({comp_hours / 8:.1f} days)"
            )

    print("\nEffort by Gap Type:")
    for gap_type in ["missing", "incomplete", "enhancement"]:
        type_apis = [e for e in estimates.values() if e["gap_type"] == gap_type]
        if type_apis:
            type_hours = sum(e["total_hours"] for e in type_apis)
            print(
                f"  {gap_type}: {len(type_apis)} APIs, {type_hours:.1f}h ({type_hours / 8:.1f} days)"
            )

    # Save to JSON for use in backlog update
    import json

    output_file = PROJECT_ROOT / "docs" / "api-audit" / "api-effort-estimates.json"
    with open(output_file, "w") as f:
        json.dump(estimates, f, indent=2)
    print(f"\n✅ Estimates saved to: {output_file.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
