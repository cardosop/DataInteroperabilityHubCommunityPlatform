"""
Business Rules Base Class

Comprehensive base class for implementing business rules validation with:
- Validation result structure (is_valid, errors, warnings, details)
- Rule execution context (tenant_id, user_id, resource, metadata)
- Rule composition (combine multiple rules, short-circuit on error)
- Rule caching (cache validation results with TTL)
- Rule execution metrics (Prometheus)
- Rule execution logging (structured logging)
- Rule execution tracing (OpenTelemetry)

All validation methods follow engineering best practices:
- No mocks/stubs - use real services and models
- Fix root causes, not symptoms
- Comprehensive error messages with context
- Follow DRY, SOLID, and clean code principles
"""
import hashlib
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
from functools import wraps

from django.core.cache import cache
from django.conf import settings

import structlog

# OpenTelemetry imports (optional)
try:
    from opentelemetry import trace
    from hub.apps.observability.otel_config import get_tracer
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    trace = None
    get_tracer = None

# OpenTelemetry metrics imports (optional)
try:
    from hub.apps.observability.otel_metrics import get_meter
    OPENTELEMETRY_METRICS_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_METRICS_AVAILABLE = False
    get_meter = None

logger = structlog.get_logger(__name__)

# Cache TTL for business rules validation results (in seconds)
CACHE_TTL_BUSINESS_RULES = getattr(settings, 'CACHE_TTL_BUSINESS_RULES', 300)  # 5 minutes default

# Cache key prefix
CACHE_PREFIX_BUSINESS_RULES = "business_rules:validation"


@dataclass
class ValidationResult:
    """
    Result of a validation operation.

    Attributes:
        is_valid: Whether the validation passed
        errors: List of error messages
        warnings: List of warning messages
        details: Additional context dictionary
    """
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        """Allow using ValidationResult in boolean context."""
        return self.is_valid

    def __str__(self) -> str:
        """String representation for debugging."""
        status = "VALID" if self.is_valid else "INVALID"
        error_count = len(self.errors)
        warning_count = len(self.warnings)
        return (
            f"ValidationResult({status}, errors={error_count}, "
            f"warnings={warning_count})"
        )

    def combine(self, other: 'ValidationResult') -> 'ValidationResult':
        """
        Combine this result with another result.

        Args:
            other: Another ValidationResult to combine

        Returns:
            New ValidationResult combining both results
        """
        return ValidationResult(
            is_valid=self.is_valid and other.is_valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
            details={**self.details, **other.details}
        )


