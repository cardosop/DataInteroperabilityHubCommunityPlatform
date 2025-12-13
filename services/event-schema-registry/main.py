"""
Event Schema Registry Service

Provides REST API for event schema operations including:
- Event schema retrieval
- Event type discovery
- Event data validation
- Schema version management
"""
import os
import sys
import django
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Add services directory to path for shared modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

# Setup Django
django.setup()

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import json
import time
import logging

from hub.apps.core.events.schema import (
    BASE_EVENT_SCHEMA,
    EventSchema,
    get_event_schema as get_event_schema_merged
)
from hub.apps.core.events.event_types import (
    EVENT_TYPE_SCHEMAS,
    get_all_event_types,
    get_event_schema,
    validate_event_data,
    CURRENT_EVENT_VERSION
)
from hub.apps.core.events.versioning import get_version_manager
from shared.metrics import get_metrics_response

logger = logging.getLogger(__name__)

app = FastAPI(title="Event Schema Registry Service", version="1.0.0")
SERVICE_NAME = "event-schema-registry-service"

# Initialize version manager
version_manager = get_version_manager()


# Request/Response Models
class ValidateEventRequest(BaseModel):
    """Request model for event validation"""
    event_type: str = Field(..., description="Event type (e.g., 'contract.created')")
    data: Dict[str, Any] = Field(..., description="Event data payload to validate")
    event_version: Optional[str] = Field(None, description="Event schema version (uses current if not specified)")


class ValidateEventResponse(BaseModel):
    """Response model for event validation"""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class EventTypeInfo(BaseModel):
    """Information about an event type"""
    event_type: str
    schema: Dict[str, Any]
    version: str
    description: Optional[str] = None


class EventTypesListResponse(BaseModel):
    """Response model for event types list"""
    event_types: List[str]
    total: int
    version: str


class SchemaResponse(BaseModel):
    """Response model for schema retrieval"""
    event_type: str
    schema: Dict[str, Any]
    version: str
    base_schema: Dict[str, Any]


# Health Check Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "timestamp": time.time(),
        "version": CURRENT_EVENT_VERSION,
        "total_event_types": len(EVENT_TYPE_SCHEMAS)
    }


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    metrics_data, content_type = get_metrics_response()
    return Response(content=metrics_data, media_type=content_type)


# Event Schema Registry Endpoints
@app.get("/event-types", response_model=EventTypesListResponse)
async def list_event_types(
    category: Optional[str] = Query(None, description="Filter by category (e.g., 'contract', 'asset')")
):
    """
    List all registered event types.
    
    Supports filtering by category (prefix matching).
    """
    try:
        all_types = get_all_event_types()
        
        if category:
            # Filter by category prefix
            filtered_types = [
                event_type for event_type in all_types
                if event_type.startswith(f"{category}.")
            ]
        else:
            filtered_types = all_types
        
        return EventTypesListResponse(
            event_types=sorted(filtered_types),
            total=len(filtered_types),
            version=CURRENT_EVENT_VERSION
        )
    except Exception as e:
        logger.error(f"Error listing event types: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/event-types/{event_type}", response_model=SchemaResponse)
