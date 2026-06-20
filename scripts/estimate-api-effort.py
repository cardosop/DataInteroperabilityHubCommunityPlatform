#!/usr/bin/env python3
"""
API Development Effort Estimation

Comprehensive effort estimation for API development tasks considering:
- Complexity (simple CRUD vs complex business logic)
- Dependencies (database changes, external services, infrastructure)
- Integration requirements
- Testing requirements
- Documentation requirements
"""

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


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

    # Complexity multipliers
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

    # Total effort
    total_effort_hours: float = 0.0
    total_effort_days: float = 0.0

    # Effort breakdown
    development_effort: float = 0.0
    testing_effort: float = 0.0
    documentation_effort: float = 0.0

    def calculate_total(self):
        """Calculate total effort."""
        # Development effort
        self.development_effort = (
            self.base_effort * self.complexity_multiplier
            + self.database_effort
            + self.external_service_effort
            + self.infrastructure_effort
            + self.service_integration_effort
            + self.workflow_integration_effort
        )

        # Testing effort
        self.testing_effort = (
            self.unit_test_effort + self.integration_test_effort + self.e2e_test_effort
        )

        # Documentation effort
        self.documentation_effort = self.api_doc_effort + self.code_doc_effort

        # Total effort
        self.total_effort_hours = (
            self.development_effort + self.testing_effort + self.documentation_effort
        )

        # Convert to days (8 hours per day)
        self.total_effort_days = self.total_effort_hours / 8.0


