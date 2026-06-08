"""
285.11.1.12 — Admin registration for PipelineDependency + PipelineRunDependency.
These models may not exist yet (planned feature). Registered conditionally.
"""
from django.contrib import admin

_models = {}
for _name in ("PipelineDependency", "PipelineRunDependency",
              "PipelineType", "DependencyType", "DependencySource"):
    try:
        from hub.apps.orchestration import models as _m
        _models[_name] = getattr(_m, _name)
    except (ImportError, AttributeError):
        _models[_name] = None

if _models["PipelineDependency"] is not None:
    @admin.register(_models["PipelineDependency"])
    class PipelineDependencyAdmin(admin.ModelAdmin):
        list_display = ("id", "tenant", "pipeline_id", "created_by")
        list_filter = ("pipeline_type", "dependency_type")
        search_fields = ("pipeline_id",)

if _models["PipelineRunDependency"] is not None:
    @admin.register(_models["PipelineRunDependency"])
    class PipelineRunDependencyAdmin(admin.ModelAdmin):
        list_display = ("id", "tenant", "upstream_run_type", "upstream_run_id",
                        "downstream_run_type", "upstream_status", "created_at")
        list_filter = ("upstream_status", "upstream_run_type", "downstream_run_type")
        search_fields = ("upstream_run_id", "downstream_run_id")