async def get_event_type_schema(event_type: str):
    """
    Get schema for a specific event type.
    
    Returns the complete schema including base schema merged with event type-specific schema.
    """
    try:
        # Check if event type exists first
        type_schema = get_event_schema(event_type)
        
        if not type_schema:
            raise HTTPException(
                status_code=404,
                detail=f"Event type not found: {event_type}"
            )
        
        # Get merged schema (base + event type specific)
        merged_schema = get_event_schema_merged(event_type)
        
        return SchemaResponse(
            event_type=event_type,
            schema=merged_schema,
            version=CURRENT_EVENT_VERSION,
            base_schema=BASE_EVENT_SCHEMA
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event type schema: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/base-schema", response_model=Dict[str, Any])
async def get_base_schema():
    """
    Get base event schema.
    
    Returns the base schema that all events must conform to.
    """
    return BASE_EVENT_SCHEMA


@app.post("/validate", response_model=ValidateEventResponse)
async def validate_event(request: ValidateEventRequest):
    """
    Validate event data against event type schema.
    
    Validates the event data payload against the schema for the specified event type.
    """
    try:
        # Validate event data against schema
        is_valid, error = validate_event_data(request.event_type, request.data)
        
        if is_valid:
            return ValidateEventResponse(
                valid=True,
                errors=[],
                warnings=[]
            )
        else:
            return ValidateEventResponse(
                valid=False,
                errors=[error] if error else [],
                warnings=[]
            )
    except Exception as e:
        logger.error(f"Error validating event: {e}", exc_info=True)
        return ValidateEventResponse(
            valid=False,
            errors=[f"Validation error: {str(e)}"],
            warnings=[]
        )


@app.post("/validate-full", response_model=ValidateEventResponse)
async def validate_full_event(event: Dict[str, Any]):
    """
    Validate a complete event (including base fields).
    
    Validates the entire event structure including event_id, timestamp, source, etc.
    """
    try:
        # Validate against base schema
        is_valid, error = EventSchema.validate_event(event)
        
        if not is_valid:
            return ValidateEventResponse(
                valid=False,
                errors=[error] if error else [],
                warnings=[]
            )
        
        # Validate event data against event type schema
        event_type = event.get("event_type")
        if not event_type:
            return ValidateEventResponse(
                valid=False,
                errors=["Missing event_type field"],
                warnings=[]
            )
        
        data = event.get("data", {})
        is_data_valid, data_error = validate_event_data(event_type, data)
        
        if not is_data_valid:
            return ValidateEventResponse(
                valid=False,
                errors=[data_error] if data_error else [],
                warnings=[]
            )
        
        return ValidateEventResponse(
            valid=True,
            errors=[],
            warnings=[]
        )
    except Exception as e:
        logger.error(f"Error validating full event: {e}", exc_info=True)
        return ValidateEventResponse(
            valid=False,
            errors=[f"Validation error: {str(e)}"],
            warnings=[]
        )


@app.get("/categories")
async def get_event_categories():
    """
    Get list of event categories.
    
    Returns unique categories (prefixes before first dot) from all event types.
    """
    try:
        all_types = get_all_event_types()
        categories = set()
        
        for event_type in all_types:
            # Extract category (part before first dot)
            parts = event_type.split('.')
            if len(parts) > 0:
                categories.add(parts[0])
        
        return {
            "categories": sorted(categories),
            "total": len(categories)
        }
    except Exception as e:
        logger.error(f"Error getting event categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/categories/{category}/event-types", response_model=EventTypesListResponse)
async def get_category_event_types(category: str):
    """
    Get all event types for a specific category.
    
    Returns all event types that start with the category prefix.
    """
    try:
        all_types = get_all_event_types()
        category_types = [
            event_type for event_type in all_types
            if event_type.startswith(f"{category}.")
        ]
        
        if not category_types:
            raise HTTPException(
                status_code=404,
                detail=f"Category not found: {category}"
            )
        
        return EventTypesListResponse(
            event_types=sorted(category_types),
            total=len(category_types),
            version=CURRENT_EVENT_VERSION
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting category event types: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/version")
async def get_schema_version():
    """
    Get current event schema version.
    
    Returns the current schema version and version information.
    """
    return {
        "version": CURRENT_EVENT_VERSION,
        "total_event_types": len(EVENT_TYPE_SCHEMAS),
        "total_categories": len(set(event_type.split('.')[0] for event_type in EVENT_TYPE_SCHEMAS.keys()))
    }


@app.get("/version/{event_type}")
async def get_event_type_version(event_type: str):
    """
    Get schema version for a specific event type.
    
    Returns version information for the specified event type.
    """
    try:
        # Check if event type exists using event_types.get_event_schema
        type_schema = get_event_schema(event_type)
        
        if not type_schema:
            raise HTTPException(
                status_code=404,
                detail=f"Event type not found: {event_type}"
            )
        
        return {
            "event_type": event_type,
            "version": CURRENT_EVENT_VERSION,
            "has_schema": True
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event type version: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("EVENT_SCHEMA_REGISTRY_PORT", "8091"))
    uvicorn.run(app, host="0.0.0.0", port=port)