class APIEffortEstimator:
    """Estimates effort for API development tasks."""

    # Base effort by gap type (hours)
    BASE_EFFORT = {
        GapType.MISSING: {
            ComplexityLevel.SIMPLE: 3.0,  # Basic CRUD endpoint
            ComplexityLevel.MEDIUM: 6.0,  # CRUD with validation
            ComplexityLevel.COMPLEX: 12.0,  # Business logic
            ComplexityLevel.VERY_COMPLEX: 24.0,  # Multi-service integration
        },
        GapType.INCOMPLETE: {
            ComplexityLevel.SIMPLE: 1.5,  # Add query params
            ComplexityLevel.MEDIUM: 3.0,  # Add features
            ComplexityLevel.COMPLEX: 6.0,  # Add business logic
            ComplexityLevel.VERY_COMPLEX: 12.0,  # Add integrations
        },
        GapType.ENHANCEMENT: {
            ComplexityLevel.SIMPLE: 1.5,  # Performance optimization
            ComplexityLevel.MEDIUM: 3.0,  # Feature additions
            ComplexityLevel.COMPLEX: 6.0,  # Complex enhancements
            ComplexityLevel.VERY_COMPLEX: 12.0,  # Major enhancements
        },
    }

    # Complexity multipliers
    COMPLEXITY_MULTIPLIERS = {
        ComplexityLevel.SIMPLE: 1.0,
        ComplexityLevel.MEDIUM: 1.5,
        ComplexityLevel.COMPLEX: 2.0,
        ComplexityLevel.VERY_COMPLEX: 3.0,
    }

    # Dependency effort (hours)
    DATABASE_EFFORT = {
        "none": 0.0,
        "simple": 2.0,  # Add field, simple migration
        "medium": 4.0,  # Add model, relationships
        "complex": 8.0,  # Complex schema changes, data migration
    }

    EXTERNAL_SERVICE_EFFORT = {
        "none": 0.0,
        "simple": 4.0,  # Simple API integration
        "medium": 8.0,  # Complex API integration, auth
        "complex": 16.0,  # Multiple services, error handling
    }

    INFRASTRUCTURE_EFFORT = {
        "none": 0.0,
        "simple": 2.0,  # Configuration changes
        "medium": 4.0,  # New service setup
        "complex": 8.0,  # Infrastructure changes
    }

    # Integration effort (hours)
    SERVICE_INTEGRATION_EFFORT = {
        "none": 0.0,
        "single": 2.0,  # Single service integration
        "multiple": 4.0,  # Multiple services
        "complex": 8.0,  # Complex orchestration
    }

    WORKFLOW_INTEGRATION_EFFORT = {
        "none": 0.0,
        "simple": 4.0,  # Simple workflow
        "complex": 8.0,  # Complex workflow with compensation
    }

    # Testing effort (hours) - typically 30-40% of development effort
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
    API_DOC_EFFORT = 0.5  # OpenAPI spec already exists, just review/update
    CODE_DOC_EFFORT = {
        ComplexityLevel.SIMPLE: 0.5,
        ComplexityLevel.MEDIUM: 0.5,
        ComplexityLevel.COMPLEX: 1.0,
        ComplexityLevel.VERY_COMPLEX: 2.0,
    }

    def estimate_effort(
        self,
        gap_type: GapType,
        complexity: ComplexityLevel,
        dependencies: dict[str, str],
        integrations: dict[str, str],
        has_ai_ml: bool = False,
        has_workflow: bool = False,
        has_external_service: bool = False,
    ) -> EffortEstimate:
        """Estimate effort for an API."""
        estimate = EffortEstimate()

        # Base effort
        estimate.base_effort = self.BASE_EFFORT[gap_type][complexity]
        estimate.complexity_multiplier = self.COMPLEXITY_MULTIPLIERS[complexity]

        # Database effort
        db_complexity = dependencies.get("database", "none")
        estimate.database_effort = self.DATABASE_EFFORT.get(db_complexity, 0.0)

        # External service effort
        if has_external_service:
            ext_complexity = dependencies.get("external_service", "medium")
            estimate.external_service_effort = self.EXTERNAL_SERVICE_EFFORT.get(ext_complexity, 0.0)

        # Infrastructure effort
        infra_complexity = dependencies.get("infrastructure", "none")
        estimate.infrastructure_effort = self.INFRASTRUCTURE_EFFORT.get(infra_complexity, 0.0)

        # Service integration effort
        if integrations.get("services"):
            svc_complexity = integrations.get("services", "single")
            estimate.service_integration_effort = self.SERVICE_INTEGRATION_EFFORT.get(
                svc_complexity, 0.0
            )

        # Workflow integration effort
        if has_workflow:
            wf_complexity = integrations.get("workflow", "simple")
            estimate.workflow_integration_effort = self.WORKFLOW_INTEGRATION_EFFORT.get(
                wf_complexity, 0.0
            )

        # AI/ML multiplier
        if has_ai_ml:
            estimate.complexity_multiplier *= 1.5

        # Testing effort
        estimate.unit_test_effort = self.UNIT_TEST_EFFORT[complexity]
        estimate.integration_test_effort = self.INTEGRATION_TEST_EFFORT[complexity]
        estimate.e2e_test_effort = self.E2E_TEST_EFFORT[complexity]

        # Documentation effort
        estimate.api_doc_effort = self.API_DOC_EFFORT  # OpenAPI spec exists
        estimate.code_doc_effort = self.CODE_DOC_EFFORT[complexity]

        # Calculate total
        estimate.calculate_total()

        return estimate

    def determine_complexity(
        self,
        gap_type: GapType,
        category: str,
        has_business_logic: bool,
        has_workflow: bool,
        has_ai_ml: bool,
        has_external_service: bool,
        integration_count: int,
    ) -> ComplexityLevel:
        """Determine complexity level based on API characteristics."""
        if has_ai_ml or has_workflow or integration_count > 2:
            return ComplexityLevel.VERY_COMPLEX
        elif has_business_logic or has_external_service or integration_count > 0:
            return ComplexityLevel.COMPLEX
        elif gap_type == GapType.MISSING:
            return ComplexityLevel.MEDIUM
        else:
            return ComplexityLevel.SIMPLE

    def format_effort(self, estimate: EffortEstimate) -> dict[str, Any]:
        """Format effort estimate for documentation."""
        return {
            "total_hours": round(estimate.total_effort_hours, 1),
            "total_days": round(estimate.total_effort_days, 1),
            "breakdown": {
                "development": {
                    "hours": round(estimate.development_effort, 1),
                    "days": round(estimate.development_effort / 8.0, 1),
                    "components": {
                        "base_effort": round(
                            estimate.base_effort * estimate.complexity_multiplier, 1
                        ),
                        "database": round(estimate.database_effort, 1),
                        "external_service": round(estimate.external_service_effort, 1),
                        "infrastructure": round(estimate.infrastructure_effort, 1),
                        "service_integration": round(estimate.service_integration_effort, 1),
                        "workflow_integration": round(estimate.workflow_integration_effort, 1),
                    },
                },
                "testing": {
                    "hours": round(estimate.testing_effort, 1),
                    "days": round(estimate.testing_effort / 8.0, 1),
                    "components": {
                        "unit_tests": round(estimate.unit_test_effort, 1),
                        "integration_tests": round(estimate.integration_test_effort, 1),
                        "e2e_tests": round(estimate.e2e_test_effort, 1),
                    },
                },
                "documentation": {
                    "hours": round(estimate.documentation_effort, 1),
                    "days": round(estimate.documentation_effort / 8.0, 1),
                    "components": {
                        "api_documentation": round(estimate.api_doc_effort, 1),
                        "code_documentation": round(estimate.code_doc_effort, 1),
                    },
                },
            },
        }


