"""
Workflow Registry Service

Provides REST API for workflow registry operations including:
- Workflow registration
- Workflow discovery
- Dependency tracking
- Workflow validation
"""
import os
import sys
import django
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Setup Django
django.setup()

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Set
import json
import time
import logging

from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.models import WorkflowDefinition
from django.core.exceptions import ValidationError
from asgiref.sync import sync_to_async

# Import shared metrics - adjust path based on project structure
try:
    from services.shared.metrics import get_metrics_response
except ImportError:
    # Fallback if shared module not in path
    import sys
    shared_path = Path(__file__).parent.parent / 'shared'
    if shared_path.exists():
        sys.path.insert(0, str(shared_path.parent))
        from shared.metrics import get_metrics_response
    else:
        # Create a minimal fallback
        def get_metrics_response():
            return {"status": "ok", "service": "workflow-registry-service"}

logger = logging.getLogger(__name__)

app = FastAPI(title="Workflow Registry Service", version="1.0.0")
SERVICE_NAME = "workflow-registry-service"

# Initialize registry
workflow_registry = WorkflowRegistry()

# Build dependency graph on startup
@app.on_event("startup")
async def startup_event():
    """Build dependency graph on service startup."""
    try:
        await sync_to_async(workflow_registry.build_dependency_graph)()
        logger.info("Workflow registry service started successfully")
    except Exception as e:
        logger.error(f"Error building dependency graph on startup: {e}", exc_info=True)


# Request/Response Models
class RegisterWorkflowRequest(BaseModel):
    """Request model for workflow registration"""
    workflow_name: str = Field(..., description="Workflow name")
    dsl_json: Dict[str, Any] = Field(..., description="Workflow DSL JSON")
    version: Optional[str] = Field(None, description="Workflow version (auto-increments if not specified)")
    description: Optional[str] = Field(None, description="Workflow description")
    created_by_id: Optional[str] = Field(None, description="User ID who created the workflow")


class WorkflowDefinitionResponse(BaseModel):
    """Response model for workflow definition"""
    id: str
    name: str
    version: str
    description: Optional[str]
    dsl_json: Dict[str, Any]
    is_active: bool
    dependencies: List[str]
    metadata: Dict[str, Any]
    created_at: str
    updated_at: str

    @classmethod
    def from_model(cls, workflow_def: WorkflowDefinition):
        """Create response from WorkflowDefinition model"""
        return cls(
            id=str(workflow_def.id),
            name=workflow_def.name,
            version=workflow_def.version,
            description=workflow_def.description,
            dsl_json=workflow_def.dsl_json,
            is_active=workflow_def.is_active,
            dependencies=workflow_def.dependencies or [],
            metadata=workflow_def.metadata or {},
            created_at=workflow_def.created_at.isoformat(),
            updated_at=workflow_def.updated_at.isoformat()
        )


class DiscoverWorkflowsResponse(BaseModel):
    """Response model for workflow discovery"""
    workflows: List[WorkflowDefinitionResponse]
    total: int


class ValidateWorkflowResponse(BaseModel):
    """Response model for workflow validation"""
    valid: bool
    errors: List[str]


class DependencyGraphResponse(BaseModel):
    """Response model for dependency graph"""
    graph: Dict[str, List[str]]


# Health Check Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "timestamp": time.time()
    }


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    metrics_data, content_type = get_metrics_response()
    return Response(content=metrics_data, media_type=content_type)


