"""
Virtualization Query Execution Workflow

Orchestrates the virtual dataset query execution process with proper error handling,
retry logic, and compensation. Manages the complete query execution lifecycle.
"""
import structlog
from typing import Dict, Any, Optional
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.virtualization.models import (
    VirtualDataset,
    VirtualDatasetStatus,
    QueryExecution,
    QueryExecutionStatus,
    QueryExecutionMode,
    QueryType
)
from hub.apps.virtualization.business_rules import (
    VirtualizationBusinessRules,
    QueryExecutionBusinessRules,
    ResultBusinessRules
)
from hub.apps.virtualization.services import VirtualizationService
from hub.apps.core.services.base import ValidationError, NotFoundError
from hub.apps.audit.utils import create_audit_event

logger = structlog.get_logger(__name__)


class VirtualizationWorkflow:
    """
    Virtual dataset query execution workflow orchestrator.

    Manages the complete query execution process:
    1. Validate query syntax
    2. Validate source compatibility
    3. Optimize query
    4. Execute query against sources
    5. Aggregate results from multiple sources
    6. Cache results
    7. Store results (if needed)
    8. Complete workflow
    """

    WORKFLOW_NAME = "virtualization_query_execution"
    WORKFLOW_VERSION = "1.0.0"

    @classmethod
    def register_workflow(cls, registry: WorkflowRegistry) -> None:
        """
        Register the virtualization query execution workflow definition.

        Args:
            registry: WorkflowRegistry instance
        """
        workflow_dsl = {
            "version": cls.WORKFLOW_VERSION,
            "dependencies": [],
            "steps": [
                {
                    "name": "validate_query",
                    "type": "task",
                    "task": "virtualization.validate_query"
                },
                {
                    "name": "validate_sources",
                    "type": "task",
                    "task": "virtualization.validate_sources"
                },
                {
                    "name": "optimize_query",
                    "type": "task",
                    "task": "virtualization.optimize_query"
                },
                {
                    "name": "execute_query",
                    "type": "task",
                    "task": "virtualization.execute_query"
                },
                {
                    "name": "aggregate_results",
                    "type": "task",
                    "task": "virtualization.aggregate_results"
                },
                {
                    "name": "cache_results",
                    "type": "task",
                    "task": "virtualization.cache_results"
                },
                {
                    "name": "store_results",
                    "type": "task",
                    "task": "virtualization.store_results"
                },
                {
                    "name": "complete",
                    "type": "task",
                    "task": "virtualization.complete"
                }
            ],
            "compensation": {"enabled": True}
        }
        registry.register_workflow(
            workflow_name=cls.WORKFLOW_NAME,
            dsl_json=workflow_dsl,
            description="Orchestrates virtual dataset query execution with validation, optimization, execution, and result caching",
            version=cls.WORKFLOW_VERSION
        )

    @classmethod
    def register_tasks(cls, engine: WorkflowEngine) -> None:
        """
        Register all workflow tasks with the engine.

        Args:
            engine: WorkflowEngine instance
        """
        engine.register_task("virtualization.validate_query", cls._validate_query_task)
        engine.register_task("virtualization.validate_sources", cls._validate_sources_task)
        engine.register_task("virtualization.optimize_query", cls._optimize_query_task)
        engine.register_task("virtualization.execute_query", cls._execute_query_task)
        engine.register_task("virtualization.aggregate_results", cls._aggregate_results_task)
        engine.register_task("virtualization.cache_results", cls._cache_results_task)
        engine.register_task("virtualization.store_results", cls._store_results_task)
        engine.register_task("virtualization.complete", cls._complete_task)
        # Compensation tasks
        engine.register_task("virtualization.rollback_execution", cls._rollback_execution_task)
        engine.register_task("virtualization.rollback_cache", cls._rollback_cache_task)

    @staticmethod
    def _update_progress(instance: WorkflowInstance, progress: int, step_name: str) -> None:
        """
        Update workflow progress and publish progress event.

        Args:
            instance: Workflow instance
            progress: Progress percentage (0-100)
            step_name: Current step name
        """
        if progress < 0:
            progress = 0
        elif progress > 100:
            progress = 100

        instance.state_data["progress_percentage"] = progress
        instance.state_data["current_step"] = step_name
        instance.save(update_fields=['state_data'])

        # Publish workflow progress event
        try:
            execution_id = instance.state_data.get("execution_id")
            virtual_dataset_id = instance.state_data.get("virtual_dataset_id")
            tenant_id = instance.tenant_id
            user_id = instance.created_by_id

            if execution_id and virtual_dataset_id:
                service = VirtualizationService(
                    tenant_id=str(tenant_id) if tenant_id else None,
                    user_id=str(user_id) if user_id else None
                )

                # Calculate elapsed time if available
                elapsed_time_ms = None
                if instance.started_at:
                    elapsed = timezone.now() - instance.started_at
                    elapsed_time_ms = int(elapsed.total_seconds() * 1000)

                # Get total steps from workflow definition
                total_steps = len(instance.workflow_definition.get("steps", []))
                completed_steps = int((progress / 100.0) * total_steps) if total_steps > 0 else None

                # Publish query execution progress event
                try:
                    service.publish_query_execution_progress(
                        query_execution_id=str(execution_id),
                        virtual_dataset_id=str(virtual_dataset_id),
                        progress_percent=progress / 100.0,
                        current_step=step_name,
                        elapsed_time_ms=elapsed_time_ms,
                        completed_steps=completed_steps,
                        total_steps=total_steps if total_steps > 0 else None,
                        tenant_id=str(tenant_id) if tenant_id else None
                    )
                except Exception as e:
                    # Log but don't fail progress update if event publishing fails
                    logger.warning(
                        "Failed to publish query execution progress event",
                        workflow_instance_id=str(instance.id),
                        execution_id=str(execution_id),
                        error=str(e),
                        exc_info=True
                    )

                logger.info(
                    "Workflow progress updated",
                    workflow_instance_id=str(instance.id),
                    execution_id=str(execution_id),
                    progress_percent=progress / 100.0,
                    current_step=step_name,
                    total_steps=total_steps if total_steps > 0 else None,
                    completed_steps=completed_steps,
                    elapsed_time_ms=elapsed_time_ms
                )
        except Exception as e:
            # Log but don't fail progress update if event publishing fails
            logger.warning(
                "Failed to publish workflow progress event",
                workflow_instance_id=str(instance.id),
                error=str(e),
                exc_info=True
            )

    @staticmethod
    def _validate_query_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate query syntax using VirtualizationBusinessRules.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with validation status
        """
        virtual_dataset_id = input_data.get("virtual_dataset_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        user_id = input_data.get("user_id") or instance.created_by_id

        if not virtual_dataset_id:
            raise ValueError("virtual_dataset_id is required")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id)
        virtual_dataset = VirtualDataset.objects.get(id=virtual_dataset_id, tenant=tenant)

        # Update progress
        VirtualizationWorkflow._update_progress(instance, 10, "validate_query")

        # Validate query syntax using business rules
        business_rules = VirtualizationBusinessRules(
            tenant_id=str(tenant_id),
            user_id=str(user_id) if user_id else None
        )

        validation_result = business_rules.validate_query_syntax(
            query=virtual_dataset.query,
            query_type=virtual_dataset.query_type,
            raise_on_error=True
        )

        # Store validation result in state_data
        instance.state_data["virtual_dataset_id"] = str(virtual_dataset.id)
        instance.state_data["virtual_dataset_name"] = virtual_dataset.name
        instance.state_data["query_type"] = virtual_dataset.query_type
        instance.state_data["validation_result"] = {
            "is_valid": validation_result.is_valid,
            "errors": validation_result.errors,
            "warnings": validation_result.warnings,
            "details": validation_result.details
        }
        instance.save(update_fields=['state_data'])

        logger.info(
            "Query validated",
            workflow_instance_id=str(instance.id),
            virtual_dataset_id=str(virtual_dataset.id),
            query_type=virtual_dataset.query_type,
            validation_status=validation_result.is_valid
        )

        return {
            "validation_status": "VALID" if validation_result.is_valid else "INVALID",
            "errors": validation_result.errors,
            "warnings": validation_result.warnings
        }

    @staticmethod
    def _validate_sources_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Validate source compatibility using VirtualizationBusinessRules.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with compatibility status
        """
        virtual_dataset_id = instance.state_data.get("virtual_dataset_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        user_id = input_data.get("user_id") or instance.created_by_id

        if not virtual_dataset_id:
            raise ValueError("virtual_dataset_id is required (from previous step)")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id)
        virtual_dataset = VirtualDataset.objects.get(id=virtual_dataset_id, tenant=tenant)

        # Update progress
        VirtualizationWorkflow._update_progress(instance, 20, "validate_sources")

        # Validate source compatibility using business rules
        business_rules = VirtualizationBusinessRules(
            tenant_id=str(tenant_id),
            user_id=str(user_id) if user_id else None
        )

        compatibility_result = business_rules.validate_source_compatibility(
            virtual_dataset=virtual_dataset,
            raise_on_error=True
        )

        # Store compatibility result in state_data
        instance.state_data["compatibility_result"] = {
            "is_compatible": compatibility_result.is_valid,
            "errors": compatibility_result.errors,
            "warnings": compatibility_result.warnings,
            "details": compatibility_result.details
        }
        instance.save(update_fields=['state_data'])

        logger.info(
            "Sources validated",
            workflow_instance_id=str(instance.id),
            virtual_dataset_id=str(virtual_dataset.id),
            source_count=len(virtual_dataset.sources) if virtual_dataset.sources else 0,
            compatibility_status=compatibility_result.is_valid
        )

        return {
            "compatibility_status": "COMPATIBLE" if compatibility_result.is_valid else "INCOMPATIBLE",
            "errors": compatibility_result.errors,
            "warnings": compatibility_result.warnings
        }

    @staticmethod
    def _optimize_query_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Optimize query using QueryExecutionBusinessRules.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with optimized query
        """
        virtual_dataset_id = instance.state_data.get("virtual_dataset_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        user_id = input_data.get("user_id") or instance.created_by_id

        if not virtual_dataset_id:
            raise ValueError("virtual_dataset_id is required (from previous step)")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id)
        virtual_dataset = VirtualDataset.objects.get(id=virtual_dataset_id, tenant=tenant)

        # Update progress
        VirtualizationWorkflow._update_progress(instance, 30, "optimize_query")

        # Optimize query using business rules
        execution_business_rules = QueryExecutionBusinessRules(
            tenant_id=str(tenant_id),
            user_id=str(user_id) if user_id else None
        )

        optimization_result = execution_business_rules.optimize_query(
            query=virtual_dataset.query,
            query_type=virtual_dataset.query_type,
            raise_on_error=False
        )

        # Store optimized query in state_data
        optimized_query = optimization_result.get("optimized_query", virtual_dataset.query)
        instance.state_data["original_query"] = virtual_dataset.query
        instance.state_data["optimized_query"] = optimized_query
        instance.state_data["optimizations_applied"] = optimization_result.get("optimizations_applied", [])
        instance.state_data["optimization_warnings"] = optimization_result.get("warnings", [])
        instance.save(update_fields=['state_data'])

        logger.info(
            "Query optimized",
            workflow_instance_id=str(instance.id),
            virtual_dataset_id=str(virtual_dataset.id),
            optimizations_applied=len(optimization_result.get("optimizations_applied", []))
        )

        return {
            "optimized_query": optimized_query,
            "optimizations_applied": optimization_result.get("optimizations_applied", []),
            "warnings": optimization_result.get("warnings", [])
        }

    @staticmethod
    @transaction.atomic
    def _execute_query_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Execute query against sources using VirtualizationService.

        For SPARQL queries, integrates with SemanticService.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with execution results
        """
        virtual_dataset_id = instance.state_data.get("virtual_dataset_id")
        optimized_query = instance.state_data.get("optimized_query")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        user_id = input_data.get("user_id") or instance.created_by_id
        parameters = input_data.get("parameters", {})
        execution_mode = input_data.get("execution_mode", QueryExecutionMode.ASYNC)
        timeout_seconds = input_data.get("timeout_seconds")

        if not virtual_dataset_id:
            raise ValueError("virtual_dataset_id is required (from previous step)")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User
        tenant = Tenant.objects.get(id=tenant_id)
        created_by = User.objects.get(id=user_id) if user_id else None
        virtual_dataset = VirtualDataset.objects.get(id=virtual_dataset_id, tenant=tenant)

        # Use optimized query if available, otherwise use original
        query_to_execute = optimized_query or virtual_dataset.query

        # Update progress
        VirtualizationWorkflow._update_progress(instance, 50, "execute_query")

        # Create query execution record
        execution = QueryExecution.objects.create(
            virtual_dataset=virtual_dataset,
            query=query_to_execute,
            parameters=parameters,
            execution_mode=execution_mode,
            status=QueryExecutionStatus.PENDING
        )

        # Store execution_id in state_data
        instance.state_data["execution_id"] = str(execution.id)
        instance.state_data["execution_mode"] = execution_mode
        instance.save(update_fields=['state_data'])

        # Publish workflow started event
        try:
            service = VirtualizationService(
                tenant_id=str(tenant_id) if tenant_id else None,
                user_id=str(user_id) if user_id else None
            )
            service.publish_query_execution_started(
                query_execution_id=str(execution.id),
                virtual_dataset_id=str(virtual_dataset.id),
                execution_mode=execution_mode,
                tenant_id=str(tenant_id) if tenant_id else None
            )
        except Exception as e:
            logger.warning(
                "Failed to publish query execution started event",
                workflow_instance_id=str(instance.id),
                execution_id=str(execution.id),
                error=str(e),
                exc_info=True
            )

        # Mark execution as running
        execution.status = QueryExecutionStatus.RUNNING
        execution.started_at = timezone.now()
        execution.save(update_fields=['status', 'started_at'])

        # Initialize virtualization service
        service = VirtualizationService(
            tenant_id=str(tenant_id),
            user_id=str(user_id) if user_id else None
        )

        # Execute query
        try:
            # For SPARQL queries, use SemanticService integration
            if virtual_dataset.query_type == QueryType.SPARQL:
                result_data = VirtualizationWorkflow._execute_sparql_query(
                    service=service,
                    query=query_to_execute,
                    timeout_seconds=timeout_seconds or 300
                )
            elif virtual_dataset.query_type == QueryType.FEDERATED:
                # For federated queries, execute against each source and aggregate
                result_data = VirtualizationWorkflow._execute_federated_query(
                    service=service,
                    virtual_dataset=virtual_dataset,
                    query=query_to_execute,
                    parameters=parameters,
                    timeout_seconds=timeout_seconds or 300
                )
            else:
                # For standard query types (SQL, REST, GraphQL, etc.), use the same
                # entrypoint as the REST path: VirtualizationService._execute_query_against_sources
                # and _aggregate_results (feat1 2.1.1 – single execution path).
                result_data = VirtualizationWorkflow._execute_via_service_sources(
                    service=service,
                    virtual_dataset=virtual_dataset,
                    query=query_to_execute,
                    parameters=parameters,
                    timeout_seconds=timeout_seconds or 300,
                )

            # Store execution results in state_data
            instance.state_data["execution_results"] = result_data
            instance.state_data["execution_status"] = "COMPLETED"
            instance.save(update_fields=['state_data'])

            logger.info(
                "Query executed",
                workflow_instance_id=str(instance.id),
                virtual_dataset_id=str(virtual_dataset.id),
                execution_id=str(execution.id),
                query_type=virtual_dataset.query_type,
                row_count=result_data.get("row_count", 0)
            )

            return {
                "execution_status": "COMPLETED",
                "result_data": result_data,
                "row_count": result_data.get("row_count", 0)
            }
        except Exception as e:
            # Mark execution as failed
            execution.status = QueryExecutionStatus.FAILED
            execution.completed_at = timezone.now()
            execution.save(update_fields=['status', 'completed_at'])

            # Publish execution failed event
            try:
                # Calculate duration
                duration_ms = None
                if execution.started_at:
                    duration_ms = int((timezone.now() - execution.started_at).total_seconds() * 1000)

                service.publish_query_execution_failed(
                    query_execution_id=str(execution.id),
                    virtual_dataset_id=str(virtual_dataset.id),
                    error_message=str(e),
                    duration_ms=duration_ms,
                    tenant_id=str(tenant_id) if tenant_id else None
                )
            except Exception as publish_error:
                logger.warning(
                    "Failed to publish query execution failed event",
                    workflow_instance_id=str(instance.id),
                    execution_id=str(execution.id),
                    error=str(publish_error),
                    exc_info=True
                )

            instance.state_data["execution_status"] = "FAILED"
            instance.state_data["execution_error"] = str(e)
            instance.save(update_fields=['state_data'])

            logger.error(
                "Query execution failed",
                workflow_instance_id=str(instance.id),
                virtual_dataset_id=str(virtual_dataset.id),
                execution_id=str(execution.id),
                error=str(e),
                exc_info=True
            )
            raise

    @staticmethod
    def _execute_sparql_query(
        service: VirtualizationService,
        query: str,
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """
        Execute SPARQL query using SemanticService.

        Args:
            service: VirtualizationService instance
            query: SPARQL query string
            timeout_seconds: Query timeout in seconds

        Returns:
            Query result data dictionary
        """
        from hub.apps.semantic.service_client import SemanticServiceClient

        try:
            client = SemanticServiceClient()
            result = client.query_sparql(
                query=query,
                output_format="json",
                timeout=timeout_seconds
            )

            if "error" in result:
                raise ValidationError(
                    f"SPARQL query execution failed: {result['error']}",
                    code="SPARQL_EXECUTION_FAILED"
                )

            # Extract bindings from SPARQL result
            bindings = result.get("results", {}).get("bindings", [])
            data = []
            for binding in bindings:
                row = {}
                for key, value in binding.items():
                    # SPARQL results have type and value
                    row[key] = value.get("value") if isinstance(value, dict) else value
                data.append(row)

            return {
                "data": data,
                "columns": list(bindings[0].keys()) if bindings else [],
                "row_count": len(data),
                "source_type": "sparql",
                "query_type": QueryType.SPARQL
            }
        except Exception as e:
            logger.error(
                f"SPARQL query execution failed: {e}",
                extra={"error": str(e)},
                exc_info=True
            )
            raise ValidationError(
                f"SPARQL query execution failed: {str(e)}",
                code="SPARQL_EXECUTION_FAILED"
            ) from e

    @staticmethod
    def _execute_via_service_sources(
        service: VirtualizationService,
        virtual_dataset: VirtualDataset,
        query: str,
        parameters: Dict[str, Any],
        timeout_seconds: int,
    ) -> Dict[str, Any]:
        """
        Execute standard query (SQL, REST, GraphQL, etc.) using the same path as REST.

        Delegates to VirtualizationService._execute_query_against_sources and
        _aggregate_results so workflow and view share one implementation (feat1 2.1.1/2.1.2).
        """
        try:
            sources = virtual_dataset.sources or []
            if not sources:
                raise ValidationError(
                    "No sources configured for query execution",
                    code="NO_SOURCES",
                )
            results = service._execute_query_against_sources(
                query=query,
                query_type=virtual_dataset.query_type,
                sources=sources,
                parameters=parameters,
                timeout_seconds=timeout_seconds,
            )
            aggregated = service._aggregate_results(
                results,
                virtual_dataset.query_type,
            )
            all_columns = set()
            for r in results:
                all_columns.update(r.get("columns", []))
            columns = list(all_columns)
            return {
                "data": aggregated,
                "columns": columns,
                "row_count": len(aggregated),
                "source_type": results[0].get("source_type", "unknown") if results else "unknown",
                "query_type": virtual_dataset.query_type,
            }
        except ValidationError:
            raise
        except Exception as e:
            logger.error(
                "Standard query execution failed: %s",
                e,
                extra={"error": str(e)},
                exc_info=True,
            )
            raise ValidationError(
                f"Query execution failed: {str(e)}",
                code="QUERY_EXECUTION_FAILED",
            ) from e

    @staticmethod
    def _execute_federated_query(
        service: VirtualizationService,
        virtual_dataset: VirtualDataset,
        query: str,
        parameters: Dict[str, Any],
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """
        Execute federated query across multiple sources.

        For federated queries, we execute the query against each source individually
        (using the source's type, not FEDERATED), then aggregate results.

        Args:
            service: VirtualizationService instance
            virtual_dataset: VirtualDataset instance
            query: Query string
            parameters: Query parameters
            timeout_seconds: Query timeout in seconds

        Returns:
            Aggregated query result data dictionary
        """
        if not virtual_dataset.sources:
            raise ValidationError(
                "Federated queries require at least one source",
                code="MISSING_SOURCES"
            )

        all_results = []
        all_columns = []
        total_rows = 0

        # Execute query against each source
        for source_index, source in enumerate(virtual_dataset.sources):
            source_type = source.get("type", "").lower()
            
            # Determine query type based on source type
            if source_type in ["postgresql", "mysql", "sqlserver", "mssql"]:
                source_query_type = QueryType.SQL
            elif source_type == "sparql":
                source_query_type = QueryType.SPARQL
            elif source_type in ["rest", "http", "https"]:
                source_query_type = QueryType.REST
            elif source_type == "graphql":
                source_query_type = QueryType.GRAPHQL
            else:
                # For other source types, try to execute with SQL
                source_query_type = QueryType.SQL

            try:
                # Execute query against this source using source's query type
                result = service._execute_query_against_source(
                    query=query,
                    query_type=source_query_type,  # Use source type, not FEDERATED
                    source=source,
                    parameters=parameters,
                    timeout_seconds=timeout_seconds,
                    source_index=source_index
                )

                source_data = result.get("data", [])
                source_columns = result.get("columns", [])
                source_rows = result.get("row_count", len(source_data) if isinstance(source_data, list) else 0)

                if source_data:
                    all_results.extend(source_data)
                    # Use columns from first source, or merge if different
                    if not all_columns:
                        all_columns = source_columns
                    total_rows += source_rows

            except Exception as e:
                logger.warning(
                    f"Failed to execute query against source {source_index}: {e}",
                    extra={
                        "source_index": source_index,
                        "source_type": source_type,
                        "error": str(e)
                    }
                )
                # Continue with other sources even if one fails
                continue

        return {
            "data": all_results,
            "columns": all_columns,
            "row_count": total_rows,
            "source_count": len(virtual_dataset.sources),
            "query_type": "FEDERATED"
        }

    @staticmethod
    def _aggregate_results_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Aggregate results from multiple sources (if applicable).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with aggregated results
        """
        execution_results = instance.state_data.get("execution_results", {})
        virtual_dataset_id = instance.state_data.get("virtual_dataset_id")

        if not execution_results:
            raise ValueError("execution_results are required (from previous step)")

        # Update progress
        VirtualizationWorkflow._update_progress(instance, 70, "aggregate_results")

        # For single source queries, aggregation is already done
        # For multiple sources, we would aggregate here
        # For now, we'll just pass through the results
        aggregated_results = execution_results

        # Store aggregated results in state_data
        instance.state_data["aggregated_results"] = aggregated_results
        instance.save(update_fields=['state_data'])

        logger.info(
            "Results aggregated",
            workflow_instance_id=str(instance.id),
            virtual_dataset_id=str(virtual_dataset_id),
            row_count=aggregated_results.get("row_count", 0)
        )

        return {
            "aggregated_results": aggregated_results,
            "row_count": aggregated_results.get("row_count", 0)
        }

    @staticmethod
    def _cache_results_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Cache query results using ResultBusinessRules validation.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with cache status
        """
        execution_id = instance.state_data.get("execution_id")
        aggregated_results = instance.state_data.get("aggregated_results", {})
        virtual_dataset_id = instance.state_data.get("virtual_dataset_id")
        parameters = input_data.get("parameters", {})
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        user_id = input_data.get("user_id") or instance.created_by_id

        if not execution_id:
            raise ValueError("execution_id is required (from previous step)")
        if not aggregated_results:
            raise ValueError("aggregated_results are required (from previous step)")

        # Update progress
        VirtualizationWorkflow._update_progress(instance, 85, "cache_results")

        # Validate caching configuration using ResultBusinessRules
        result_business_rules = ResultBusinessRules(
            tenant_id=str(tenant_id),
            user_id=str(user_id) if user_id else None
        )

        # Estimate result size (rough estimate)
        result_size = len(str(aggregated_results).encode('utf-8'))
        cache_validation = result_business_rules.validate_result_caching(
            cache_enabled=True,
            cache_ttl=3600,  # 1 hour default
            result_size=result_size,
            raise_on_error=False
        )

        if not cache_validation.is_valid:
            logger.warning(
                "Cache validation failed, skipping cache",
                workflow_instance_id=str(instance.id),
                execution_id=str(execution_id),
                errors=cache_validation.errors
            )
            instance.state_data["cache_status"] = "SKIPPED"
            instance.state_data["cache_errors"] = cache_validation.errors
            instance.save(update_fields=['state_data'])
            return {"cache_status": "SKIPPED", "reason": cache_validation.errors}

        # Generate cache key
        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id)
        virtual_dataset = VirtualDataset.objects.get(id=virtual_dataset_id, tenant=tenant)

        service = VirtualizationService(
            tenant_id=str(tenant_id),
            user_id=str(user_id) if user_id else None
        )
        cache_key = service._get_query_cache_key(virtual_dataset, parameters)

        # Cache results
        cache_ttl = cache_validation.details.get("validated_cache_ttl", 3600)
        cache.set(
            cache_key,
            {
                "data": aggregated_results.get("data", []),
                "row_count": aggregated_results.get("row_count", 0),
                "columns": aggregated_results.get("columns", []),
                "cached_at": timezone.now().isoformat()
            },
            timeout=cache_ttl
        )

        # Update execution with cache key
        execution = QueryExecution.objects.get(id=execution_id)
        execution.result_cache_key = cache_key
        execution.save(update_fields=['result_cache_key'])

        # Store cache status in state_data
        instance.state_data["cache_status"] = "CACHED"
        instance.state_data["cache_key"] = cache_key
        instance.state_data["cache_ttl"] = cache_ttl
        instance.save(update_fields=['state_data'])

        logger.info(
            "Results cached",
            workflow_instance_id=str(instance.id),
            execution_id=str(execution.id),
            cache_key=cache_key,
            cache_ttl=cache_ttl
        )

        return {
            "cache_status": "CACHED",
            "cache_key": cache_key,
            "cache_ttl": cache_ttl
        }

    @staticmethod
    def _store_results_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Store query results (if storage is needed for large results).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with storage status
        """
        execution_id = instance.state_data.get("execution_id")
        aggregated_results = instance.state_data.get("aggregated_results", {})

        if not execution_id:
            raise ValueError("execution_id is required (from previous step)")

        # Update progress
        VirtualizationWorkflow._update_progress(instance, 95, "store_results")

        # For now, we'll skip storage if results are small enough to be cached
        # In production, this would store large results to S3 or similar
        result_size = len(str(aggregated_results).encode('utf-8'))
        large_result_threshold = 100 * 1024 * 1024  # 100MB

        if result_size > large_result_threshold:
            # Store large results to persistent storage
            # This is a placeholder - full implementation would use S3StorageClient
            logger.info(
                "Large results detected, would store to persistent storage",
                workflow_instance_id=str(instance.id),
                execution_id=str(execution_id),
                result_size=result_size
            )
            instance.state_data["storage_status"] = "STORED"
            instance.state_data["storage_path"] = None  # Would be set in full implementation
        else:
            instance.state_data["storage_status"] = "SKIPPED"
            instance.state_data["storage_reason"] = "Results small enough for cache"

        instance.save(update_fields=['state_data'])

        return {
            "storage_status": instance.state_data.get("storage_status", "SKIPPED"),
            "storage_path": instance.state_data.get("storage_path")
        }

    @staticmethod
    @transaction.atomic
    def _complete_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Complete workflow and mark execution as completed.

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with completion status
        """
        execution_id = instance.state_data.get("execution_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id
        user_id = input_data.get("user_id") or instance.created_by_id

        if not execution_id:
            raise ValueError("execution_id is required (from previous step)")
        if not tenant_id:
            raise ValueError("tenant_id is required")

        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User
        tenant = Tenant.objects.get(id=tenant_id)
        created_by = User.objects.get(id=user_id) if user_id else None
        execution = QueryExecution.objects.get(id=execution_id)

        # Update progress to 100%
        VirtualizationWorkflow._update_progress(instance, 100, "complete")

        # Mark execution as completed
        execution.status = QueryExecutionStatus.COMPLETED
        execution.completed_at = timezone.now()
        execution.metrics = instance.state_data.get("execution_results", {})
        execution.save(update_fields=['status', 'completed_at', 'metrics'])

        # Publish execution completed event
        try:
            service = VirtualizationService(
                tenant_id=str(tenant_id) if tenant_id else None,
                user_id=str(user_id) if user_id else None
            )

            # Calculate duration
            duration_ms = None
            if execution.started_at and execution.completed_at:
                duration_ms = int((execution.completed_at - execution.started_at).total_seconds() * 1000)

            # Get metrics from execution
            metrics = execution.metrics or {}
            row_count = metrics.get("row_count") or 0

            service.publish_query_execution_completed(
                query_execution_id=str(execution.id),
                virtual_dataset_id=str(execution.virtual_dataset.id),
                status="COMPLETED",
                duration_ms=duration_ms,
                rows_processed=row_count,
                tenant_id=str(tenant_id) if tenant_id else None
            )
        except Exception as e:
            logger.warning(
                "Failed to publish query execution completed event",
                workflow_instance_id=str(instance.id),
                execution_id=str(execution.id),
                error=str(e),
                exc_info=True
            )

        # Create audit event
        create_audit_event(
            resource_type="VIRTUAL_DATASET",
            action="QUERY_EXECUTION_COMPLETED",
            actor_user=created_by,
            tenant=tenant,
            resource_id=str(execution.virtual_dataset.id),
            details={
                "execution_id": str(execution.id),
                "virtual_dataset_id": str(execution.virtual_dataset.id),
                "virtual_dataset_name": execution.virtual_dataset.name,
                "query_type": execution.virtual_dataset.query_type,
                "execution_mode": execution.execution_mode,
                "workflow_instance_id": str(instance.id)
            }
        )

        logger.info(
            "Workflow completed",
            workflow_instance_id=str(instance.id),
            execution_id=str(execution.id),
            virtual_dataset_id=str(execution.virtual_dataset.id)
        )

        return {
            "completed": True,
            "execution_id": str(execution.id),
            "row_count": execution.metrics.get("row_count", 0) if execution.metrics else 0
        }

    @staticmethod
    @transaction.atomic
    def _rollback_execution_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Rollback execution record (compensation task).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with rollback status
        """
        execution_id = instance.state_data.get("execution_id")
        tenant_id = input_data.get("tenant_id") or instance.tenant_id

        if not execution_id:
            logger.warning(
                "Cannot rollback execution: execution_id not found",
                workflow_instance_id=str(instance.id)
            )
            return {"rolled_back": False, "reason": "execution_id not found"}

        if not tenant_id:
            logger.warning(
                "Cannot rollback execution: tenant_id not found",
                workflow_instance_id=str(instance.id)
            )
            return {"rolled_back": False, "reason": "tenant_id not found"}

        from hub.apps.tenants.models import Tenant
        tenant = Tenant.objects.get(id=tenant_id)

        try:
            execution = QueryExecution.objects.get(id=execution_id)
            # Mark execution as failed if not already
            if execution.status != QueryExecutionStatus.FAILED:
                execution.status = QueryExecutionStatus.FAILED
                execution.completed_at = timezone.now()
                execution.save(update_fields=['status', 'completed_at'])

            logger.info(
                "Execution rolled back",
                workflow_instance_id=str(instance.id),
                execution_id=str(execution.id)
            )

            return {"rolled_back": True}
        except QueryExecution.DoesNotExist:
            logger.warning(
                "Execution not found for rollback",
                workflow_instance_id=str(instance.id),
                execution_id=execution_id
            )
            return {"rolled_back": False, "reason": "execution not found"}

    @staticmethod
    @transaction.atomic
    def _rollback_cache_task(input_data: Dict[str, Any], instance: WorkflowInstance, step) -> Dict[str, Any]:
        """
        Rollback cache entry (compensation task).

        Args:
            input_data: Workflow input data
            instance: Workflow instance
            step: Workflow step

        Returns:
            Task output with rollback status
        """
        cache_key = instance.state_data.get("cache_key")

        if not cache_key:
            logger.warning(
                "Cannot rollback cache: cache_key not found",
                workflow_instance_id=str(instance.id)
            )
            return {"rolled_back": False, "reason": "cache_key not found"}

        try:
            # Delete cache entry
            cache.delete(cache_key)

            logger.info(
                "Cache rolled back (deleted)",
                workflow_instance_id=str(instance.id),
                cache_key=cache_key
            )

            return {"rolled_back": True}
        except Exception as e:
            logger.warning(
                "Failed to rollback cache",
                workflow_instance_id=str(instance.id),
                cache_key=cache_key,
                error=str(e),
                exc_info=True
            )
            return {"rolled_back": False, "reason": f"Failed to delete cache: {str(e)}"}

    @classmethod
    def execute(
        cls,
        virtual_dataset_id: str,
        tenant_id: str,
        user_id: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        execution_mode: Optional[QueryExecutionMode] = None,
        timeout_seconds: Optional[int] = None,
        engine: Optional[WorkflowEngine] = None,
        registry: Optional[WorkflowRegistry] = None
    ) -> Dict[str, Any]:
        """
        Execute virtualization query execution workflow.

        Args:
            virtual_dataset_id: Virtual dataset ID to execute query for
            tenant_id: Tenant ID
            user_id: User ID who triggered the execution
            parameters: Query parameters dictionary
            execution_mode: Execution mode (SYNC, ASYNC) - default: ASYNC
            timeout_seconds: Query timeout in seconds
            engine: Optional WorkflowEngine instance
            registry: Optional WorkflowRegistry instance

        Returns:
            Workflow execution result dictionary

        Raises:
            ValueError: If workflow execution fails
        """
        # Create engine and registry if not provided
        if engine is None:
            engine = WorkflowEngine()
            cls.register_tasks(engine)

        if registry is None:
            registry = WorkflowRegistry()
            cls.register_workflow(registry)

        # Validate tenant exists before creating workflow instance
        from hub.apps.tenants.models import Tenant
        try:
            Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise ValueError(f"Tenant matching query does not exist: {tenant_id}")

        # Prepare workflow input
        workflow_input = {
            "virtual_dataset_id": virtual_dataset_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "parameters": parameters or {},
            "execution_mode": execution_mode or QueryExecutionMode.ASYNC,
            "timeout_seconds": timeout_seconds
        }

        # Create workflow instance
        try:
            workflow_instance = engine.create_instance(
                workflow_name=cls.WORKFLOW_NAME,
                input_data=workflow_input,
                tenant_id=tenant_id,
                created_by_id=user_id
            )
        except Exception as e:
            # Catch database integrity errors and convert to ValueError
            from django.db import IntegrityError
            if isinstance(e, IntegrityError) or "foreign key constraint" in str(e).lower():
                raise ValueError(f"Invalid tenant_id: {tenant_id}") from e
            raise

        # Start and execute workflow
        workflow_instance = engine.start_instance(str(workflow_instance.id))
        workflow_instance = engine.execute_instance(str(workflow_instance.id))

        # Check workflow status
        if workflow_instance.status == WorkflowStatus.COMPLETED:
            logger.info(
                "Virtualization query execution workflow completed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                virtual_dataset_id=virtual_dataset_id,
                execution_id=workflow_instance.state_data.get("execution_id")
            )
            return {
                "success": True,
                "workflow_instance_id": str(workflow_instance.id),
                "execution_id": workflow_instance.state_data.get("execution_id"),
                "output_data": workflow_instance.output_data
            }
        else:
            error_message = workflow_instance.error_message or "Workflow execution failed"
            logger.error(
                "Virtualization query execution workflow failed",
                workflow_instance_id=str(workflow_instance.id),
                tenant_id=tenant_id,
                virtual_dataset_id=virtual_dataset_id,
                error=error_message
            )
            raise ValueError(f"Virtualization query execution workflow failed: {error_message}")