def estimate_api_efforts() -> dict[str, Any]:
    """Estimate efforts for all APIs in the backlog."""
    estimator = APIEffortEstimator()
    estimates = {}

    # Define API characteristics for each endpoint
    api_characteristics = {
        # P0 - Missing Endpoints
        "POST /api/v1/auth/register/": {
            "gap_type": GapType.MISSING,
            "category": "Authentication",
            "has_business_logic": True,
            "has_workflow": False,
            "has_ai_ml": False,
            "has_external_service": False,  # Email service optional
            "integration_count": 0,
            "dependencies": {
                "database": "simple",
                "external_service": "none",
                "infrastructure": "none",
            },
            "integrations": {"services": "none", "workflow": "none"},
        },
        "GET /api/v1/auth/me/": {
            "gap_type": GapType.MISSING,
            "category": "Authentication",
            "has_business_logic": False,
            "has_workflow": False,
            "has_ai_ml": False,
            "has_external_service": False,
            "integration_count": 0,
            "dependencies": {
                "database": "none",
                "external_service": "none",
                "infrastructure": "none",
            },
            "integrations": {"services": "none", "workflow": "none"},
        },
        # P0 - Incomplete Endpoints
        "GET /api/v1/assets/": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Asset Management",
            "has_business_logic": False,
            "has_workflow": False,
            "has_ai_ml": False,
            "has_external_service": False,
            "integration_count": 0,
            "dependencies": {
                "database": "none",
                "external_service": "none",
                "infrastructure": "none",
            },
            "integrations": {"services": "none", "workflow": "none"},
        },
        "POST /api/v1/assets/{id}/activate/": {
            "gap_type": GapType.INCOMPLETE,
            "category": "Asset Management",
            "has_business_logic": True,
            "has_workflow": True,
            "has_ai_ml": False,
            "has_external_service": False,
            "integration_count": 3,  # Contract, DQ, Compliance services
            "dependencies": {
                "database": "none",
                "external_service": "none",
                "infrastructure": "none",
            },
            "integrations": {"services": "multiple", "workflow": "complex"},
        },
        # P1 - Credential Management
        "GET /api/v1/scheduled-ingestions/{id}/credentials/": {
            "gap_type": GapType.MISSING,
            "category": "Credential Management",
            "has_business_logic": True,  # Credential masking
            "has_workflow": False,
            "has_ai_ml": False,
            "has_external_service": False,
            "integration_count": 0,
            "dependencies": {
                "database": "none",
                "external_service": "none",
                "infrastructure": "none",
            },
            "integrations": {"services": "none", "workflow": "none"},
        },
        "POST /api/v1/scheduled-ingestions/{id}/credentials/test/": {
            "gap_type": GapType.MISSING,
            "category": "Credential Management",
            "has_business_logic": True,
            "has_workflow": False,
            "has_ai_ml": False,
            "has_external_service": True,  # Connector services
            "integration_count": 1,
            "dependencies": {
                "database": "none",
                "external_service": "medium",
                "infrastructure": "none",
            },
            "integrations": {"services": "single", "workflow": "none"},
        },
        # P2 - AI/ML
        "POST /api/v1/ai/natural-language-search/": {
            "gap_type": GapType.MISSING,
            "category": "AI/ML",
            "has_business_logic": True,
            "has_workflow": False,
            "has_ai_ml": True,
            "has_external_service": True,  # LLM service
            "integration_count": 1,
            "dependencies": {
                "database": "none",
                "external_service": "complex",
                "infrastructure": "simple",
            },
            "integrations": {"services": "single", "workflow": "none"},
        },
        "POST /api/v1/ai/schema-matching/": {
            "gap_type": GapType.MISSING,
            "category": "AI/ML",
            "has_business_logic": True,
            "has_workflow": False,
            "has_ai_ml": True,
            "has_external_service": True,  # AI service
            "integration_count": 1,
            "dependencies": {
                "database": "none",
                "external_service": "complex",
                "infrastructure": "simple",
            },
            "integrations": {"services": "single", "workflow": "none"},
        },
        # P2 - Social Features
        "POST /api/v1/social/ratings/": {
            "gap_type": GapType.MISSING,
            "category": "Social Features",
            "has_business_logic": True,  # Rating validation, duplicate prevention
            "has_workflow": False,
            "has_ai_ml": False,
            "has_external_service": False,
            "integration_count": 0,
            "dependencies": {
                "database": "simple",
                "external_service": "none",
                "infrastructure": "none",
            },
            "integrations": {"services": "none", "workflow": "none"},
        },
        "POST /api/v1/social/reviews/": {
            "gap_type": GapType.MISSING,
            "category": "Social Features",
            "has_business_logic": True,  # Content moderation, spam detection
            "has_workflow": True,  # Moderation workflow
            "has_ai_ml": False,
            "has_external_service": False,
            "integration_count": 0,
            "dependencies": {
                "database": "simple",
                "external_service": "none",
                "infrastructure": "none",
            },
            "integrations": {"services": "none", "workflow": "simple"},
        },
        "POST /api/v1/social/comments/": {
            "gap_type": GapType.MISSING,
            "category": "Social Features",
            "has_business_logic": True,  # Threading, moderation
            "has_workflow": False,
            "has_ai_ml": False,
            "has_external_service": False,
            "integration_count": 0,
            "dependencies": {
                "database": "simple",
                "external_service": "none",
                "infrastructure": "none",
            },
            "integrations": {"services": "none", "workflow": "none"},
        },
        "POST /api/v1/social/communities/": {
            "gap_type": GapType.MISSING,
            "category": "Social Features",
            "has_business_logic": True,  # Community management
            "has_workflow": False,
            "has_ai_ml": False,
            "has_external_service": False,
            "integration_count": 0,
            "dependencies": {
                "database": "medium",
                "external_service": "none",
                "infrastructure": "none",
            },
            "integrations": {"services": "none", "workflow": "none"},
        },
        # P3 - Advanced Marketplace
        "GET /api/v1/marketplace/listings/{id}/preview/": {
            "gap_type": GapType.MISSING,
            "category": "Advanced Marketplace",
            "has_business_logic": True,  # Sample data generation, quality metrics
            "has_workflow": False,
            "has_ai_ml": False,
            "has_external_service": False,
            "integration_count": 1,  # DQ service for quality metrics
            "dependencies": {
                "database": "none",
                "external_service": "none",
                "infrastructure": "none",
            },
            "integrations": {"services": "single", "workflow": "none"},
        },
        # P3 - Developer Experience
        "GET /api/v1/developer/plugins/": {
            "gap_type": GapType.MISSING,
            "category": "Developer Experience",
            "has_business_logic": False,
            "has_workflow": False,
            "has_ai_ml": False,
            "has_external_service": False,
            "integration_count": 0,
            "dependencies": {
                "database": "none",
                "external_service": "none",
                "infrastructure": "none",
            },
            "integrations": {"services": "none", "workflow": "none"},
        },
        "GET /api/v1/developer/sdk/": {
            "gap_type": GapType.MISSING,
            "category": "Developer Experience",
            "has_business_logic": False,
            "has_workflow": False,
            "has_ai_ml": False,
            "has_external_service": False,
            "integration_count": 0,
            "dependencies": {
                "database": "none",
                "external_service": "none",
                "infrastructure": "none",
            },
            "integrations": {"services": "none", "workflow": "none"},
        },
    }

    # Estimate for each API
    for endpoint, characteristics in api_characteristics.items():
        complexity = estimator.determine_complexity(
            gap_type=characteristics["gap_type"],
            category=characteristics["category"],
            has_business_logic=characteristics["has_business_logic"],
            has_workflow=characteristics["has_workflow"],
            has_ai_ml=characteristics["has_ai_ml"],
            has_external_service=characteristics["has_external_service"],
            integration_count=characteristics["integration_count"],
        )

        estimate = estimator.estimate_effort(
            gap_type=characteristics["gap_type"],
            complexity=complexity,
            dependencies=characteristics["dependencies"],
            integrations=characteristics["integrations"],
            has_ai_ml=characteristics["has_ai_ml"],
            has_workflow=characteristics["has_workflow"],
            has_external_service=characteristics["has_external_service"],
        )

        estimates[endpoint] = {
            "complexity": complexity.value,
            "estimate": estimator.format_effort(estimate),
        }

    return estimates


def main():
    """Main entry point."""
    print("=" * 80)
    print("API Development Effort Estimation")
    print("=" * 80)

    APIEffortEstimator()
    estimates = estimate_api_efforts()

    total_hours = sum(e["estimate"]["total_hours"] for e in estimates.values())
    total_days = sum(e["estimate"]["total_days"] for e in estimates.values())

    print("\nTotal Estimated Effort:")
    print(f"  Hours: {total_hours:.1f}")
    print(f"  Days: {total_days:.1f} ({total_days / 5:.1f} weeks)")

    print("\nEffort by Endpoint:")
    for endpoint, data in sorted(estimates.items()):
        est = data["estimate"]
        print(f"  {endpoint}")
        print(f"    Complexity: {data['complexity']}")
        print(f"    Total: {est['total_hours']:.1f} hours ({est['total_days']:.1f} days)")
        print(f"    Development: {est['breakdown']['development']['hours']:.1f}h")
        print(f"    Testing: {est['breakdown']['testing']['hours']:.1f}h")
        print(f"    Documentation: {est['breakdown']['documentation']['hours']:.1f}h")


if __name__ == "__main__":
    main()