# Workflow Registry Endpoints
@app.post("/workflows", response_model=WorkflowDefinitionResponse, status_code=201)
async def register_workflow(request: RegisterWorkflowRequest):
    """
    Register a new workflow definition.
    
    Validates the workflow DSL, checks dependencies, and creates a new workflow definition.
    Returns 200 if workflow already exists, 201 if created.
    """
    try:
        workflow_def = await sync_to_async(workflow_registry.register_workflow)(
            workflow_name=request.workflow_name,
            dsl_json=request.dsl_json,
            version=request.version,
            description=request.description,
            created_by_id=request.created_by_id
        )
        return WorkflowDefinitionResponse.from_model(workflow_def)
    except ValidationError as e:
        error_str = str(e)
        # If workflow already exists, return existing workflow with 200 status
        if "already exists" in error_str.lower():
            # Determine version to look up
            lookup_version = request.version
            if not lookup_version:
                from hub.apps.orchestration.versioning import WorkflowVersionManager
                latest = await sync_to_async(WorkflowVersionManager.get_latest_version)(
                    request.workflow_name
                )
                if latest:
                    lookup_version = latest.version
                else:
                    lookup_version = "1.0.0"
            
            try:
                existing_workflow = await sync_to_async(WorkflowDefinition.objects.get)(
                    name=request.workflow_name,
                    version=lookup_version
                )
                response_data = WorkflowDefinitionResponse.from_model(existing_workflow)
                return Response(
                    content=response_data.model_dump_json(),
                    media_type="application/json",
                    status_code=200
                )
            except WorkflowDefinition.DoesNotExist:
                # Workflow doesn't exist despite error message - re-raise original error
                pass
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error registering workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/workflows", response_model=DiscoverWorkflowsResponse)
async def discover_workflows(
    workflow_name: Optional[str] = Query(None, description="Filter by workflow name"),
    tags: Optional[str] = Query(None, description="Comma-separated list of tags"),
    is_active: Optional[bool] = Query(None, description="Filter by active status")
):
    """
    Discover workflow definitions.
    
    Supports filtering by workflow name, tags, and active status.
    """
    try:
        tags_list = tags.split(",") if tags else None
        
        workflows = await sync_to_async(workflow_registry.discover_workflows)(
            workflow_name=workflow_name,
            tags=tags_list,
            is_active=is_active
        )
        
        # Convert workflows to response models (this is CPU-bound, no DB access)
        workflow_responses = [WorkflowDefinitionResponse.from_model(wf) for wf in workflows]
        return DiscoverWorkflowsResponse(
            workflows=workflow_responses,
            total=len(workflows)
        )
    except Exception as e:
        logger.error(f"Error discovering workflows: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/workflows/{workflow_name}", response_model=WorkflowDefinitionResponse)
async def get_workflow(
    workflow_name: str,
    version: Optional[str] = Query(None, description="Workflow version (uses active version if not specified)")
):
    """
    Get a workflow definition by name and optional version.
    """
    try:
        workflow_def = await sync_to_async(workflow_registry.get_workflow)(workflow_name, version=version)
        
        if not workflow_def:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow not found: {workflow_name}" + (f" (version: {version})" if version else "")
            )
        
        return WorkflowDefinitionResponse.from_model(workflow_def)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/workflows/{workflow_name}/dependencies", response_model=Dict[str, List[str]])
async def get_workflow_dependencies(workflow_name: str):
    """
    Get dependencies for a workflow.
    
    Returns a dictionary with 'dependencies' key containing list of workflow names.
    """
    try:
        dependencies = await sync_to_async(workflow_registry.get_dependencies)(workflow_name)
        return {"dependencies": list(dependencies)}
    except Exception as e:
        logger.error(f"Error getting workflow dependencies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/workflows/{workflow_name}/dependents", response_model=Dict[str, List[str]])
async def get_workflow_dependents(workflow_name: str):
    """
    Get workflows that depend on this workflow.
    
    Returns a dictionary with 'dependents' key containing list of workflow names.
    """
    try:
        dependents = await sync_to_async(workflow_registry.get_dependents)(workflow_name)
        return {"dependents": list(dependents)}
    except Exception as e:
        logger.error(f"Error getting workflow dependents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/workflows/{workflow_name}/validate", response_model=ValidateWorkflowResponse)
async def validate_workflow(
    workflow_name: str,
    version: Optional[str] = Query(None, description="Workflow version (uses active version if not specified)")
):
    """
    Validate a workflow definition.
    
    Checks DSL structure, dependencies, and circular dependencies.
    """
    try:
        result = await sync_to_async(workflow_registry.validate_workflow)(workflow_name, version=version)
        return ValidateWorkflowResponse(**result)
    except Exception as e:
        logger.error(f"Error validating workflow: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/dependency-graph", response_model=DependencyGraphResponse)
async def get_dependency_graph():
    """
    Get complete dependency graph.
    
    Returns a dictionary mapping workflow names to their dependencies.
    """
    try:
        graph = await sync_to_async(workflow_registry.get_dependency_graph)()
        # Convert sets to lists for JSON serialization
        graph_dict = {name: list(deps) for name, deps in graph.items()}
        return DependencyGraphResponse(graph=graph_dict)
    except Exception as e:
        logger.error(f"Error getting dependency graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/dependency-graph/build")
async def build_dependency_graph():
    """
    Rebuild dependency graph from all registered workflows.
    
    This endpoint should be called after bulk workflow registration or when
    the dependency graph needs to be refreshed.
    """
    try:
        await sync_to_async(workflow_registry.build_dependency_graph)()
        return {"status": "success", "message": "Dependency graph rebuilt successfully"}
    except Exception as e:
        logger.error(f"Error building dependency graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("WORKFLOW_REGISTRY_PORT", "8089"))
    uvicorn.run(app, host="0.0.0.0", port=port)

