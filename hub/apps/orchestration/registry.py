"""
Workflow Registry and Discovery

Manages workflow registration, discovery, dependency tracking, and validation.
"""
import logging
from typing import Dict, Any, Optional, List, Set
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import WorkflowDefinition
from .dsl_parser import WorkflowDSLParser
from .versioning import WorkflowVersionManager

logger = logging.getLogger(__name__)


class WorkflowRegistry:
    """
    Workflow registry.
    
    Manages workflow definitions, discovery, dependency graphs, and validation.
    """
    
    def __init__(self):
        self.dsl_parser = WorkflowDSLParser()
        self.version_manager = WorkflowVersionManager()
        self._dependency_graph: Dict[str, Set[str]] = {}
        self._reverse_dependency_graph: Dict[str, Set[str]] = {}
    
    @transaction.atomic
    def register_workflow(
        self,
        workflow_name: str,
        dsl_json: Dict[str, Any],
        version: Optional[str] = None,
        description: Optional[str] = None,
        created_by_id: Optional[str] = None
    ) -> WorkflowDefinition:
        """
        Register a new workflow definition.
        
        Args:
            workflow_name: Workflow name
            dsl_json: Workflow DSL JSON
            version: Optional version (auto-increments if not specified)
            description: Optional description
            created_by_id: Optional user ID
            
        Returns:
            Registered WorkflowDefinition
        """
        # Validate workflow DSL
        self.dsl_parser.parse_json(dsl_json)
        
        # Validate dependencies
        dependencies = dsl_json.get("dependencies", [])
        self._validate_dependencies(workflow_name, dependencies)
        
        # Create workflow definition
        workflow_def = self.version_manager.create_version(
            workflow_name=workflow_name,
            dsl_json=dsl_json,
            version=version,
            description=description,
            created_by_id=created_by_id
        )
        
        # Update dependency graph
        self._update_dependency_graph(workflow_name, dependencies)
        
        logger.info(f"Registered workflow: {workflow_name} v{workflow_def.version}")
        return workflow_def
    
    def discover_workflows(
        self,
        workflow_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_active: Optional[bool] = True
    ) -> List[WorkflowDefinition]:
        """
        Discover workflow definitions.
        
        Args:
            workflow_name: Optional workflow name filter
            tags: Optional tags filter
            is_active: Optional active status filter
            
        Returns:
            List of WorkflowDefinition instances
        """
        queryset = WorkflowDefinition.objects.all()
        
        if workflow_name:
            queryset = queryset.filter(name=workflow_name)
        
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active)
        
        if tags:
            # Filter by tags in metadata
            for tag in tags:
                queryset = queryset.filter(metadata__tags__contains=[tag])
        
        return list(queryset.order_by('name', '-version'))
    
    def get_workflow(
        self,
        workflow_name: str,
        version: Optional[str] = None
    ) -> Optional[WorkflowDefinition]:
        """
        Get a workflow definition.
        
        Args:
            workflow_name: Workflow name
            version: Optional version (uses active version if not specified)
            
        Returns:
            WorkflowDefinition or None if not found
        """
        return self.version_manager.get_workflow_definition(
            workflow_name,
            version=version
        )
    
    def get_dependencies(self, workflow_name: str) -> Set[str]:
        """
        Get workflow dependencies.
        
        Args:
            workflow_name: Workflow name
            
        Returns:
            Set of dependency workflow names
        """
        return self._dependency_graph.get(workflow_name, set())
    
    def get_dependents(self, workflow_name: str) -> Set[str]:
        """
        Get workflows that depend on this workflow.
        
        Args:
            workflow_name: Workflow name
            
        Returns:
            Set of dependent workflow names
        """
        return self._reverse_dependency_graph.get(workflow_name, set())
    
    def get_dependency_graph(self) -> Dict[str, Set[str]]:
        """
        Get complete dependency graph.
        
        Returns:
            Dictionary mapping workflow names to their dependencies
        """
        return self._dependency_graph.copy()
    
    def validate_workflow(self, workflow_name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate a workflow definition.
        
        Args:
            workflow_name: Workflow name
            version: Optional version (uses active version if not specified)
            
        Returns:
            Validation result dictionary with 'valid' boolean and 'errors' list
        """
        workflow_def = self.get_workflow(workflow_name, version=version)
        
        if not workflow_def:
            return {
                "valid": False,
                "errors": [f"Workflow not found: {workflow_name}"]
            }
        
        errors = []
        
        # Validate DSL structure
        try:
            self.dsl_parser.parse_json(workflow_def.dsl_json)
        except ValidationError as e:
            errors.append(f"DSL validation error: {str(e)}")
        
        # Validate dependencies exist
        dependencies = workflow_def.dependencies
        for dep_name in dependencies:
            dep_workflow = self.get_workflow(dep_name)
            if not dep_workflow:
                errors.append(f"Dependency not found: {dep_name}")
        
        # Check for circular dependencies
        if self._has_circular_dependency(workflow_name):
            errors.append(f"Circular dependency detected for workflow: {workflow_name}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _validate_dependencies(self, workflow_name: str, dependencies: List[str]) -> None:
        """
        Validate workflow dependencies exist.
        
        Args:
            workflow_name: Workflow name
            dependencies: List of dependency workflow names
            
        Raises:
            ValidationError: If dependencies are invalid
        """
        for dep_name in dependencies:
            # Check if dependency workflow exists
            dep_workflow = self.get_workflow(dep_name)
            if not dep_workflow:
                raise ValidationError(
                    f"Workflow '{workflow_name}' depends on '{dep_name}', but '{dep_name}' is not registered"
                )
    
    def _update_dependency_graph(self, workflow_name: str, dependencies: List[str]) -> None:
        """
        Update dependency graph.
        
        Args:
            workflow_name: Workflow name
            dependencies: List of dependency workflow names
        """
        # Update forward dependency graph
        self._dependency_graph[workflow_name] = set(dependencies)
        
        # Update reverse dependency graph
        for dep_name in dependencies:
            if dep_name not in self._reverse_dependency_graph:
                self._reverse_dependency_graph[dep_name] = set()
            self._reverse_dependency_graph[dep_name].add(workflow_name)
    
    def _has_circular_dependency(self, workflow_name: str) -> bool:
        """
        Check if workflow has circular dependencies.
        
        Args:
            workflow_name: Workflow name
            
        Returns:
            True if circular dependency exists, False otherwise
        """
        visited = set()
        rec_stack = set()
        
        def has_cycle(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            dependencies = self._dependency_graph.get(node, set())
            for dep in dependencies:
                if dep not in visited:
                    if has_cycle(dep):
                        return True
                elif dep in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        return has_cycle(workflow_name)
    
    def build_dependency_graph(self) -> None:
        """
        Build dependency graph from all registered workflows.
        
        This should be called on startup or after bulk workflow registration.
        """
        workflows = WorkflowDefinition.objects.filter(is_active=True)
        
        self._dependency_graph.clear()
        self._reverse_dependency_graph.clear()
        
        for workflow_def in workflows:
            dependencies = workflow_def.dependencies or []
            self._update_dependency_graph(workflow_def.name, dependencies)
        
        logger.info(f"Built dependency graph for {len(workflows)} workflows")

