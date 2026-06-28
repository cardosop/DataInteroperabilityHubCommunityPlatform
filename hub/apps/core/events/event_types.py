"""
Event Type Definitions

Comprehensive definitions for all system events with JSON schemas.
"""

from typing import Any

# Event schema version
CURRENT_EVENT_VERSION = "1.0.0"

# Event type-specific schemas (extend BASE_EVENT_SCHEMA)
EVENT_TYPE_SCHEMAS: dict[str, dict[str, Any]] = {
    # Contract Events
    "contract.created": {
        "data": {
            "type": "object",
            "required": ["contract_id"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": ["string", "null"], "format": "uuid"},
                "status": {"type": "string"},
                "original_format": {"type": "string"},
                "original_spec_version": {"type": "string"},
            },
        }
    },
    "contract.updated": {
        "data": {
            "type": "object",
            "required": ["contract_id"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
                "previous_status": {"type": "string"},
                "new_status": {"type": "string"},
            },
        }
    },
    "contract.deleted": {
        "data": {
            "type": "object",
            "required": ["contract_id"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "deleted_at": {"type": "string", "format": "date-time"},
                "reason": {"type": "string"},
            },
        }
    },
    "contract.validated": {
        "data": {
            "type": "object",
            "required": ["contract_id", "validation_result"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "validation_result": {"type": "boolean"},
                "validation_errors": {"type": "array", "items": {"type": "string"}},
                "validation_warnings": {"type": "array", "items": {"type": "string"}},
            },
        }
    },
    "contract.normalized": {
        "data": {
            "type": "object",
            "required": ["contract_id", "normalization_status"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "normalization_status": {"type": "string"},
                "normalization_errors": {"type": ["array", "null"], "items": {"type": "string"}},
            },
        }
    },
    # Normalization Events
    "normalization.started": {
        "data": {
            "type": "object",
            "required": ["contract_id", "normalization_type"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "normalization_type": {"type": "string"},
                "spec_version": {"type": ["string", "null"]},
                "source_format": {"type": ["string", "null"]},
            },
        }
    },
    "normalization.completed": {
        "data": {
            "type": "object",
            "required": ["contract_id", "normalization_status"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "normalization_status": {"type": "string"},
                "normalization_errors": {"type": ["array", "null"], "items": {"type": "string"}},
                "normalization_warnings": {"type": ["array", "null"], "items": {"type": "string"}},
                "duration_ms": {"type": ["integer", "null"]},
                "spec_version": {"type": ["string", "null"]},
            },
        }
    },
    "normalization.failed": {
        "data": {
            "type": "object",
            "required": ["contract_id", "error_message"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "error_message": {"type": "string"},
                "error_details": {"type": ["object", "null"]},
                "normalization_errors": {"type": ["array", "null"], "items": {"type": "string"}},
                "retry_count": {"type": ["integer", "null"]},
                "spec_version": {"type": ["string", "null"]},
            },
        }
    },
    # Asset Events
    "asset.created": {
        "data": {
            "type": "object",
            "required": ["asset_id"],
            "properties": {
                "asset_id": {"type": "string", "format": "uuid"},
                "name": {"type": "string"},
                "domain": {"type": "string"},
                "status": {"type": "string"},
                "contract_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    "asset.updated": {
        "data": {
            "type": "object",
            "required": ["asset_id"],
            "properties": {
                "asset_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
                "previous_status": {"type": "string"},
                "new_status": {"type": "string"},
            },
        }
    },
    "asset.activated": {
        "data": {
            "type": "object",
            "required": ["asset_id"],
            "properties": {
                "asset_id": {"type": "string", "format": "uuid"},
                "activation_reason": {"type": "string"},
                "dq_status": {"type": "string"},
                "compliance_status": {"type": "string"},
            },
        }
    },
    "asset.published": {
        "data": {
            "type": "object",
            "required": ["asset_id", "marketplace_listing_id"],
            "properties": {
                "asset_id": {"type": "string", "format": "uuid"},
                "marketplace_listing_id": {"type": "string", "format": "uuid"},
                "pricing_model": {"type": "string"},
                "license_type": {"type": "string"},
            },
        }
    },
    "asset.retired": {
        "data": {
            "type": "object",
            "required": ["asset_id"],
            "properties": {
                "asset_id": {"type": "string", "format": "uuid"},
                "retirement_reason": {"type": "string"},
                "retired_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    # Dataset Events
    "dataset.created": {
        "data": {
            "type": "object",
            "required": ["dataset_id"],
            "properties": {
                "dataset_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": ["string", "null"], "format": "uuid"},
                "file_id": {"type": "string", "format": "uuid"},
                "format": {"type": "string"},
                "schema_inferred": {"type": "boolean"},
            },
        }
    },
    "dataset.updated": {
        "data": {
            "type": "object",
            "required": ["dataset_id"],
            "properties": {
                "dataset_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
                "file_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    "dataset.deleted": {
        "data": {
            "type": "object",
            "required": ["dataset_id"],
            "properties": {
                "dataset_id": {"type": "string", "format": "uuid"},
                "deleted_at": {"type": "string", "format": "date-time"},
                "reason": {"type": "string"},
            },
        }
    },
    "dataset.uploaded": {
        "data": {
            "type": "object",
            "required": ["dataset_id", "file_id"],
            "properties": {
                "dataset_id": {"type": "string", "format": "uuid"},
                "file_id": {"type": "string", "format": "uuid"},
                "file_size": {"type": "integer"},
                "file_format": {"type": "string"},
                "upload_duration_ms": {"type": "integer"},
            },
        }
    },
    # File Events
    "file.created": {
        "data": {
            "type": "object",
            "required": ["file_id"],
            "properties": {
                "file_id": {"type": "string", "format": "uuid"},
                "name": {"type": ["string", "null"]},
                "content_type": {"type": ["string", "null"]},
                "size": {"type": ["integer", "null"]},
                "status": {"type": ["string", "null"]},
                "content_sha256": {"type": ["string", "null"]},
            },
        }
    },
    "file.updated": {
        "data": {
            "type": "object",
            "required": ["file_id"],
            "properties": {
                "file_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
                "previous_status": {"type": ["string", "null"]},
                "new_status": {"type": ["string", "null"]},
            },
        }
    },
    "file.deleted": {
        "data": {
            "type": "object",
            "required": ["file_id"],
            "properties": {
                "file_id": {"type": "string", "format": "uuid"},
                "deleted_at": {"type": "string", "format": "date-time"},
                "reason": {"type": ["string", "null"]},
            },
        }
    },
    "file.uploaded": {
        "data": {
            "type": "object",
            "required": ["file_id"],
            "properties": {
                "file_id": {"type": "string", "format": "uuid"},
                "file_size": {"type": ["integer", "null"]},
                "content_type": {"type": ["string", "null"]},
                "upload_duration_ms": {"type": ["integer", "null"]},
                "content_sha256": {"type": ["string", "null"]},
            },
        }
    },
    "file.downloaded": {
        "data": {
            "type": "object",
            "required": ["file_id"],
            "properties": {
                "file_id": {"type": "string", "format": "uuid"},
                "download_duration_ms": {"type": ["integer", "null"]},
                "download_size": {"type": ["integer", "null"]},
            },
        }
    },
    # Phase 260.7.G — file.purged (hard-delete after grace window or GDPR)
    "file.purged": {
        "data": {
            "type": "object",
            "required": ["file_id"],
            "properties": {
                "file_id": {"type": "string", "format": "uuid"},
                "purged_at": {"type": "string", "format": "date-time"},
                "name": {"type": ["string", "null"]},
                "size": {"type": ["integer", "null"]},
                "content_sha256": {"type": ["string", "null"]},
            },
        }
    },
    # Lineage Events
    "lineage.updated": {
        "data": {
            "type": "object",
            "required": ["contract_id"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "model_name": {"type": ["string", "null"]},
                "field_name": {"type": ["string", "null"]},
                "lineage_type": {"type": ["string", "null"]},  # "contract", "model", "field"
                "changes": {"type": ["object", "null"]},
                "relationship_count": {"type": ["integer", "null"]},
            },
        }
    },
    "lineage.relationship_added": {
        "data": {
            "type": "object",
            "required": ["contract_id", "source_reference", "target_reference"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "source_reference": {"type": "string"},  # namespace/name/model/field format
                "target_reference": {"type": "string"},  # namespace/name/model/field format
                "relationship_type": {
                    "type": ["string", "null"]
                },  # "depends_on", "derived_from", etc.
                "model_name": {"type": ["string", "null"]},
                "field_name": {"type": ["string", "null"]},
            },
        }
    },
    "lineage.relationship_removed": {
        "data": {
            "type": "object",
            "required": ["contract_id", "source_reference", "target_reference"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "source_reference": {"type": "string"},  # namespace/name/model/field format
                "target_reference": {"type": "string"},  # namespace/name/model/field format
                "relationship_type": {
                    "type": ["string", "null"]
                },  # "depends_on", "derived_from", etc.
                "model_name": {"type": ["string", "null"]},
                "field_name": {"type": ["string", "null"]},
                "reason": {"type": ["string", "null"]},
            },
        }
    },
    # Ingestion Events
    "ingestion.started": {
        "data": {
            "type": "object",
            "required": ["ingestion_id", "source_type"],
            "properties": {
                "ingestion_id": {"type": "string", "format": "uuid"},
                "source_type": {"type": "string"},
                "source_config": {"type": "object"},
                "scheduled_ingestion_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    "ingestion.completed": {
        "data": {
            "type": "object",
            "required": ["ingestion_id", "files_processed"],
            "properties": {
                "ingestion_id": {"type": "string", "format": "uuid"},
                "files_processed": {"type": "integer"},
                "files_succeeded": {"type": "integer"},
                "files_failed": {"type": "integer"},
                "duration_ms": {"type": ["integer", "null"]},
                "datasets_created": {"type": "integer"},
            },
        }
    },
    "ingestion.failed": {
        "data": {
            "type": "object",
            "required": ["ingestion_id", "error_message"],
            "properties": {
                "ingestion_id": {"type": "string", "format": "uuid"},
                "error_message": {"type": "string"},
                "error_details": {"type": "object"},
                "retry_count": {"type": "integer"},
            },
        }
    },
    "ingestion.file_processed": {
        "data": {
            "type": "object",
            "required": ["ingestion_id", "file_id", "status"],
            "properties": {
                "ingestion_id": {"type": "string", "format": "uuid"},
                "file_id": {"type": "string", "format": "uuid"},
                "status": {"type": "string"},
                "dataset_id": {"type": ["string", "null"], "format": "uuid"},
                "error_message": {"type": ["string", "null"]},
            },
        }
    },
    # Quality Events
    "quality.check.started": {
        "data": {
            "type": "object",
            "required": ["quality_check_id", "target_type", "target_id"],
            "properties": {
                "quality_check_id": {"type": "string", "format": "uuid"},
                "target_type": {"type": "string"},
                "target_id": {"type": "string", "format": "uuid"},
                "rules_count": {"type": "integer"},
            },
        }
    },
    "quality.check.completed": {
        "data": {
            "type": "object",
            "required": ["quality_check_id", "overall_score"],
            "properties": {
                "quality_check_id": {"type": "string", "format": "uuid"},
                "overall_score": {"type": "number"},
                "rules_passed": {"type": "integer"},
                "rules_failed": {"type": "integer"},
                "duration_ms": {"type": "integer"},
            },
        }
    },
    "quality.check.failed": {
        "data": {
            "type": "object",
            "required": ["quality_check_id", "error_message"],
            "properties": {
                "quality_check_id": {"type": "string", "format": "uuid"},
                "error_message": {"type": "string"},
                "error_details": {"type": "object"},
            },
        }
    },
    "quality.anomaly.detected": {
        "data": {
            "type": "object",
            "required": ["quality_check_id", "anomaly_type"],
            "properties": {
                "quality_check_id": {"type": "string", "format": "uuid"},
                "anomaly_type": {"type": "string"},
                "anomaly_details": {"type": "object"},
                "severity": {"type": "string"},
            },
        }
    },
    # Compliance Events
    "compliance.check.started": {
        "data": {
            "type": "object",
            "required": ["compliance_check_id", "target_type", "target_id"],
            "properties": {
                "compliance_check_id": {"type": "string", "format": "uuid"},
                "target_type": {"type": "string"},
                "target_id": {"type": "string", "format": "uuid"},
                "compliance_frameworks": {"type": "array", "items": {"type": "string"}},
            },
        }
    },
    "compliance.check.completed": {
        "data": {
            "type": "object",
            "required": ["compliance_check_id", "compliance_status"],
            "properties": {
                "compliance_check_id": {"type": "string", "format": "uuid"},
                "compliance_status": {"type": "string"},
                "frameworks_passed": {"type": "array", "items": {"type": "string"}},
                "frameworks_failed": {"type": "array", "items": {"type": "string"}},
                "duration_ms": {"type": "integer"},
            },
        }
    },
    "compliance.check.failed": {
        "data": {
            "type": "object",
            "required": ["compliance_check_id", "error_message"],
            "properties": {
                "compliance_check_id": {"type": "string", "format": "uuid"},
                "error_message": {"type": "string"},
                "error_details": {"type": "object"},
            },
        }
    },
    "compliance.report.generated": {
        "data": {
            "type": "object",
            "required": ["report_id", "report_type"],
            "properties": {
                "report_id": {"type": "string", "format": "uuid"},
                "report_type": {"type": "string"},
                "compliance_framework": {"type": "string"},
                "report_format": {"type": "string"},
                "generated_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    # Version Events
    "version.created": {
        "data": {
            "type": "object",
            "required": ["version_id", "resource_type", "resource_id"],
            "properties": {
                "version_id": {"type": "string", "format": "uuid"},
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string", "format": "uuid"},
                "version_number": {"type": ["string", "null"]},
                "version_type": {"type": ["string", "null"]},
                "semantic_version": {"type": ["string", "null"]},
                "parent_version_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    "version.updated": {
        "data": {
            "type": "object",
            "required": ["version_id"],
            "properties": {
                "version_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
                "resource_type": {"type": ["string", "null"]},
                "resource_id": {"type": ["string", "null"], "format": "uuid"},
                "previous_version": {"type": ["string", "null"]},
                "new_version": {"type": ["string", "null"]},
            },
        }
    },
    "version.rolled_back": {
        "data": {
            "type": "object",
            "required": ["version_id", "target_version"],
            "properties": {
                "version_id": {"type": "string", "format": "uuid"},
                "target_version": {"type": "string"},
                "rollback_reason": {"type": "string"},
            },
        }
    },
    "version.deleted": {
        "data": {
            "type": "object",
            "required": ["version_id", "resource_type", "resource_id"],
            "properties": {
                "version_id": {"type": "string", "format": "uuid"},
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string", "format": "uuid"},
                "deleted_at": {"type": "string", "format": "date-time"},
                "reason": {"type": ["string", "null"]},
            },
        }
    },
    "version.promoted": {
        "data": {
            "type": "object",
            "required": [
                "version_id",
                "resource_type",
                "resource_id",
                "promoted_from",
                "promoted_to",
            ],
            "properties": {
                "version_id": {"type": "string", "format": "uuid"},
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string", "format": "uuid"},
                "promoted_from": {"type": "string"},
                "promoted_to": {"type": "string"},
                "promotion_reason": {"type": ["string", "null"]},
            },
        }
    },
    # Access Events
    "access.requested": {
        "data": {
            "type": "object",
            "required": ["access_request_id", "resource_type", "resource_id"],
            "properties": {
                "access_request_id": {"type": "string", "format": "uuid"},
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string", "format": "uuid"},
                "requester_id": {"type": "string", "format": "uuid"},
                "request_reason": {"type": "string"},
            },
        }
    },
    "access.granted": {
        "data": {
            "type": "object",
            "required": ["access_request_id", "resource_type", "resource_id"],
            "properties": {
                "access_request_id": {"type": "string", "format": "uuid"},
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string", "format": "uuid"},
                "granted_by": {"type": "string", "format": "uuid"},
                "granted_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "access.revoked": {
        "data": {
            "type": "object",
            "required": ["access_request_id", "resource_type", "resource_id"],
            "properties": {
                "access_request_id": {"type": "string", "format": "uuid"},
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string", "format": "uuid"},
                "revoked_by": {"type": "string", "format": "uuid"},
                "revoked_at": {"type": "string", "format": "date-time"},
                "revocation_reason": {"type": "string"},
            },
        }
    },
    "access.certified": {
        "data": {
            "type": "object",
            "required": ["access_request_id", "certification_type"],
            "properties": {
                "access_request_id": {"type": "string", "format": "uuid"},
                "certification_type": {"type": "string"},
                "certified_by": {"type": "string", "format": "uuid"},
                "certified_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    # Marketplace Events
    "marketplace.listing.published": {
        "data": {
            "type": "object",
            "required": ["listing_id", "asset_id"],
            "properties": {
                "listing_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": "string", "format": "uuid"},
                "pricing_model": {"type": "string"},
                "published_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "marketplace.listing.unpublished": {
        "data": {
            "type": "object",
            "required": ["listing_id"],
            "properties": {
                "listing_id": {"type": "string", "format": "uuid"},
                "unpublished_at": {"type": "string", "format": "date-time"},
                "reason": {"type": "string"},
            },
        }
    },
    "marketplace.order.created": {
        "data": {
            "type": "object",
            "required": ["order_id", "listing_id", "buyer_id"],
            "properties": {
                "order_id": {"type": "string", "format": "uuid"},
                "listing_id": {"type": "string", "format": "uuid"},
                "buyer_id": {"type": "string", "format": "uuid"},
                "order_amount": {"type": "number"},
                "currency": {"type": "string"},
            },
        }
    },
    "marketplace.order.approved": {
        "data": {
            "type": "object",
            "required": ["order_id", "approved_by"],
            "properties": {
                "order_id": {"type": "string", "format": "uuid"},
                "approved_by": {"type": "string", "format": "uuid"},
                "approved_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "marketplace.order.rejected": {
        "data": {
            "type": "object",
            "required": ["order_id", "rejected_by", "rejection_reason"],
            "properties": {
                "order_id": {"type": "string", "format": "uuid"},
                "rejected_by": {"type": "string", "format": "uuid"},
                "rejected_at": {"type": "string", "format": "date-time"},
                "rejection_reason": {"type": "string"},
            },
        }
    },
    "marketplace.order.fulfilled": {
        "data": {
            "type": "object",
            "required": ["order_id"],
            "properties": {
                "order_id": {"type": "string", "format": "uuid"},
                "fulfilled_at": {"type": "string", "format": "date-time"},
                "entitlement_id": {"type": "string", "format": "uuid"},
            },
        }
    },
    "marketplace.entitlement.granted": {
        "data": {
            "type": "object",
            "required": ["entitlement_id", "order_id", "user_id"],
            "properties": {
                "entitlement_id": {"type": "string", "format": "uuid"},
                "order_id": {"type": "string", "format": "uuid"},
                "user_id": {"type": "string", "format": "uuid"},
                "granted_at": {"type": "string", "format": "date-time"},
                "expires_at": {"type": ["string", "null"], "format": "date-time"},
            },
        }
    },
    "marketplace.entitlement.revoked": {
        "data": {
            "type": "object",
            "required": ["entitlement_id", "revoked_by"],
            "properties": {
                "entitlement_id": {"type": "string", "format": "uuid"},
                "revoked_by": {"type": "string", "format": "uuid"},
                "revoked_at": {"type": "string", "format": "date-time"},
                "revocation_reason": {"type": "string"},
            },
        }
    },
    # Payment Events
    "payment.initiated": {
        "data": {
            "type": "object",
            "required": ["payment_id", "order_id"],
            "properties": {
                "payment_id": {"type": "string", "format": "uuid"},
                "order_id": {"type": "string", "format": "uuid"},
                "amount": {"type": ["number", "null"]},
                "currency": {"type": ["string", "null"]},
                "gateway": {"type": ["string", "null"]},
                "payment_method": {"type": ["string", "null"]},
            },
        }
    },
    "payment.completed": {
        "data": {
            "type": "object",
            "required": ["payment_id", "order_id", "status"],
            "properties": {
                "payment_id": {"type": "string", "format": "uuid"},
                "order_id": {"type": "string", "format": "uuid"},
                "status": {"type": "string"},
                "amount": {"type": ["number", "null"]},
                "currency": {"type": ["string", "null"]},
                "gateway": {"type": ["string", "null"]},
                "gateway_transaction_id": {"type": ["string", "null"]},
                "processed_at": {"type": ["string", "null"], "format": "date-time"},
            },
        }
    },
    "payment.failed": {
        "data": {
            "type": "object",
            "required": ["payment_id", "order_id", "error_message"],
            "properties": {
                "payment_id": {"type": "string", "format": "uuid"},
                "order_id": {"type": "string", "format": "uuid"},
                "error_message": {"type": "string"},
                "error_details": {"type": ["object", "null"]},
                "amount": {"type": ["number", "null"]},
                "currency": {"type": ["string", "null"]},
                "gateway": {"type": ["string", "null"]},
                "failed_at": {"type": ["string", "null"], "format": "date-time"},
            },
        }
    },
    "payment.refunded": {
        "data": {
            "type": "object",
            "required": ["payment_id", "order_id"],
            "properties": {
                "payment_id": {"type": "string", "format": "uuid"},
                "order_id": {"type": "string", "format": "uuid"},
                "refund_amount": {"type": ["number", "null"]},
                "currency": {"type": ["string", "null"]},
                "gateway": {"type": ["string", "null"]},
                "gateway_refund_id": {"type": ["string", "null"]},
                "refund_reason": {"type": ["string", "null"]},
                "refunded_at": {"type": ["string", "null"], "format": "date-time"},
            },
        }
    },
    # Payment Gateway Events
    "payment.gateway.linked": {
        "data": {
            "type": "object",
            "required": ["contract_id", "gateway_id"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "gateway_id": {"type": "string"},
                "webhook_url": {"type": ["string", "null"]},
                "gateway_type": {"type": ["string", "null"]},
                "gateway_name": {"type": ["string", "null"]},
            },
        }
    },
    "payment.gateway.unlinked": {
        "data": {
            "type": "object",
            "required": ["contract_id", "gateway_id"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "gateway_id": {"type": "string"},
                "reason": {"type": ["string", "null"]},
                "gateway_type": {"type": ["string", "null"]},
                "gateway_name": {"type": ["string", "null"]},
            },
        }
    },
    "payment.gateway.webhook.received": {
        "data": {
            "type": "object",
            "required": ["contract_id", "gateway_id"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "gateway_id": {"type": "string"},
                "webhook_type": {"type": ["string", "null"]},
                "webhook_data": {"type": "object"},
                "webhook_headers": {"type": "object"},
                "webhook_signature": {"type": ["string", "null"]},
                "processing_status": {"type": ["string", "null"]},
                "processing_error": {"type": ["string", "null"]},
            },
        }
    },
    # Workflow Events
    "workflow.created": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "workflow_name"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "workflow_name": {"type": "string"},
                "workflow_version": {"type": "string"},
                "input_data": {"type": "object"},
            },
        }
    },
    "workflow.started": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "workflow_name"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "workflow_name": {"type": "string"},
                "workflow_version": {"type": "string"},
                "input_data": {"type": "object"},
            },
        }
    },
    "workflow.completed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "workflow_name"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "workflow_name": {"type": "string"},
                "output_data": {"type": "object"},
                "duration_ms": {"type": "integer"},
            },
        }
    },
    "workflow.failed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "workflow_name", "error_message"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "workflow_name": {"type": "string"},
                "error_message": {"type": "string"},
                "error_details": {"type": "object"},
                "failed_step_index": {"type": ["integer", "null"]},
            },
        }
    },
    "workflow.cancelled": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "workflow_name"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "workflow_name": {"type": "string"},
                "cancelled_by": {"type": "string", "format": "uuid"},
                "cancellation_reason": {"type": "string"},
            },
        }
    },
    "workflow.step.started": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "step_index", "step_name"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "step_index": {"type": "integer"},
                "step_name": {"type": "string"},
                "step_type": {"type": "string"},
            },
        }
    },
    "workflow.step.completed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "step_index", "step_name"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "step_index": {"type": "integer"},
                "step_name": {"type": "string"},
                "output_data": {"type": "object"},
                "duration_ms": {"type": "integer"},
            },
        }
    },
    "workflow.step.failed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "step_index", "step_name", "error_message"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "step_index": {"type": "integer"},
                "step_name": {"type": "string"},
                "error_message": {"type": "string"},
                "error_details": {"type": "object"},
                "retry_count": {"type": "integer"},
            },
        }
    },
    # Data Mesh Workflow Events
    "workflow.data_mesh.domain_creation.started": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "domain_name": {"type": ["string", "null"]},
                "tenant_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    "workflow.data_mesh.domain_creation.step_completed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "step_name", "progress_percentage"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "step_name": {"type": "string"},
                "progress_percentage": {"type": "number"},
                "total_steps": {"type": ["integer", "null"]},
                "completed_steps": {"type": ["integer", "null"]},
                "elapsed_time_ms": {"type": ["integer", "null"]},
                "status": {"type": ["string", "null"]},
            },
        }
    },
    "workflow.data_mesh.domain_creation.completed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "domain_id"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "domain_id": {"type": "string", "format": "uuid"},
                "domain_name": {"type": ["string", "null"]},
                "duration_ms": {"type": ["integer", "null"]},
                "applied_policies_count": {"type": ["integer", "null"]},
            },
        }
    },
    "workflow.data_mesh.domain_creation.failed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "error_message"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "error_message": {"type": "string"},
                "domain_name": {"type": ["string", "null"]},
                "error_details": {"type": ["object", "null"]},
                "failed_step_index": {"type": ["integer", "null"]},
            },
        }
    },
    # API Key Management Workflow Events
    "workflow.api_key_management.started": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "operation": {"type": "string"},
                "status": {"type": "string"},
            },
        }
    },
    "workflow.api_key_management.step_completed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "step": {"type": "string"},
                "operation": {"type": "string"},
                "api_key_id": {"type": ["string", "null"], "format": "uuid"},
                "status": {"type": "string"},
            },
        }
    },
    "workflow.api_key_management.completed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "operation": {"type": "string"},
                "api_key_id": {"type": ["string", "null"], "format": "uuid"},
                "status": {"type": "string"},
            },
        }
    },
    "workflow.model_training.started": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": ["string", "null"]},
                "dataset_id": {"type": ["string", "null"]},
                "training_config": {"type": "object"},
            },
        }
    },
    "workflow.model_training.step_completed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "model_id": {"type": ["string", "null"]},
                "training_job_id": {"type": ["string", "null"]},
                "progress_percent": {"type": "number"},
                "current_step": {"type": "string"},
                "total_steps": {"type": ["integer", "null"]},
                "completed_steps": {"type": ["integer", "null"]},
                "elapsed_time_ms": {"type": ["integer", "null"]},
                "status": {"type": "string"},
            },
        }
    },
    "workflow.model_training.completed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "model_id": {"type": "string"},
                "training_job_id": {"type": ["string", "null"]},
                "duration_ms": {"type": ["integer", "null"]},
            },
        }
    },
    # ML Inference Workflow Events
    "workflow.model_inference.started": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "model_id": {"type": ["string", "null"]},
                "input_data": {"type": "object"},
            },
        }
    },
    "workflow.model_inference.step_completed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "model_id": {"type": ["string", "null"]},
                "inference_id": {"type": ["string", "null"]},
                "progress_percent": {"type": "number"},
                "current_step": {"type": "string"},
                "total_steps": {"type": ["integer", "null"]},
                "completed_steps": {"type": ["integer", "null"]},
                "elapsed_time_ms": {"type": ["integer", "null"]},
                "status": {"type": "string"},
            },
        }
    },
    "workflow.model_inference.completed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "model_id": {"type": ["string", "null"]},
                "inference_id": {"type": ["string", "null"]},
                "inference_result": {"type": "object"},
                "duration_ms": {"type": ["integer", "null"]},
            },
        }
    },
    # ODPS Events
    "odps.created": {
        "data": {
            "type": "object",
            "required": ["contract_id"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": ["string", "null"], "format": "uuid"},
                "status": {"type": ["string", "null"]},
                "odps_version": {"type": ["string", "null"]},
                "original_format": {"type": ["string", "null"]},
            },
        }
    },
    "odps.updated": {
        "data": {
            "type": "object",
            "required": ["contract_id"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
                "previous_status": {"type": ["string", "null"]},
                "new_status": {"type": ["string", "null"]},
            },
        }
    },
    "odps.deleted": {
        "data": {
            "type": "object",
            "required": ["contract_id"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "deleted_at": {"type": "string", "format": "date-time"},
                "reason": {"type": "string"},
            },
        }
    },
    "odps.normalized": {
        "data": {
            "type": "object",
            "required": ["contract_id", "normalization_status"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "normalization_status": {"type": "string"},
                "normalization_errors": {"type": ["array", "null"], "items": {"type": "string"}},
                "odps_version": {"type": ["string", "null"]},
            },
        }
    },
    "odps.linked": {
        "data": {
            "type": "object",
            "required": ["odps_contract_id", "odcs_contract_id"],
            "properties": {
                "odps_contract_id": {"type": "string", "format": "uuid"},
                "odcs_contract_id": {"type": "string", "format": "uuid"},
                "link_type": {"type": ["string", "null"]},
            },
        }
    },
    "odps.unlinked": {
        "data": {
            "type": "object",
            "required": ["odps_contract_id", "odcs_contract_id"],
            "properties": {
                "odps_contract_id": {"type": "string", "format": "uuid"},
                "odcs_contract_id": {"type": "string", "format": "uuid"},
                "reason": {"type": "string"},
            },
        }
    },
    "odps.ref.resolved": {
        "data": {
            "type": "object",
            "required": ["contract_id", "ref_path", "ref_type", "resolution_status"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "ref_path": {"type": "string"},
                "ref_type": {"type": "string"},
                "resolution_status": {"type": "string"},
                "ref_count": {"type": "integer"},
                "duration_ms": {"type": "integer"},
            },
        }
    },
    "odps.ref.failed": {
        "data": {
            "type": "object",
            "required": ["contract_id", "ref_path", "ref_type", "error_message"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "ref_path": {"type": "string"},
                "ref_type": {"type": "string"},
                "error_message": {"type": "string"},
                "error_code": {"type": "string"},
                "error_details": {"type": "object"},
            },
        }
    },
    "odps.export.started": {
        "data": {
            "type": "object",
            "required": ["contract_id", "export_format"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "export_format": {"type": "string"},
                "output_format": {"type": ["string", "null"]},
                "odps_version": {"type": ["string", "null"]},
            },
        }
    },
    "odps.export.completed": {
        "data": {
            "type": "object",
            "required": ["contract_id", "export_format"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "export_format": {"type": "string"},
                "output_format": {"type": ["string", "null"]},
                "file_size": {"type": ["integer", "null"]},
                "duration_ms": {"type": ["integer", "null"]},
            },
        }
    },
    "odps.export.failed": {
        "data": {
            "type": "object",
            "required": ["contract_id", "export_format", "error_message"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "export_format": {"type": "string"},
                "error_message": {"type": "string"},
                "error_details": {"type": "object"},
            },
        }
    },
    # ODPS Workflow Events (Task 7.1.4)
    "odps.workflow.started": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "workflow_name"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "workflow_name": {"type": "string"},
                "workflow_version": {"type": ["string", "null"]},
                "input_data": {"type": ["object", "null"]},
                "odps_version": {"type": ["string", "null"]},
                "progress_percentage": {"type": ["number", "null"]},
            },
        }
    },
    "odps.workflow.completed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "workflow_name"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "workflow_name": {"type": "string"},
                "workflow_version": {"type": ["string", "null"]},
                "output_data": {"type": ["object", "null"]},
                "duration_ms": {"type": ["integer", "null"]},
                "odps_contract_id": {"type": ["string", "null"], "format": "uuid"},
                "odcs_contract_id": {"type": ["string", "null"], "format": "uuid"},
                "progress_percentage": {"type": ["number", "null"]},
            },
        }
    },
    "odps.workflow.failed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "workflow_name", "error_message"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "workflow_name": {"type": "string"},
                "workflow_version": {"type": ["string", "null"]},
                "error_message": {"type": "string"},
                "error_details": {"type": ["object", "null"]},
                "failed_step_index": {"type": ["integer", "null"]},
                "failed_step_name": {"type": ["string", "null"]},
                "progress_percentage": {"type": ["number", "null"]},
            },
        }
    },
    "odps.workflow.step.completed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "step_index", "step_name"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "step_index": {"type": "integer"},
                "step_name": {"type": "string"},
                "step_type": {"type": ["string", "null"]},
                "output_data": {"type": ["object", "null"]},
                "duration_ms": {"type": ["integer", "null"]},
                "progress_percentage": {"type": ["number", "null"]},
                "odps_version": {"type": ["string", "null"]},
            },
        }
    },
    "odps.workflow.step.failed": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "step_index", "step_name", "error_message"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "step_index": {"type": "integer"},
                "step_name": {"type": "string"},
                "error_message": {"type": "string"},
                "error_details": {"type": ["object", "null"]},
                "retry_count": {"type": ["integer", "null"]},
                "duration_ms": {"type": ["integer", "null"]},
                "progress_percentage": {"type": ["number", "null"]},
            },
        }
    },
    "odps.workflow.progress": {
        "data": {
            "type": "object",
            "required": ["workflow_instance_id", "workflow_name", "progress_percentage"],
            "properties": {
                "workflow_instance_id": {"type": "string", "format": "uuid"},
                "workflow_name": {"type": "string"},
                "workflow_version": {"type": ["string", "null"]},
                "progress_percentage": {"type": "number"},
                "current_step_index": {"type": ["integer", "null"]},
                "current_step_name": {"type": ["string", "null"]},
                "total_steps": {"type": ["integer", "null"]},
            },
        }
    },
    # ODPS Progress Events (Task 7.3.2)
    "odps.creation.progress": {
        "data": {
            "type": "object",
            "required": ["progress_percentage"],
            "properties": {
                "contract_id": {"type": ["string", "null"], "format": "uuid"},
                "workflow_instance_id": {"type": ["string", "null"], "format": "uuid"},
                "progress_percentage": {"type": "number"},
                "current_step": {"type": ["string", "null"]},
                "total_steps": {"type": ["integer", "null"]},
                "step_index": {"type": ["integer", "null"]},
                "status_message": {"type": ["string", "null"]},
            },
        }
    },
    "odps.normalization.progress": {
        "data": {
            "type": "object",
            "required": ["progress_percentage"],
            "properties": {
                "contract_id": {"type": ["string", "null"], "format": "uuid"},
                "progress_percentage": {"type": "number"},
                "current_phase": {"type": ["string", "null"]},
                "total_phases": {"type": ["integer", "null"]},
                "phase_index": {"type": ["integer", "null"]},
                "items_processed": {"type": ["integer", "null"]},
                "items_total": {"type": ["integer", "null"]},
                "status_message": {"type": ["string", "null"]},
                "odps_version": {"type": ["string", "null"]},
            },
        }
    },
    "odps.ref.progress": {
        "data": {
            "type": "object",
            "required": ["progress_percentage"],
            "properties": {
                "contract_id": {"type": ["string", "null"], "format": "uuid"},
                "progress_percentage": {"type": "number"},
                "refs_processed": {"type": ["integer", "null"]},
                "refs_total": {"type": ["integer", "null"]},
                "current_ref_path": {"type": ["string", "null"]},
                "ref_type": {"type": ["string", "null"]},
                "status_message": {"type": ["string", "null"]},
            },
        }
    },
    "odps.linking.status": {
        "data": {
            "type": "object",
            "required": ["odps_contract_id", "odcs_contract_id", "status"],
            "properties": {
                "odps_contract_id": {"type": "string", "format": "uuid"},
                "odcs_contract_id": {"type": "string", "format": "uuid"},
                "status": {"type": "string"},
                "progress_percentage": {"type": ["number", "null"]},
                "current_phase": {"type": ["string", "null"]},
                "validation_passed": {"type": ["boolean", "null"]},
                "validation_errors": {"type": ["array", "null"], "items": {"type": "string"}},
                "link_type": {"type": ["string", "null"]},
                "status_message": {"type": ["string", "null"]},
            },
        }
    },
    "odps.export.progress": {
        "data": {
            "type": "object",
            "required": ["contract_id", "export_format", "progress_percentage"],
            "properties": {
                "contract_id": {"type": "string", "format": "uuid"},
                "export_format": {"type": "string"},
                "progress_percentage": {"type": "number"},
                "current_phase": {"type": ["string", "null"]},
                "bytes_processed": {"type": ["integer", "null"]},
                "bytes_total": {"type": ["integer", "null"]},
                "status_message": {"type": ["string", "null"]},
                "odps_version": {"type": ["string", "null"]},
            },
        }
    },
    # Transformation Pipeline Events
    "transformation.pipeline.created": {
        "data": {
            "type": "object",
            "required": ["pipeline_id"],
            "properties": {
                "pipeline_id": {"type": "string", "format": "uuid"},
                "name": {"type": ["string", "null"]},
                "version": {"type": ["string", "null"]},
                "status": {"type": ["string", "null"]},
            },
        }
    },
    "pipeline.started": {
        "data": {
            "type": "object",
            "required": ["pipeline_id"],
            "properties": {
                "pipeline_id": {"type": "string", "format": "uuid"},
                "execution_id": {"type": ["string", "null"], "format": "uuid"},
                "source_asset_id": {"type": ["string", "null"], "format": "uuid"},
                "target_asset_id": {"type": ["string", "null"], "format": "uuid"},
                "execution_mode": {"type": ["string", "null"]},
            },
        }
    },
    "pipeline.completed": {
        "data": {
            "type": "object",
            "required": ["pipeline_id", "execution_id"],
            "properties": {
                "pipeline_id": {"type": "string", "format": "uuid"},
                "execution_id": {"type": "string", "format": "uuid"},
                "result_asset_id": {"type": ["string", "null"], "format": "uuid"},
                "duration_ms": {"type": ["integer", "null"]},
                "records_processed": {"type": ["integer", "null"]},
                "status": {"type": ["string", "null"]},
            },
        }
    },
    "pipeline.failed": {
        "data": {
            "type": "object",
            "required": ["pipeline_id", "execution_id", "error_message"],
            "properties": {
                "pipeline_id": {"type": "string", "format": "uuid"},
                "execution_id": {"type": "string", "format": "uuid"},
                "error_message": {"type": "string"},
                "error_details": {"type": ["object", "null"]},
                "duration_ms": {"type": ["integer", "null"]},
            },
        }
    },
    "transformation.pipeline.execution.started": {
        "data": {
            "type": "object",
            "required": ["pipeline_id", "execution_id"],
            "properties": {
                "pipeline_id": {"type": "string", "format": "uuid"},
                "execution_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": ["string", "null"], "format": "uuid"},
                "execution_mode": {"type": ["string", "null"]},
            },
        }
    },
    "transformation.pipeline.execution.completed": {
        "data": {
            "type": "object",
            "required": ["pipeline_id", "execution_id"],
            "properties": {
                "pipeline_id": {"type": "string", "format": "uuid"},
                "execution_id": {"type": "string", "format": "uuid"},
                "result_asset_id": {"type": ["string", "null"], "format": "uuid"},
                "duration_ms": {"type": ["integer", "null"]},
                "records_processed": {"type": ["integer", "null"]},
                "quality_metrics": {"type": ["object", "null"]},
            },
        }
    },
    "transformation.pipeline.execution.failed": {
        "data": {
            "type": "object",
            "required": ["pipeline_id", "execution_id", "error_message"],
            "properties": {
                "pipeline_id": {"type": "string", "format": "uuid"},
                "execution_id": {"type": "string", "format": "uuid"},
                "error_message": {"type": "string"},
                "error_code": {"type": ["string", "null"]},
                "error_details": {"type": ["object", "null"]},
                "duration_ms": {"type": ["integer", "null"]},
            },
        }
    },
    # Transformation Wrangling Events
    "transformation.wrangling.operation.applied": {
        "data": {
            "type": "object",
            "required": ["session_id", "operation_id", "asset_id", "operation_type"],
            "properties": {
                "session_id": {"type": "string", "format": "uuid"},
                "operation_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": "string", "format": "uuid"},
                "operation_type": {"type": "string"},
                "operation_parameters": {"type": ["object", "null"]},
                "rows_affected": {"type": ["integer", "null"]},
                "execution_time_ms": {"type": ["integer", "null"]},
            },
        }
    },
    "transformation.wrangling.completed": {
        "data": {
            "type": "object",
            "required": ["session_id", "operation_id", "asset_id", "operation_type"],
            "properties": {
                "session_id": {"type": "string", "format": "uuid"},
                "operation_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": "string", "format": "uuid"},
                "operation_type": {"type": "string"},
                "rows_processed": {"type": ["integer", "null"]},
            },
        }
    },
    # Transformation Pipeline Execution Progress Events
    "transformation.pipeline.execution.progress": {
        "data": {
            "type": "object",
            "required": ["pipeline_id", "execution_id"],
            "properties": {
                "pipeline_id": {"type": "string", "format": "uuid"},
                "execution_id": {"type": "string", "format": "uuid"},
                "progress_percent": {"type": ["number", "null"]},
                "current_step": {"type": ["string", "null"]},
                "total_steps": {"type": ["integer", "null"]},
                "completed_steps": {"type": ["integer", "null"]},
                "elapsed_time_ms": {"type": ["integer", "null"]},
                "estimated_remaining_ms": {"type": ["integer", "null"]},
                "status": {"type": ["string", "null"]},
                "metrics": {"type": ["object", "null"]},
            },
        }
    },
    "transformation.pipeline.execution.step_completed": {
        "data": {
            "type": "object",
            "required": ["pipeline_id", "execution_id", "step_name"],
            "properties": {
                "pipeline_id": {"type": "string", "format": "uuid"},
                "execution_id": {"type": "string", "format": "uuid"},
                "step_name": {"type": "string"},
                "step_index": {"type": ["integer", "null"]},
                "duration_ms": {"type": ["integer", "null"]},
                "records_processed": {"type": ["integer", "null"]},
                "step_result": {"type": ["object", "null"]},
            },
        }
    },
    # Transformation Preview Events
    "transformation.preview.progress": {
        "data": {
            "type": "object",
            "required": ["pipeline_id", "asset_id", "preview_id"],
            "properties": {
                "pipeline_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": "string", "format": "uuid"},
                "preview_id": {"type": "string"},
                "progress_percent": {"type": ["number", "null"]},
                "current_operation": {"type": ["string", "null"]},
                "rows_processed": {"type": ["integer", "null"]},
                "total_rows": {"type": ["integer", "null"]},
                "elapsed_time_ms": {"type": ["integer", "null"]},
            },
        }
    },
    "transformation.preview.generated": {
        "data": {
            "type": "object",
            "required": ["pipeline_id", "asset_id", "preview_id"],
            "properties": {
                "pipeline_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": "string", "format": "uuid"},
                "preview_id": {"type": "string"},
                "row_count_changes": {"type": ["object", "null"]},
                "schema_changes": {"type": ["object", "null"]},
                "quality_impact": {"type": ["object", "null"]},
            },
        }
    },
    # Data Mesh Events
    "domain.created": {
        "data": {
            "type": "object",
            "required": ["domain_id"],
            "properties": {
                "domain_id": {"type": "string", "format": "uuid"},
                "name": {"type": "string"},
                "status": {"type": "string"},
                "owner_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    "domain.updated": {
        "data": {
            "type": "object",
            "required": ["domain_id"],
            "properties": {
                "domain_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
                "previous_status": {"type": "string"},
                "new_status": {"type": "string"},
            },
        }
    },
    "domain.deleted": {
        "data": {
            "type": "object",
            "required": ["domain_id"],
            "properties": {
                "domain_id": {"type": "string", "format": "uuid"},
                "deleted_at": {"type": "string", "format": "date-time"},
                "reason": {"type": "string"},
            },
        }
    },
    "policy.applied": {
        "data": {
            "type": "object",
            "required": ["policy_application_id", "domain_id"],
            "properties": {
                "policy_application_id": {"type": "string", "format": "uuid"},
                "domain_id": {"type": "string", "format": "uuid"},
                "policy_id": {"type": ["string", "null"], "format": "uuid"},
                "status": {"type": "string"},
            },
        }
    },
    "policy.revoked": {
        "data": {
            "type": "object",
            "required": ["policy_application_id", "domain_id"],
            "properties": {
                "policy_application_id": {"type": "string", "format": "uuid"},
                "domain_id": {"type": "string", "format": "uuid"},
                "policy_id": {"type": ["string", "null"], "format": "uuid"},
                "reason": {"type": "string"},
            },
        }
    },
    "compliance.report.generated": {
        "data": {
            "type": "object",
            "required": ["compliance_report_id", "domain_id"],
            "properties": {
                "compliance_report_id": {"type": "string", "format": "uuid"},
                "domain_id": {"type": "string", "format": "uuid"},
                "compliance_status": {"type": "string"},
                "asset_id": {"type": ["string", "null"], "format": "uuid"},
                "violation_count": {"type": ["integer", "null"]},
            },
        }
    },
    "mesh.compliance.checked": {
        "data": {
            "type": "object",
            "required": ["domain_id"],
            "properties": {
                "domain_id": {"type": "string", "format": "uuid"},
                "compliance_status": {"type": ["string", "null"]},
                "violation_count": {"type": ["integer", "null"]},
                "checked_at": {"type": ["string", "null"], "format": "date-time"},
            },
        }
    },
    "mesh.topology.updated": {
        "data": {
            "type": "object",
            "required": [],
            "properties": {
                "tenant_id": {"type": ["string", "null"], "format": "uuid"},
                "domain_count": {"type": ["integer", "null"]},
                "relationship_count": {"type": ["integer", "null"]},
                "updated_at": {"type": ["string", "null"], "format": "date-time"},
                "user_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    "mesh.domain.created": {
        "data": {
            "type": "object",
            "required": ["domain_id"],
            "properties": {
                "domain_id": {"type": "string", "format": "uuid"},
                "name": {"type": "string"},
                "status": {"type": "string"},
                "owner_id": {"type": ["string", "null"], "format": "uuid"},
                "tenant_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    "mesh.domain.updated": {
        "data": {
            "type": "object",
            "required": ["domain_id"],
            "properties": {
                "domain_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
                "previous_status": {"type": ["string", "null"]},
                "new_status": {"type": ["string", "null"]},
                "tenant_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    "mesh.policy.applied": {
        "data": {
            "type": "object",
            "required": ["policy_application_id", "domain_id"],
            "properties": {
                "policy_application_id": {"type": "string", "format": "uuid"},
                "domain_id": {"type": "string", "format": "uuid"},
                "policy_id": {"type": ["string", "null"], "format": "uuid"},
                "status": {"type": "string"},
                "tenant_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    "mesh.health.status_changed": {
        "data": {
            "type": "object",
            "required": ["domain_id"],
            "properties": {
                "domain_id": {"type": "string", "format": "uuid"},
                "previous_status": {"type": ["string", "null"]},
                "new_status": {"type": "string"},
                "health_metrics": {"type": ["object", "null"]},
                "changed_at": {"type": ["string", "null"], "format": "date-time"},
                "tenant_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    # Virtualization Events
    "virtualization.dataset.created": {
        "data": {
            "type": "object",
            "required": ["virtual_dataset_id"],
            "properties": {
                "virtual_dataset_id": {"type": "string", "format": "uuid"},
                "name": {"type": "string"},
                "query_type": {"type": "string"},
                "status": {"type": "string"},
                "version": {"type": "string"},
            },
        }
    },
    "virtualization.dataset.updated": {
        "data": {
            "type": "object",
            "required": ["virtual_dataset_id"],
            "properties": {
                "virtual_dataset_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
                "previous_status": {"type": "string"},
                "new_status": {"type": "string"},
            },
        }
    },
    "virtualization.dataset.deleted": {
        "data": {
            "type": "object",
            "required": ["virtual_dataset_id"],
            "properties": {
                "virtual_dataset_id": {"type": "string", "format": "uuid"},
                "deleted_at": {"type": "string", "format": "date-time"},
                "reason": {"type": "string"},
            },
        }
    },
    "virtualization.query.execution.started": {
        "data": {
            "type": "object",
            "required": ["query_execution_id", "virtual_dataset_id"],
            "properties": {
                "query_execution_id": {"type": "string", "format": "uuid"},
                "virtual_dataset_id": {"type": "string", "format": "uuid"},
                "execution_mode": {"type": "string"},
                "started_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "virtualization.query.execution.progress": {
        "data": {
            "type": "object",
            "required": ["query_execution_id", "virtual_dataset_id", "progress_percent"],
            "properties": {
                "query_execution_id": {"type": "string", "format": "uuid"},
                "virtual_dataset_id": {"type": "string", "format": "uuid"},
                "progress_percent": {"type": "number"},
                "current_step": {"type": ["string", "null"]},
                "elapsed_time_ms": {"type": ["integer", "null"]},
                "completed_steps": {"type": ["integer", "null"]},
                "total_steps": {"type": ["integer", "null"]},
                "timestamp": {"type": "string", "format": "date-time"},
            },
        }
    },
    "virtualization.query.execution.completed": {
        "data": {
            "type": "object",
            "required": ["query_execution_id", "virtual_dataset_id", "status"],
            "properties": {
                "query_execution_id": {"type": "string", "format": "uuid"},
                "virtual_dataset_id": {"type": "string", "format": "uuid"},
                "status": {"type": "string"},
                "completed_at": {"type": "string", "format": "date-time"},
                "duration_ms": {"type": ["integer", "null"]},
                "rows_processed": {"type": ["integer", "null"]},
            },
        }
    },
    "virtualization.query.execution.failed": {
        "data": {
            "type": "object",
            "required": ["query_execution_id", "virtual_dataset_id", "error_message"],
            "properties": {
                "query_execution_id": {"type": "string", "format": "uuid"},
                "virtual_dataset_id": {"type": "string", "format": "uuid"},
                "error_message": {"type": "string"},
                "failed_at": {"type": "string", "format": "date-time"},
                "duration_ms": {"type": ["integer", "null"]},
            },
        }
    },
    "virtualization.query.execution.cancelled": {
        "data": {
            "type": "object",
            "required": ["query_execution_id", "virtual_dataset_id"],
            "properties": {
                "query_execution_id": {"type": "string", "format": "uuid"},
                "virtual_dataset_id": {"type": "string", "format": "uuid"},
                "reason": {"type": ["string", "null"]},
                "cancelled_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    # User Events (auth)
    "user.created": {
        "data": {
            "type": "object",
            "required": ["user_id", "email"],
            "properties": {
                "user_id": {"type": "string", "format": "uuid"},
                "email": {"type": "string"},
                "tenant_id": {"type": ["string", "null"], "format": "uuid"},
                "created_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    # Tenant Events
    "tenant.created": {
        "data": {
            "type": "object",
            "required": ["tenant_id"],
            "properties": {
                "tenant_id": {"type": "string", "format": "uuid"},
                "name": {"type": ["string", "null"]},
                "slug": {"type": ["string", "null"]},
                "status": {"type": ["string", "null"]},
                "kyc_status": {"type": ["string", "null"]},
                "region": {"type": ["string", "null"]},
            },
        }
    },
    "tenant.updated": {
        "data": {
            "type": "object",
            "required": ["tenant_id"],
            "properties": {
                "tenant_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
                "previous_status": {"type": ["string", "null"]},
                "new_status": {"type": ["string", "null"]},
            },
        }
    },
    "tenant.deleted": {
        "data": {
            "type": "object",
            "required": ["tenant_id"],
            "properties": {
                "tenant_id": {"type": "string", "format": "uuid"},
                "deleted_at": {"type": "string", "format": "date-time"},
                "reason": {"type": ["string", "null"]},
            },
        }
    },
    "tenant.quota.changed": {
        "data": {
            "type": "object",
            "required": ["tenant_id"],
            "properties": {
                "tenant_id": {"type": "string", "format": "uuid"},
                "quota_type": {"type": "string"},
                "previous_value": {"type": ["string", "number", "array", "object", "null"]},
                "new_value": {"type": ["string", "number", "array", "object", "null"]},
                "quota_field": {"type": "string"},
            },
        }
    },
    # Search Events
    "search.query": {
        "data": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {"type": "string"},
                "query_type": {"type": ["string", "null"]},
                "filters": {"type": "object"},
                "result_count": {"type": ["integer", "null"]},
                "no_results": {"type": ["boolean", "null"]},
                "execution_time_ms": {"type": ["integer", "null"]},
            },
        }
    },
    "search.index.updated": {
        "data": {
            "type": "object",
            "required": ["resource_type", "resource_id"],
            "properties": {
                "index_id": {"type": ["string", "null"]},
                "resource_type": {"type": "string"},
                "resource_id": {"type": "string"},
                "title": {"type": ["string", "null"]},
                "update_type": {"type": ["string", "null"]},  # 'created', 'updated', 'deleted'
            },
        }
    },
    "search.index.rebuilt": {
        "data": {
            "type": "object",
            "required": [],
            "properties": {
                "tenant_id": {"type": ["string", "null"], "format": "uuid"},
                "resource_count": {"type": ["integer", "null"]},
                "duration_ms": {"type": ["integer", "null"]},
                "resource_types": {"type": "array", "items": {"type": "string"}},
                "success": {"type": ["boolean", "null"]},
                "errors": {"type": "array", "items": {"type": "string"}},
            },
        }
    },
    # Observability Events
    "observability.metric.recorded": {
        "data": {
            "type": "object",
            "required": ["metric_name"],
            "properties": {
                "metric_name": {"type": "string"},
                "metric_value": {"type": ["number", "null"]},
                "metric_type": {
                    "type": ["string", "null"]
                },  # 'counter', 'gauge', 'histogram', 'summary'
                "labels": {"type": ["object", "null"]},
            },
        }
    },
    "observability.trace.created": {
        "data": {
            "type": "object",
            "required": ["trace_id", "span_id"],
            "properties": {
                "trace_id": {"type": "string", "format": "uuid"},
                "span_id": {"type": "string", "format": "uuid"},
                "operation_name": {"type": ["string", "null"]},
                "duration_ms": {"type": ["number", "null"]},
                "status": {"type": ["string", "null"]},  # 'ok', 'error', 'unset'
                "attributes": {"type": ["object", "null"]},
            },
        }
    },
    "observability.log.created": {
        "data": {
            "type": "object",
            "required": ["message"],
            "properties": {
                "message": {"type": "string"},
                "log_level": {
                    "type": ["string", "null"]
                },  # 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
                "logger_name": {"type": ["string", "null"]},
                "context": {"type": ["object", "null"]},
            },
        }
    },
    "observability.alert.triggered": {
        "data": {
            "type": "object",
            "required": ["alert_name", "alert_severity"],
            "properties": {
                "alert_name": {"type": "string"},
                "alert_severity": {"type": "string"},  # 'info', 'warning', 'critical'
                "alert_message": {"type": ["string", "null"]},
                "metric_name": {"type": ["string", "null"]},
                "threshold_value": {"type": ["number", "null"]},
                "current_value": {"type": ["number", "null"]},
                "triggered_at": {"type": ["string", "null"], "format": "date-time"},
            },
        }
    },
    # Integration Events
    "integration.connection.created": {
        "data": {
            "type": "object",
            "required": ["connection_id", "marketplace_type", "name"],
            "properties": {
                "connection_id": {"type": "string", "format": "uuid"},
                "marketplace_type": {"type": "string"},
                "name": {"type": "string"},
                "is_active": {"type": "boolean"},
            },
        }
    },
    "integration.connection.updated": {
        "data": {
            "type": "object",
            "required": ["connection_id", "changes"],
            "properties": {
                "connection_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
            },
        }
    },
    "integration.connection.deleted": {
        "data": {
            "type": "object",
            "required": ["connection_id", "marketplace_type", "name"],
            "properties": {
                "connection_id": {"type": "string", "format": "uuid"},
                "marketplace_type": {"type": "string"},
                "name": {"type": "string"},
                "deleted_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "integration.connection.tested": {
        "data": {
            "type": "object",
            "required": ["connection_id", "success"],
            "properties": {
                "connection_id": {"type": "string", "format": "uuid"},
                "success": {"type": "boolean"},
                "message": {"type": ["string", "null"]},
                "tested_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    # Sync Job Events
    "integration.sync_job.created": {
        "data": {
            "type": "object",
            "required": ["sync_job_id", "connection_id", "direction"],
            "properties": {
                "sync_job_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "direction": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "integration.sync_job.started": {
        "data": {
            "type": "object",
            "required": ["sync_job_id", "connection_id", "direction"],
            "properties": {
                "sync_job_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "direction": {"type": "string"},
                "started_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "integration.sync_job.completed": {
        "data": {
            "type": "object",
            "required": [
                "sync_job_id",
                "connection_id",
                "direction",
                "status",
                "items_synced",
                "items_failed",
            ],
            "properties": {
                "sync_job_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "direction": {"type": "string"},
                "status": {"type": "string"},
                "items_synced": {"type": "integer"},
                "items_failed": {"type": "integer"},
                "completed_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "integration.sync_job.cancelled": {
        "data": {
            "type": "object",
            "required": ["sync_job_id", "connection_id", "direction"],
            "properties": {
                "sync_job_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "direction": {"type": "string"},
                "reason": {"type": ["string", "null"]},
                "cancelled_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    # Mapping Events
    "integration.mapping.created": {
        "data": {
            "type": "object",
            "required": ["mapping_id", "connection_id", "hub_asset_id", "external_listing_id"],
            "properties": {
                "mapping_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "hub_asset_id": {"type": "string", "format": "uuid"},
                "external_listing_id": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "integration.mapping.updated": {
        "data": {
            "type": "object",
            "required": ["mapping_id", "connection_id", "changes"],
            "properties": {
                "mapping_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
                "updated_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "integration.mapping.deleted": {
        "data": {
            "type": "object",
            "required": ["mapping_id", "connection_id", "hub_asset_id", "external_listing_id"],
            "properties": {
                "mapping_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "hub_asset_id": {"type": "string", "format": "uuid"},
                "external_listing_id": {"type": "string"},
                "reason": {"type": ["string", "null"]},
                "deleted_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    # Scheduled Sync Events
    "integration.scheduled_sync.created": {
        "data": {
            "type": "object",
            "required": ["scheduled_sync_id", "connection_id", "direction", "schedule_type"],
            "properties": {
                "scheduled_sync_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "direction": {"type": "string"},
                "schedule_type": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "integration.scheduled_sync.deleted": {
        "data": {
            "type": "object",
            "required": ["scheduled_sync_id", "connection_id"],
            "properties": {
                "scheduled_sync_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "deleted_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    # Marketplace Integration Events (using marketplace.* prefix)
    "marketplace.connection.created": {
        "data": {
            "type": "object",
            "required": ["connection_id", "marketplace_type", "name"],
            "properties": {
                "connection_id": {"type": "string", "format": "uuid"},
                "marketplace_type": {"type": "string"},
                "name": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "marketplace.connection.updated": {
        "data": {
            "type": "object",
            "required": ["connection_id", "changes"],
            "properties": {
                "connection_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
                "updated_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "marketplace.connection.deleted": {
        "data": {
            "type": "object",
            "required": ["connection_id", "marketplace_type", "name"],
            "properties": {
                "connection_id": {"type": "string", "format": "uuid"},
                "marketplace_type": {"type": "string"},
                "name": {"type": "string"},
                "reason": {"type": ["string", "null"]},
                "deleted_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "marketplace.sync.started": {
        "data": {
            "type": "object",
            "required": ["sync_job_id", "connection_id", "direction"],
            "properties": {
                "sync_job_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "direction": {"type": "string"},
                "started_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "marketplace.sync.completed": {
        "data": {
            "type": "object",
            "required": [
                "sync_job_id",
                "connection_id",
                "direction",
                "status",
                "items_synced",
                "items_failed",
            ],
            "properties": {
                "sync_job_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "direction": {"type": "string"},
                "status": {"type": "string"},
                "items_synced": {"type": "integer"},
                "items_failed": {"type": "integer"},
                "completed_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "marketplace.sync.failed": {
        "data": {
            "type": "object",
            "required": ["sync_job_id", "connection_id", "direction", "error_message"],
            "properties": {
                "sync_job_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "direction": {"type": "string"},
                "error_message": {"type": "string"},
                "error_details": {"type": "object"},
                "failed_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "marketplace.mapping.created": {
        "data": {
            "type": "object",
            "required": ["mapping_id", "connection_id", "hub_asset_id", "external_listing_id"],
            "properties": {
                "mapping_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "hub_asset_id": {"type": "string", "format": "uuid"},
                "external_listing_id": {"type": "string"},
                "created_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "marketplace.mapping.updated": {
        "data": {
            "type": "object",
            "required": ["mapping_id", "connection_id", "changes"],
            "properties": {
                "mapping_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "changes": {"type": "object"},
                "updated_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "marketplace.mapping.deleted": {
        "data": {
            "type": "object",
            "required": ["mapping_id", "connection_id", "hub_asset_id", "external_listing_id"],
            "properties": {
                "mapping_id": {"type": "string", "format": "uuid"},
                "connection_id": {"type": "string", "format": "uuid"},
                "hub_asset_id": {"type": "string", "format": "uuid"},
                "external_listing_id": {"type": "string"},
                "reason": {"type": ["string", "null"]},
                "deleted_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    # BaaS Events
    "baas.usage.tracked": {
        "data": {
            "type": "object",
            "required": ["api_key_id", "endpoint", "method", "status_code", "response_time_ms"],
            "properties": {
                "api_key_id": {"type": "string", "format": "uuid"},
                "endpoint": {"type": "string"},
                "method": {"type": "string"},
                "status_code": {"type": "integer"},
                "response_time_ms": {"type": "integer"},
                "tenant_id": {"type": ["string", "null"], "format": "uuid"},
                "user_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    # Billing Events (Phase 116B — customer billing reports)
    "billing.report.generated": {
        "data": {
            "type": "object",
            "required": ["report_id", "customer_id", "total_amount", "currency"],
            "properties": {
                "report_id": {"type": "string", "format": "uuid"},
                "customer_id": {"type": "string"},
                "total_amount": {"type": "string"},
                "currency": {"type": "string"},
            },
        }
    },
    "billing.report.sent": {
        "data": {
            "type": "object",
            "required": ["report_id", "customer_id", "customer_email"],
            "properties": {
                "report_id": {"type": "string", "format": "uuid"},
                "customer_id": {"type": "string"},
                "customer_email": {"type": "string"},
            },
        }
    },
    # Phase 240.5.A — DQ run completion billing event.
    # Payload contract mirrors hub.apps.billing.event_types.DQ_RUN_COMPLETED.
    "billing.dq.run.completed": {
        "data": {
            "type": "object",
            "required": [
                "tenant_id",
                "dq_run_id",
                "engine",
                "rows_inspected",
                "columns_inspected",
                "execution_time_seconds",
            ],
            "properties": {
                "tenant_id": {"type": "string", "format": "uuid"},
                "dq_run_id": {"type": "string", "format": "uuid"},
                "engine": {"type": "string"},
                "rows_inspected": {"type": "integer"},
                "columns_inspected": {"type": "integer"},
                "execution_time_seconds": {"type": "number"},
                "quality_score": {"type": ["number", "null"]},
            },
        }
    },
    # Notification Events
    "notification.created": {
        "data": {
            "type": "object",
            "required": ["id", "user_id"],
            "properties": {
                "id": {"type": "string", "format": "uuid"},
                "user_id": {"type": "string", "format": "uuid"},
                "category": {"type": "string"},
                "notification_type": {"type": "string"},
                "title": {"type": "string"},
                "resource_type": {"type": "string"},
                "resource_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    # ── Social Events ────────────────────────────────────────────────
    # Schemas mirror the data dicts published by social/views.py.
    # user_id is carried as event metadata (Event.user_id column), NOT
    # inside the data payload — do NOT add it as a required field here.
    "social.rating.created": {
        "data": {
            "type": "object",
            "required": ["rating_id", "asset_id"],
            "properties": {
                "rating_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": "string", "format": "uuid"},
                "rating": {"type": "integer"},
            },
        }
    },
    "social.review.created": {
        "data": {
            "type": "object",
            "required": ["review_id", "asset_id"],
            "properties": {
                "review_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": "string", "format": "uuid"},
            },
        }
    },
    "social.comment.created": {
        "data": {
            "type": "object",
            "required": ["comment_id", "asset_id"],
            "properties": {
                "comment_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": "string", "format": "uuid"},
                "parent_comment_id": {"type": ["string", "null"], "format": "uuid"},
            },
        }
    },
    "social.community.created": {
        "data": {
            "type": "object",
            "required": ["community_id"],
            "properties": {
                "community_id": {"type": "string", "format": "uuid"},
                "name": {"type": "string"},
            },
        }
    },
    "social.community.joined": {
        "data": {
            "type": "object",
            "required": ["community_id"],
            "properties": {
                "community_id": {"type": "string", "format": "uuid"},
                "name": {"type": "string"},
            },
        }
    },
    # ── ML Model Events ──────────────────────────────────────────────
    "ml.model.linked": {
        "data": {
            "type": "object",
            "required": ["model_id", "odh_model_id"],
            "properties": {
                "model_id": {"type": "string", "format": "uuid"},
                "odh_model_id": {"type": "string"},
                "asset_id": {"type": ["string", "null"], "format": "uuid"},
                "contract_id": {"type": ["string", "null"], "format": "uuid"},
                "linked_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "ml.model.synced": {
        "data": {
            "type": "object",
            "required": ["model_id", "odh_model_id", "sync_status"],
            "properties": {
                "model_id": {"type": "string", "format": "uuid"},
                "odh_model_id": {"type": "string"},
                "sync_status": {"type": "string"},
                "synced_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "ml.dataset.linked": {
        "data": {
            "type": "object",
            "required": ["model_id", "dataset_id", "role"],
            "properties": {
                "model_id": {"type": "string", "format": "uuid"},
                "dataset_id": {"type": "string", "format": "uuid"},
                "role": {"type": "string"},
                "linked_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "ml.model.asset.created": {
        "data": {
            "type": "object",
            "required": ["model_id", "asset_id"],
            "properties": {
                "model_id": {"type": "string", "format": "uuid"},
                "asset_id": {"type": "string", "format": "uuid"},
                "created_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    # ── ML Training Job Events ─────────────────────────────────────────
    "ml.training.job.submitted": {
        "data": {
            "type": "object",
            "required": ["model_id", "dataset_id", "odh_job_id"],
            "properties": {
                "model_id": {"type": "string", "format": "uuid"},
                "dataset_id": {"type": "string", "format": "uuid"},
                "odh_job_id": {"type": "string"},
                "hub_job_id": {"type": "string"},
                "submitted_at": {"type": "string", "format": "date-time"},
            },
        }
    },
    "ml.training.job.completed": {
        "data": {
            "type": "object",
            "required": ["model_id", "odh_job_id", "status"],
            "properties": {
                "model_id": {"type": "string", "format": "uuid"},
                "odh_job_id": {"type": "string"},
                "hub_job_id": {"type": ["string", "null"]},
                "asset_id": {"type": ["string", "null"], "format": "uuid"},
                "status": {"type": "string"},
                "metrics": {"type": "object"},
                "completed_at": {"type": "string", "format": "date-time"},
            },
        }
    },
}


def get_event_schema(event_type: str) -> dict[str, Any] | None:
    """
    Get schema for specific event type.

    Args:
        event_type: Event type (e.g., 'contract.created')

    Returns:
        Event schema dictionary or None if not found
    """
    return EVENT_TYPE_SCHEMAS.get(event_type)


def get_all_event_types() -> list[str]:
    """
    Get list of all defined event types.

    Returns:
        List of event type strings
    """
    return list(EVENT_TYPE_SCHEMAS.keys())


def validate_event_data(event_type: str, data: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Validate event data against event type schema.

    Args:
        event_type: Event type (e.g., 'contract.created')
        data: Event data to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    schema = get_event_schema(event_type)
    if not schema:
        return False, f"Unknown event type: {event_type}"

    # Check required fields
    required_fields = schema["data"].get("required", [])
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"

    # Basic type validation (full JSON Schema validation can be added later)
    properties = schema["data"].get("properties", {})
    for field, value in data.items():
        if field in properties:
            field_schema = properties[field]
            expected_type = field_schema.get("type")

            if expected_type:
                # Handle union types (e.g., ["string", "null"])
                if isinstance(expected_type, list):
                    if not any(_validate_type(value, t) for t in expected_type):
                        return (
                            False,
                            f"Field '{field}' has invalid type. Expected one of {expected_type}, got {type(value).__name__}",
                        )
                elif not _validate_type(value, expected_type):
                    return (
                        False,
                        f"Field '{field}' has invalid type. Expected {expected_type}, got {type(value).__name__}",
                    )

    return True, None


def _validate_type(value: Any, expected_type: str) -> bool:
    """Validate value matches expected type."""
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "object": dict,
        "array": list,
        "null": type(None),
    }

    python_type = type_map.get(expected_type)
    if python_type is None:
        return True  # Unknown type, skip validation

    if expected_type == "null":
        return value is None

    # Handle tuple types (e.g., (int, float) for number)
    if isinstance(python_type, tuple):
        return isinstance(value, python_type)

    return isinstance(value, python_type)