@dataclass
class RuleExecutionContext:
    """
    Context for rule execution.

    Attributes:
        tenant_id: Optional tenant ID for tenant-specific validation
        user_id: Optional user ID for permission and cross-tenant validation
        resource: Optional resource being validated (e.g., model instance)
        metadata: Optional additional metadata dictionary
    """
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    resource: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for caching/logging."""
        return {
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'resource_id': str(self.resource.id) if self.resource and hasattr(self.resource, 'id') else None,
            'resource_type': type(self.resource).__name__ if self.resource else None,
            'metadata': self.metadata,
        }

    def get_cache_key_suffix(self) -> str:
        """
        Generate cache key suffix from context.

        Returns:
            String suffix for cache key generation
        """
        context_dict = self.to_dict()
        # Remove resource object (not serializable) and use resource_id instead
        context_dict.pop('resource', None)
        context_str = json.dumps(context_dict, sort_keys=True, default=str)
        return hashlib.md5(context_str.encode()).hexdigest()


T = TypeVar('T', bound='BusinessRules')


def _inc_br_failure(rule_instance, rule_name: str, context) -> None:
    """Phase 78: increment business_rule_validation_failures_total counter."""
    try:
        from hub.apps.observability.otel_metrics import (
            business_rule_validation_failures_total,
        )
        tenant_id = ""
        if context is not None:
            tenant_id = str(getattr(context, "tenant_id", "") or "")
        module = rule_instance.__class__.__module__.rsplit(".", 1)[0].rsplit(".", 1)[-1]
        business_rule_validation_failures_total.labels(
            module=module,
            rule_name=rule_name,
            tenant_id=tenant_id,
        ).inc()
    except Exception:
        pass


class BusinessRules(ABC):
    """
    Base class for business rules validation.

    Provides:
    - Standardized validation result structure
    - Rule execution context management
    - Rule composition (combine multiple rules, short-circuit on error)
    - Rule caching (cache validation results with TTL)
    - Rule execution metrics (Prometheus)
    - Rule execution logging (structured logging)
    - Rule execution tracing (OpenTelemetry)

    Subclasses should implement validate() method and optionally override
    get_cache_ttl() and get_rule_name() methods.
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        enable_caching: bool = True,
        enable_metrics: bool = True,
        enable_tracing: bool = True,
        enable_logging: bool = True
    ):
        """
        Initialize BusinessRules instance.

        Args:
            tenant_id: Optional tenant ID for tenant-specific validation
            user_id: Optional user ID for permission validation
            enable_caching: Enable result caching (default: True)
            enable_metrics: Enable Prometheus metrics (default: True)
            enable_tracing: Enable OpenTelemetry tracing (default: True)
            enable_logging: Enable structured logging (default: True)
        """
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.enable_caching = enable_caching
        self.enable_metrics = enable_metrics
        self.enable_tracing = enable_tracing
        self.enable_logging = enable_logging

        # Initialize metrics if available
        self._metrics_initialized = False
        if self.enable_metrics and OPENTELEMETRY_METRICS_AVAILABLE:
            self._init_metrics()

    def _init_metrics(self):
        """Initialize Prometheus metrics."""
        if self._metrics_initialized:
            return

        try:
            meter = get_meter()
            if meter is not None:
                rule_name = self.get_rule_name()

                # Counter for rule executions
                self._metric_executions = meter.create_counter(
                    name='business_rules_executions_total',
                    description='Total number of business rule executions',
                    unit='1'
                )

                # Histogram for rule execution duration
                self._metric_duration = meter.create_histogram(
                    name='business_rules_duration_seconds',
                    description='Business rule execution duration in seconds',
                    unit='s'
                )

                # Counter for rule validation results
                self._metric_results = meter.create_counter(
                    name='business_rules_results_total',
                    description='Total number of business rule validation results',
                    unit='1'
                )

                self._metrics_initialized = True
                logger.debug(
                    "Business rules metrics initialized",
                    rule_name=rule_name
                )
        except Exception as e:
            logger.warning(
                "Failed to initialize business rules metrics",
                error=str(e),
                exc_info=True
            )

    def get_rule_name(self) -> str:
        """
        Get rule name for metrics and logging.

        Returns:
            Rule name string (default: class name)
        """
        return self.__class__.__name__

    def get_cache_ttl(self) -> int:
        """
        Get cache TTL in seconds.

        Returns:
            Cache TTL in seconds (default: CACHE_TTL_BUSINESS_RULES)
        """
        # Read from settings dynamically to support test overrides
        return getattr(settings, 'CACHE_TTL_BUSINESS_RULES', 300)

    def create_context(
        self,
        resource: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RuleExecutionContext:
        """
        Create rule execution context.

        Args:
            resource: Optional resource being validated
            metadata: Optional additional metadata

        Returns:
            RuleExecutionContext instance
        """
        return RuleExecutionContext(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            resource=resource,
            metadata=metadata or {}
        )

    def _get_cache_key(
        self,
        rule_name: str,
        context: RuleExecutionContext,
        *args,
        **kwargs
    ) -> str:
        """
        Generate cache key for validation result.

        Args:
            rule_name: Name of the rule
            context: Rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Cache key string
        """
        # Create cache key components
        key_parts = [
            CACHE_PREFIX_BUSINESS_RULES,
            rule_name,
            context.get_cache_key_suffix(),
        ]

        # Add args/kwargs to cache key if provided
        if args or kwargs:
            args_str = json.dumps(
                {'args': args, 'kwargs': kwargs},
                sort_keys=True,
                default=str
            )
            args_hash = hashlib.md5(args_str.encode()).hexdigest()
            key_parts.append(args_hash)

        return ':'.join(str(part) for part in key_parts)

    def _record_metrics(
        self,
        rule_name: str,
        duration: float,
        is_valid: bool,
        error_count: int,
        warning_count: int
    ):
        """Record Prometheus metrics."""
        if not self.enable_metrics or not self._metrics_initialized:
            return

        try:
            attributes = {
                'rule_name': rule_name,
                'result': 'valid' if is_valid else 'invalid',
            }

            # Record execution count
            self._metric_executions.add(1, attributes=attributes)

            # Record duration
            self._metric_duration.record(duration, attributes=attributes)

            # Record result with error/warning counts
            result_attributes = {
                **attributes,
                'has_errors': 'true' if error_count > 0 else 'false',
                'has_warnings': 'true' if warning_count > 0 else 'false',
            }
            self._metric_results.add(1, attributes=result_attributes)
        except Exception as e:
            logger.warning(
                "Failed to record business rules metrics",
                error=str(e),
                exc_info=True
            )

    def _log_execution(
        self,
        rule_name: str,
        context: RuleExecutionContext,
        result: ValidationResult,
        duration: float,
        cached: bool = False
    ):
        """Log rule execution with structured logging."""
        if not self.enable_logging:
            return

        log_level = 'info' if result.is_valid else 'warning'
        log_data = {
            'rule_name': rule_name,
            'tenant_id': context.tenant_id,
            'user_id': context.user_id,
            'is_valid': result.is_valid,
            'error_count': len(result.errors),
            'warning_count': len(result.warnings),
            'duration_seconds': duration,
            'cached': cached,
        }

        if context.resource:
            log_data['resource_type'] = type(context.resource).__name__
            if hasattr(context.resource, 'id'):
                log_data['resource_id'] = str(context.resource.id)

        if result.errors:
            log_data['errors'] = result.errors
        if result.warnings:
            log_data['warnings'] = result.warnings

        getattr(logger, log_level)(
            "Business rule executed",
            **log_data
        )

    def _create_trace_span(
        self,
        rule_name: str,
        context: RuleExecutionContext
    ):
        """
        Create OpenTelemetry trace span.

        Returns:
            Span context manager or None if tracing not available
        """
        if not self.enable_tracing or not OPENTELEMETRY_AVAILABLE:
            return None

        try:
            tracer = get_tracer(__name__)
            if tracer is None:
                return None

            span = tracer.start_as_current_span(
                f"business_rules.{rule_name}",
                attributes={
                    'business_rules.rule_name': rule_name,
                    'business_rules.tenant_id': context.tenant_id or '',
                    'business_rules.user_id': context.user_id or '',
                }
            )
            return span
        except Exception as e:
            logger.warning(
                "Failed to create trace span",
                error=str(e),
                exc_info=True
            )
            return None

    @abstractmethod
    def validate(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        **kwargs
    ) -> ValidationResult:
        """
        Validate business rules.

        Subclasses must implement this method.

        Args:
            context: Optional rule execution context
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            ValidationResult instance
        """
        pass

    def execute(
        self,
        context: Optional[RuleExecutionContext] = None,
        *args,
        use_cache: Optional[bool] = None,
        **kwargs
    ) -> ValidationResult:
        """
        Execute business rule validation with caching, metrics, logging, and tracing.

        Args:
            context: Optional rule execution context (creates default if not provided)
            *args: Additional positional arguments passed to validate()
            use_cache: Override caching setting (default: uses self.enable_caching) - keyword-only
            **kwargs: Additional keyword arguments passed to validate()

        Returns:
            ValidationResult instance
        """
        # Create context if not provided
        if context is None:
            resource = kwargs.get('resource')
            metadata = kwargs.get('metadata', {})
            context = self.create_context(resource=resource, metadata=metadata)

        rule_name = self.get_rule_name()
        start_time = time.time()

        # Determine if caching should be used
        cache_enabled = use_cache if use_cache is not None else self.enable_caching

        # Try to get from cache
        cached_result = None
        if cache_enabled:
            cache_key = self._get_cache_key(rule_name, context, *args, **kwargs)
            try:
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    duration = time.time() - start_time
                    self._log_execution(rule_name, context, cached_result, duration, cached=True)
                    self._record_metrics(
                        rule_name,
                        duration,
                        cached_result.is_valid,
                        len(cached_result.errors),
                        len(cached_result.warnings)
                    )
                    return cached_result
            except Exception as e:
                logger.warning(
                    "Failed to get cached validation result",
                    cache_key=cache_key,
                    error=str(e),
                    exc_info=True
                )

        # Create trace span context manager
        span_context = self._create_trace_span(rule_name, context)

        # Use span as context manager if available
        if span_context:
            span = span_context.__enter__()
        else:
            span = None

        try:
            # Execute validation
            result = self.validate(context, *args, **kwargs)

            # Calculate duration
            duration = time.time() - start_time

            # Cache result if enabled
            if cache_enabled and result.is_valid:
                # Only cache valid results to avoid caching errors
                cache_key = self._get_cache_key(rule_name, context, *args, **kwargs)
                try:
                    cache.set(cache_key, result, self.get_cache_ttl())
                except Exception as e:
                    logger.warning(
                        "Failed to cache validation result",
                        cache_key=cache_key,
                        error=str(e),
                        exc_info=True
                    )

            # Record metrics
            self._record_metrics(
                rule_name,
                duration,
                result.is_valid,
                len(result.errors),
                len(result.warnings)
            )

            # Phase 78: Prometheus counter for validation failures
            if not result.is_valid:
                _inc_br_failure(self, rule_name, context)

            # Log execution
            self._log_execution(rule_name, context, result, duration, cached=False)

            # Add span attributes
            if span:
                try:
                    span.set_attribute('business_rules.is_valid', result.is_valid)
                    span.set_attribute('business_rules.error_count', len(result.errors))
                    span.set_attribute('business_rules.warning_count', len(result.warnings))
                    span.set_attribute('business_rules.duration_seconds', duration)
                except Exception:
                    pass

            return result

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "Business rule execution failed",
                rule_name=rule_name,
                error=str(e),
                duration_seconds=duration,
                exc_info=True
            )

            # Record error metrics
            if self.enable_metrics and self._metrics_initialized:
                try:
                    attributes = {
                        'rule_name': rule_name,
                        'result': 'error',
                    }
                    self._metric_executions.add(1, attributes=attributes)
                    self._metric_duration.record(duration, attributes=attributes)
                except Exception:
                    pass

            # Add error to span
            if span:
                try:
                    span.record_exception(e)
                    if OPENTELEMETRY_AVAILABLE and trace:
                        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                except Exception:
                    pass

            # Phase 78: also count exceptions as validation failures
            _inc_br_failure(self, rule_name, context)

            # Return error result
            return ValidationResult(
                is_valid=False,
                errors=[f"Business rule execution failed: {str(e)}"],
                details={'exception_type': type(e).__name__}
            )
        finally:
            # End span context manager
            if span_context:
                try:
                    span_context.__exit__(None, None, None)
                except Exception:
                    pass

    def compose(
        self,
        *rules: Callable[[RuleExecutionContext], ValidationResult],
        context: Optional[RuleExecutionContext] = None,
        short_circuit: bool = True
    ) -> ValidationResult:
        """
        Compose multiple rules into a single validation result.

        Args:
            *rules: Rule functions to execute (each takes context and returns ValidationResult)
            context: Optional rule execution context (creates default if not provided)
            short_circuit: If True, stop on first error (default: True)

        Returns:
            Combined ValidationResult from all rules
        """
        if context is None:
            context = self.create_context()

        combined_result = ValidationResult(is_valid=True)

        for i, rule in enumerate(rules):
            rule_name = f"{self.get_rule_name()}.composed_rule_{i}"
            start_time = time.time()

            try:
                # Execute rule
                result = rule(context)

                # Combine results
                combined_result = combined_result.combine(result)

                # Log individual rule execution
                if self.enable_logging:
                    duration = time.time() - start_time
                    logger.debug(
                        "Composed rule executed",
                        rule_name=rule_name,
                        is_valid=result.is_valid,
                        error_count=len(result.errors),
                        warning_count=len(result.warnings),
                        duration_seconds=duration
                    )

                # Short-circuit on error if enabled
                if short_circuit and not result.is_valid:
                    logger.debug(
                        "Short-circuiting rule composition due to error",
                        rule_name=rule_name,
                        error_count=len(result.errors)
                    )
                    break

            except Exception as e:
                logger.error(
                    "Composed rule execution failed",
                    rule_name=rule_name,
                    error=str(e),
                    exc_info=True
                )
                error_result = ValidationResult(
                    is_valid=False,
                    errors=[f"Rule {rule_name} execution failed: {str(e)}"]
                )
                combined_result = combined_result.combine(error_result)

                if short_circuit:
                    break

        return combined_result

    @classmethod
    def create_rule_function(
        cls,
        rule_func: Callable[[RuleExecutionContext, Any], ValidationResult],
        rule_name: Optional[str] = None
    ) -> Callable[[RuleExecutionContext], ValidationResult]:
        """
        Create a rule function that can be used with compose().

        Args:
            rule_func: Function that takes context and optional args/kwargs, returns ValidationResult
            rule_name: Optional name for the rule (default: function name)

        Returns:
            Rule function compatible with compose()
        """
        name = rule_name or rule_func.__name__

        @wraps(rule_func)
        def wrapped_rule(context: RuleExecutionContext) -> ValidationResult:
            try:
                return rule_func(context)
            except Exception as e:
                logger.error(
                    "Rule function execution failed",
                    rule_name=name,
                    error=str(e),
                    exc_info=True
                )
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Rule {name} execution failed: {str(e)}"]
                )

        wrapped_rule.__name__ = name
        return wrapped_rule

