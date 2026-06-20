"""
Business Rules Registry

Comprehensive registry system for business rules with:
- Decorator-based registration
- Auto-discovery of rules
- Rule execution orchestration
- Rule dependency resolution

All registry operations follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""

import importlib
import inspect
import pkgutil
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import (
    Any,
)

import structlog

from hub.apps.core.business_rules.base import (
    BusinessRules,
    RuleExecutionContext,
    ValidationResult,
)

logger = structlog.get_logger(__name__)


@dataclass
class RuleMetadata:
    """
    Metadata for a registered business rule.

    Attributes:
        rule_class: The BusinessRules class
        rule_name: Unique name for the rule
        description: Optional description
        tags: Optional tags for categorization
        dependencies: List of rule names this rule depends on
        priority: Execution priority (lower = higher priority)
        enabled: Whether the rule is enabled
    """

    rule_class: type[BusinessRules]
    rule_name: str
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    priority: int = 100  # Default priority
    enabled: bool = True
    openspec_ref: str | None = None  # Phase 274.15 — conformance metadata backfill

    def __post_init__(self):
        """Validate rule metadata."""
        if not issubclass(self.rule_class, BusinessRules):
            raise TypeError(
                f"Rule class {self.rule_class.__name__} must inherit from BusinessRules"
            )
        if not self.rule_name:
            raise ValueError("Rule name cannot be empty")
        if not isinstance(self.tags, list):
            raise TypeError("Tags must be a list")
        if not isinstance(self.dependencies, list):
            raise TypeError("Dependencies must be a list")


class BusinessRulesRegistry:
    """
    Registry for business rules.

    Provides:
    - Decorator-based rule registration
    - Rule discovery and auto-registration
    - Rule execution orchestration
    - Rule dependency resolution
    """

    def __init__(self):
        """Initialize the registry."""
        self._rules: dict[str, RuleMetadata] = {}
        self._dependency_graph: dict[str, set[str]] = defaultdict(set)
        self._reverse_dependency_graph: dict[str, set[str]] = defaultdict(set)

    def register(
        self,
        rule_name: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        depends_on: list[str] | None = None,
        priority: int = 100,
        enabled: bool = True,
        openspec_ref: str | None = None,
    ) -> Callable:
        """
        Decorator for registering business rules.

        Args:
            rule_name: Optional unique name (defaults to class name)
            description: Optional description
            tags: Optional tags for categorization
            depends_on: Optional list of rule names this rule depends on
            priority: Execution priority (lower = higher priority)
            enabled: Whether the rule is enabled
            openspec_ref: Optional path to the OpenSpec spec file this rule implements (Phase 274.15)

        Returns:
            Decorator function

        Example:
            @registry.register(
                rule_name="domain_validation",
                description="Validates domain structure",
                tags=["domain", "validation"],
                depends_on=["tenant_validation"],
                priority=10,
                openspec_ref="specs/domain-business-rules/spec.md",
            )
            class DomainBusinessRules(BusinessRules):
                ...
        """

        def decorator(rule_class: type[BusinessRules]) -> type[BusinessRules]:
            # Use provided name or class name
            name = rule_name or rule_class.__name__

            # Check if rule already registered
            if name in self._rules:
                existing = self._rules[name]
                # Check if it's the same class by comparing name and module
                # (Python creates new class objects even for same definition)
                if (
                    existing.rule_class.__name__ != rule_class.__name__
                    or existing.rule_class.__module__ != rule_class.__module__
                ):
                    raise ValueError(
                        f"Rule name '{name}' is already registered with a different class. "
                        f"Existing: {existing.rule_class.__name__} from {existing.rule_class.__module__}, "
                        f"New: {rule_class.__name__} from {rule_class.__module__}"
                    )
                # Rule already registered with same class, update metadata (idempotent)
                logger.debug(
                    "Updating metadata for existing rule",
                    rule_name=name,
                    rule_class=rule_class.__name__,
                )

            # Create metadata
            metadata = RuleMetadata(
                rule_class=rule_class,
                rule_name=name,
                description=description,
                tags=tags or [],
                dependencies=depends_on or [],
                priority=priority,
                enabled=enabled,
                openspec_ref=openspec_ref,
            )

            # Register rule
            self._rules[name] = metadata

            # Update dependency graph
            self._update_dependency_graph(name, metadata.dependencies)

            logger.info(
                "Business rule registered",
                rule_name=name,
                rule_class=rule_class.__name__,
                dependencies=metadata.dependencies,
                priority=priority,
                enabled=enabled,
            )

            return rule_class

        return decorator

    def _update_dependency_graph(self, rule_name: str, dependencies: list[str]):
        """
        Update dependency graph for a rule.

        Args:
            rule_name: Name of the rule
            dependencies: List of dependency rule names
        """
        # Remove old dependencies
        old_deps = self._dependency_graph.get(rule_name, set())
        for old_dep in old_deps:
            if old_dep in self._reverse_dependency_graph:
                self._reverse_dependency_graph[old_dep].discard(rule_name)

        # Add new dependencies
        self._dependency_graph[rule_name] = set(dependencies)
        for dep in dependencies:
            self._reverse_dependency_graph[dep].add(rule_name)

    def register_instance(self):
        """Phase 274.6 — removed. Use @register_rule decorator instead."""
        raise NotImplementedError(
            "BusinessRulesRegistry.register_instance() was removed in Phase 274.6. "
            "Use the @register_rule decorator instead."
        )

    def get_rule(self, rule_name: str) -> RuleMetadata | None:
        """
        Get rule metadata by name.

        Args:
            rule_name: Rule name

        Returns:
            RuleMetadata or None if not found
        """
        return self._rules.get(rule_name)

    def get_all_rules(self) -> dict[str, RuleMetadata]:
        """
        Get all registered rules.

        Returns:
            Dictionary mapping rule names to RuleMetadata
        """
        return self._rules.copy()

    def discover_rules(
        self,
        package: str | Any,
        rule_name_pattern: str | None = None,
        tags: list[str] | None = None,
        enabled_only: bool = True,
    ) -> list[str]:
        """
        Auto-discover and register business rules from a package.

        Args:
            package: Package or module to search (string path or module object)
            rule_name_pattern: Optional pattern to match rule names
            tags: Optional tags filter
            enabled_only: Only discover enabled rules

        Returns:
            List of discovered rule names

        Example:
            # Discover from a package
            registry.discover_rules('hub.apps.mesh.business_rules')

            # Discover from current module
            import hub.apps.mesh.business_rules
            registry.discover_rules(hub.apps.mesh.business_rules)
        """
        discovered = []

        try:
            # Convert package to module if string
            if isinstance(package, str):
                module = importlib.import_module(package)
            else:
                module = package

            # Walk through package modules
            if hasattr(module, "__path__"):
                # It's a package, walk through submodules
                for _, modname, ispkg in pkgutil.walk_packages(
                    module.__path__, module.__name__ + "."
                ):
                    if not ispkg:
                        try:
                            submodule = importlib.import_module(modname)
                            discovered.extend(
                                self._discover_rules_from_module(
                                    submodule, rule_name_pattern, tags, enabled_only
                                )
                            )
                        except Exception as e:
                            logger.warning(
                                "Failed to import module during rule discovery",
                                module=modname,
                                error=str(e),
                                exc_info=True,
                            )
            else:
                # It's a single module
                discovered.extend(
                    self._discover_rules_from_module(module, rule_name_pattern, tags, enabled_only)
                )

        except Exception as e:
            logger.error(
                "Failed to discover rules from package",
                package=str(package),
                error=str(e),
                exc_info=True,
            )

        logger.info(
            "Rule discovery completed",
            package=str(package),
            discovered_count=len(discovered),
            discovered_rules=discovered,
        )

        return discovered

    def _discover_rules_from_module(
        self,
        module: Any,
        rule_name_pattern: str | None = None,
        tags: list[str] | None = None,
        enabled_only: bool = True,
    ) -> list[str]:
        """
        Discover rules from a single module.

        Args:
            module: Module to search
            rule_name_pattern: Optional pattern to match rule names
            tags: Optional tags filter
            enabled_only: Only discover enabled rules

        Returns:
            List of discovered rule names
        """
        discovered = []

        # Find all BusinessRules subclasses in module
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            # Check if it's a BusinessRules subclass (but not BusinessRules itself)
            if (
                issubclass(obj, BusinessRules)
                and obj != BusinessRules
                and obj.__module__ == module.__name__
            ):
                rule_name = obj.__name__

                # Check pattern match
                if rule_name_pattern and rule_name_pattern not in rule_name:
                    continue

                # Check if already registered
                if rule_name in self._rules:
                    logger.debug("Rule already registered, skipping", rule_name=rule_name)
                    continue

                # Register discovered rule
                try:
                    self.register(rule_name=rule_name)(obj)
                    discovered.append(rule_name)
                except Exception as e:
                    logger.warning(
                        "Failed to register discovered rule",
                        rule_name=rule_name,
                        error=str(e),
                        exc_info=True,
                    )

        return discovered

    def get_dependencies(self, rule_name: str) -> set[str]:
        """
        Get dependencies for a rule.

        Args:
            rule_name: Rule name

        Returns:
            Set of dependency rule names
        """
        return self._dependency_graph.get(rule_name, set()).copy()

    def get_dependents(self, rule_name: str) -> set[str]:
        """
        Get rules that depend on this rule.

        Args:
            rule_name: Rule name

        Returns:
            Set of dependent rule names
        """
        return self._reverse_dependency_graph.get(rule_name, set()).copy()

    def resolve_execution_order(self, rule_names: list[str] | None = None) -> list[str]:
        """
        Resolve execution order for rules based on dependencies.

        Uses topological sort to ensure dependencies are executed before dependents.

        Args:
            rule_names: Optional list of rule names to resolve order for.
                      If None, resolves order for all enabled rules.

        Returns:
            List of rule names in execution order

        Raises:
            ValueError: If circular dependencies are detected
        """
        # Get rules to process
        if rule_names is None:
            # All enabled rules
            rules_to_process = [name for name, metadata in self._rules.items() if metadata.enabled]
        else:
            # Validate all rules exist
            for name in rule_names:
                if name not in self._rules:
                    raise ValueError(f"Rule '{name}' not found in registry")
            rules_to_process = rule_names

        # Build dependency graph for selected rules
        graph: dict[str, set[str]] = {}
        for rule_name in rules_to_process:
            metadata = self._rules[rule_name]
            # Only include dependencies that are in rules_to_process
            graph[rule_name] = {dep for dep in metadata.dependencies if dep in rules_to_process}

        # Topological sort
        in_degree: dict[str, int] = dict.fromkeys(rules_to_process, 0)
        for rule_name, deps in graph.items():
            for _dep in deps:
                in_degree[rule_name] += 1

        # Priority queue (lower priority = higher priority)
        queue = deque([name for name in rules_to_process if in_degree[name] == 0])
        # Sort by priority
        queue = deque(sorted(queue, key=lambda n: self._rules[n].priority))

        result: list[str] = []
        processed = set()

        while queue:
            rule_name = queue.popleft()
            if rule_name in processed:
                continue

            result.append(rule_name)
            processed.add(rule_name)

            # Update in-degrees of dependents
            for dependent in self._reverse_dependency_graph.get(rule_name, set()):
                if dependent in rules_to_process and dependent not in processed:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

            # Re-sort queue by priority
            queue = deque(sorted(queue, key=lambda n: self._rules[n].priority))

        # Check for circular dependencies
        if len(result) != len(rules_to_process):
            remaining = set(rules_to_process) - set(result)
            raise ValueError(f"Circular dependency detected. Rules not processed: {remaining}")

        return result

    # Phase 274.6 — removed. Use individual rule execute() or RuleChain instead.
    def execute_rules(
        self,
        rule_names: list[str] | None = None,
        context: RuleExecutionContext | None = None,
        tenant_id: str | None = None,
        user_id: str | None = None,
        short_circuit: bool = True,
        use_cache: bool | None = None,
        **kwargs,
    ) -> dict[str, ValidationResult]:
        raise NotImplementedError(
            "BusinessRulesRegistry.execute_rules() was removed in Phase 274.6. "
        )

    def enable_rule(self, rule_name: str) -> None:
        """Phase 274.6 — removed."""
        raise NotImplementedError(
            "BusinessRulesRegistry.enable_rule() was removed in Phase 274.6. "
            "Use per-tenant feature flags instead."
        )

    def disable_rule(self, rule_name: str) -> None:
        """Phase 274.6 — removed."""
        raise NotImplementedError(
            "BusinessRulesRegistry.disable_rule() was removed in Phase 274.6. "
            "Use per-tenant feature flags instead."
        )
        """
        Disable a rule.

        Args:
            rule_name: Rule name

        Raises:
            ValueError: If rule not found
        """
        if rule_name not in self._rules:
            raise ValueError(f"Rule '{rule_name}' not found")
        self._rules[rule_name].enabled = False
        logger.info("Rule disabled", rule_name=rule_name)

    def clear(self) -> None:
        """Clear all registered rules."""
        self._rules.clear()
        self._dependency_graph.clear()
        self._reverse_dependency_graph.clear()
        logger.info("Registry cleared")


# Global registry instance
_registry = BusinessRulesRegistry()


def get_registry() -> BusinessRulesRegistry:
    """
    Get the global business rules registry instance.

    Returns:
        BusinessRulesRegistry instance
    """
    return _registry


# Convenience decorator
def register_rule(
    rule_name: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    depends_on: list[str] | None = None,
    priority: int = 100,
    enabled: bool = True,
    openspec_ref: str | None = None,
) -> Callable:
    """
    Decorator for registering business rules with the global registry.

    Args:
        rule_name: Optional unique name (defaults to class name)
        description: Optional description
        tags: Optional tags for categorization
        depends_on: Optional list of rule names this rule depends on
        priority: Execution priority (lower = higher priority)
        enabled: Whether the rule is enabled
        openspec_ref: Optional path to the OpenSpec spec file this rule implements (Phase 274.15)

    Returns:
        Decorator function

    Example:
        @register_rule(
            rule_name="domain_validation",
            description="Validates domain structure",
            tags=["domain", "validation"],
            depends_on=["tenant_validation"],
            priority=10,
            openspec_ref="specs/domain-business-rules/spec.md",
        )
        class DomainBusinessRules(BusinessRules):
            ...
    """
    return _registry.register(
        rule_name=rule_name,
        description=description,
        tags=tags,
        depends_on=depends_on,
        priority=priority,
        enabled=enabled,
        openspec_ref=openspec_ref,
    )
