"""
Data Classification Engine

Rule-based classifier for automatic data classification with confidence scoring.
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from django.db import transaction
from django.utils import timezone

from .models import (
    DataClassification,
    ClassificationCategory,
    ClassificationStatus
)
from hub.apps.compliance.service_client import ComplianceServiceClient


class PIIType(str, Enum):
    """PII types for detection"""
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    SSN = "SSN"
    CREDIT_CARD = "CREDIT_CARD"
    IP_ADDRESS = "IP_ADDRESS"
    DATE_OF_BIRTH = "DATE_OF_BIRTH"
    PASSPORT = "PASSPORT"
    DRIVER_LICENSE = "DRIVER_LICENSE"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    TAX_ID = "TAX_ID"


@dataclass
class ClassificationRule:
    """Classification rule definition"""
    name: str
    category: ClassificationCategory
    patterns: List[str]  # Regex patterns
    keywords: List[str]  # Keywords to match
    field_name_patterns: List[str]  # Field name patterns
    confidence_base: float  # Base confidence (0.0-1.0)
    pii_type: Optional[PIIType] = None


@dataclass
class ClassificationResult:
    """Classification result"""
    category: ClassificationCategory
    confidence: float
    matched_rules: List[str]
    detected_patterns: List[str]
    pii_types: List[str]


class DataClassifier:
    """
    Rule-based data classifier.
    
    Classifies fields, datasets, and assets based on:
    - Regex patterns for PII types
    - Keyword matching for sensitive terms
    - Field name patterns
    - Integration with compliance service
    """
    
    # Classification rules
    RULES = [
        # PII Rules
        ClassificationRule(
            name="email_detection",
            category=ClassificationCategory.PII,
            patterns=[
                r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$',
            ],
            keywords=[],
            field_name_patterns=['email', 'e-mail', 'mail', 'email_address'],
            confidence_base=0.95,
            pii_type=PIIType.EMAIL
        ),
        ClassificationRule(
            name="phone_detection",
            category=ClassificationCategory.PII,
            patterns=[
                r'^\+?1?\d{9,15}$',
                r'^\(\d{3}\)\s?\d{3}-\d{4}$',
                r'^\d{3}-\d{3}-\d{4}$',
            ],
            keywords=[],
            field_name_patterns=['phone', 'telephone', 'mobile', 'cell'],
            confidence_base=0.90,
            pii_type=PIIType.PHONE
        ),
        ClassificationRule(
            name="ssn_detection",
            category=ClassificationCategory.PII,
            patterns=[
                r'^\d{3}-\d{2}-\d{4}$',
                r'^\d{9}$',
            ],
            keywords=[],
            field_name_patterns=['ssn', 'social_security', 'social_security_number'],
            confidence_base=0.98,
            pii_type=PIIType.SSN
        ),
        ClassificationRule(
            name="credit_card_detection",
            category=ClassificationCategory.PCI,
            patterns=[
                r'^\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}$',
                r'^\d{13,19}$',
            ],
            keywords=[],
            field_name_patterns=['credit_card', 'card_number', 'cc_number', 'payment_card'],
            confidence_base=0.95,
            pii_type=PIIType.CREDIT_CARD
        ),
        ClassificationRule(
            name="ip_address_detection",
            category=ClassificationCategory.PII,
            patterns=[
                r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$',
                r'^[0-9a-fA-F:]+$',  # IPv6
            ],
            keywords=[],
            field_name_patterns=['ip_address', 'ip', 'ipv4', 'ipv6'],
            confidence_base=0.85,
            pii_type=PIIType.IP_ADDRESS
        ),
        ClassificationRule(
            name="date_of_birth_detection",
            category=ClassificationCategory.PII,
            patterns=[
                r'^\d{4}-\d{2}-\d{2}$',
                r'^\d{2}/\d{2}/\d{4}$',
                r'^\d{2}-\d{2}-\d{4}$',
            ],
            keywords=[],
            field_name_patterns=['dob', 'date_of_birth', 'birth_date', 'birthdate'],
            confidence_base=0.90,
            pii_type=PIIType.DATE_OF_BIRTH
        ),
        # Financial Rules
        ClassificationRule(
            name="financial_keywords",
            category=ClassificationCategory.FINANCIAL,
            patterns=[],
            keywords=['salary', 'income', 'revenue', 'profit', 'loss', 'balance', 'account'],
            field_name_patterns=['salary', 'income', 'revenue', 'profit', 'account_number'],
            confidence_base=0.80
        ),
        # Legal Rules
        ClassificationRule(
            name="legal_keywords",
            category=ClassificationCategory.LEGAL,
            patterns=[],
            keywords=['contract', 'agreement', 'lawsuit', 'litigation', 'legal', 'attorney'],
            field_name_patterns=['contract', 'agreement', 'legal'],
            confidence_base=0.75
        ),
        # Confidential Rules
        ClassificationRule(
            name="confidential_keywords",
            category=ClassificationCategory.CONFIDENTIAL,
            patterns=[],
            keywords=['secret', 'confidential', 'proprietary', 'internal', 'private'],
            field_name_patterns=['secret', 'confidential', 'proprietary'],
            confidence_base=0.70
        ),
    ]
    
    @staticmethod
    def classify_field(
        field_name: str,
        field_data: Optional[Dict[str, Any]] = None,
        sample_values: Optional[List[Any]] = None,
        compliance_service_client: Optional[ComplianceServiceClient] = None
    ) -> ClassificationResult:
        """
        Classify a field based on name, data type, and sample values.
        
        Args:
            field_name: Field name
            field_data: Field metadata (type, nullable, etc.)
            sample_values: Sample values from the field
            compliance_service_client: Optional compliance service client for enhanced detection
        
        Returns:
            ClassificationResult
        """
        matched_rules = []
        detected_patterns = []
        pii_types = []
        max_confidence = 0.0
        best_category = ClassificationCategory.INTERNAL
        
        field_name_lower = field_name.lower()
        
        # Check each rule
        for rule in DataClassifier.RULES:
            rule_matched = False
            rule_confidence = rule.confidence_base
            
            # Check field name patterns
            for pattern in rule.field_name_patterns:
                if pattern.lower() in field_name_lower:
                    rule_matched = True
                    matched_rules.append(rule.name)
                    break
            
            # Check keywords in field name
            for keyword in rule.keywords:
                if keyword.lower() in field_name_lower:
                    rule_matched = True
                    matched_rules.append(rule.name)
                    break
            
            # Check patterns in sample values
            if sample_values:
                for value in sample_values[:10]:  # Check first 10 samples
                    if value is None:
                        continue
                    
                    value_str = str(value)
                    for pattern in rule.patterns:
                        if re.match(pattern, value_str):
                            rule_matched = True
                            detected_patterns.append(f"{rule.name}:{pattern}")
                            if rule.pii_type:
                                pii_types.append(rule.pii_type.value)
                            # Increase confidence if pattern matches
                            rule_confidence = min(1.0, rule_confidence + 0.1)
                            break
            
            # Check keywords in sample values
            if sample_values:
                for value in sample_values[:10]:
                    if value is None:
                        continue
                    
                    value_str = str(value).lower()
                    for keyword in rule.keywords:
                        if keyword.lower() in value_str:
                            rule_matched = True
                            detected_patterns.append(f"{rule.name}:keyword:{keyword}")
                            rule_confidence = min(1.0, rule_confidence + 0.05)
                            break
            
            # Update best classification
            if rule_matched and rule_confidence > max_confidence:
                max_confidence = rule_confidence
                best_category = rule.category
        
        # Integration with compliance service (if available)
        if compliance_service_client and sample_values:
            try:
                # Use compliance service for enhanced PII detection
                # This is a placeholder - actual implementation would call the service
                pass
            except Exception:
                # Don't fail if compliance service is unavailable
                pass
        
        # Default to INTERNAL if no rules matched
        if max_confidence == 0.0:
            best_category = ClassificationCategory.INTERNAL
            max_confidence = 0.5  # Low confidence for default
        
        return ClassificationResult(
            category=best_category,
            confidence=max_confidence,
            matched_rules=list(set(matched_rules)),
            detected_patterns=list(set(detected_patterns)),
            pii_types=list(set(pii_types))
        )
    
    @staticmethod
    @transaction.atomic
    def classify_field_level(
        tenant_id: str,
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        field_name: str = None,
        field_data: Optional[Dict[str, Any]] = None,
        sample_values: Optional[List[Any]] = None,
        user_id: Optional[str] = None
    ) -> DataClassification:
        """
        Classify a field and create DataClassification record.
        
        Args:
            tenant_id: Tenant UUID
            asset_id: Asset UUID (optional)
            dataset_id: Dataset UUID (optional)
            field_name: Field name
            field_data: Field metadata
            sample_values: Sample values
            user_id: User UUID who triggered classification
        
        Returns:
            DataClassification instance
        """
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        
        # Get resource
        asset = Asset.objects.get(id=asset_id) if asset_id else None
        dataset = Dataset.objects.get(id=dataset_id) if dataset_id else None
        
        # Classify field
        result = DataClassifier.classify_field(
            field_name=field_name,
            field_data=field_data,
            sample_values=sample_values
        )
        
        # Create or update classification
        classification, created = DataClassification.objects.update_or_create(
            tenant_id=tenant_id,
            asset=asset,
            dataset=dataset,
            field_name=field_name,
            defaults={
                'category': result.category.value,
                'status': ClassificationStatus.AUTO_CLASSIFIED.value,
                'confidence_score': result.confidence,
                'classification_rules': result.matched_rules,
                'detected_patterns': result.detected_patterns,
                'created_by_id': user_id
            }
        )
        
        return classification
    
    @staticmethod
    @transaction.atomic
    def classify_dataset(
        tenant_id: str,
        dataset_id: str,
        user_id: Optional[str] = None
    ) -> List[DataClassification]:
        """
        Classify all fields in a dataset.
        
        Args:
            tenant_id: Tenant UUID
            dataset_id: Dataset UUID
            user_id: User UUID who triggered classification
        
        Returns:
            List of DataClassification instances
        """
        from hub.apps.datasets.models import Dataset
        
        dataset = Dataset.objects.get(id=dataset_id)
        schema_json = dataset.schema_json or {}
        fields = schema_json.get('fields', [])
        
        classifications = []
        
        for field in fields:
            field_name = field.get('name')
            sample_values = field.get('sample_values', [])
            
            classification = DataClassifier.classify_field_level(
                tenant_id=tenant_id,
                dataset_id=dataset_id,
                field_name=field_name,
                field_data=field,
                sample_values=sample_values,
                user_id=user_id
            )
            classifications.append(classification)
        
        return classifications
    
    @staticmethod
    @transaction.atomic
    def classify_asset(
        tenant_id: str,
        asset_id: str,
        user_id: Optional[str] = None
    ) -> List[DataClassification]:
        """
        Classify an asset (aggregates classifications from all datasets).
        
        Args:
            tenant_id: Tenant UUID
            asset_id: Asset UUID
            user_id: User UUID who triggered classification
        
        Returns:
            List of DataClassification instances
        """
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        
        asset = Asset.objects.get(id=asset_id)
        
        # Get all current datasets for the asset
        datasets = Dataset.objects.filter(
            tenant_id=tenant_id,
            asset_id=asset_id,
            is_current=True
        )
        
        classifications = []
        
        for dataset in datasets:
            dataset_classifications = DataClassifier.classify_dataset(
                tenant_id=tenant_id,
                dataset_id=str(dataset.id),
                user_id=user_id
            )
            classifications.extend(dataset_classifications)
        
        return classifications
    
    @staticmethod
    def approve_classification(
        classification_id: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> DataClassification:
        """
        Approve a classification (manual review).
        
        Args:
            classification_id: Classification UUID
            user_id: User UUID approving
            notes: Optional review notes
        
        Returns:
            Updated DataClassification instance
        """
        classification = DataClassification.objects.get(id=classification_id)
        classification.status = ClassificationStatus.APPROVED.value
        classification.reviewed_by_id = user_id
        classification.reviewed_at = timezone.now()
        if notes:
            classification.manual_review_notes = notes
        classification.save()
        return classification
    
    @staticmethod
    def reject_classification(
        classification_id: str,
        user_id: str,
        new_category: ClassificationCategory,
        notes: Optional[str] = None
    ) -> DataClassification:
        """
        Reject a classification and set new category.
        
        Args:
            classification_id: Classification UUID
            user_id: User UUID rejecting
            new_category: New classification category
            notes: Optional review notes
        
        Returns:
            Updated DataClassification instance
        """
        classification = DataClassification.objects.get(id=classification_id)
        classification.status = ClassificationStatus.REJECTED.value
        classification.category = new_category.value
        classification.reviewed_by_id = user_id
        classification.reviewed_at = timezone.now()
        if notes:
            classification.manual_review_notes = notes
        classification.save()
        return classification

