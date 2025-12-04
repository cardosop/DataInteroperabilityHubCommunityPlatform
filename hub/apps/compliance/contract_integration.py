"""
Compliance Service Integration with Contract Compliance Policy (GAP-8.2.2).

Reads compliance policy from HubContract and integrates it with compliance service execution.
"""
from typing import Dict, Any, List, Optional
from hub.apps.contracts.models import Contract

# Import vocabulary mappings - handle import path with hyphen
import sys
import os
semantic_service_path = os.path.join(os.path.dirname(__file__), '../../../services/semantic-service')
if semantic_service_path not in sys.path:
    sys.path.insert(0, semantic_service_path)
try:
    from vocabulary_mappings import (
        get_dpv_category,
        get_dpv_jurisdiction,
        get_dpv_legal_basis
    )
except ImportError:
    def get_dpv_category(category):
        return None
    def get_dpv_jurisdiction(jurisdiction):
        return None
    def get_dpv_legal_basis(basis):
        return None


class ContractCompliancePolicyExtractor:
    """
    Extracts compliance policy from HubContract and converts it to compliance service parameters.
    """
    
    @staticmethod
    def extract_compliance_policy(contract: Contract) -> Dict[str, Any]:
        """
        Extract compliance policy from contract's HubContract JSON.
        
        Args:
            contract: Contract instance
            
        Returns:
            Dictionary with:
            - contains_personal_data: Boolean
            - personal_data_categories: List of category strings
            - jurisdictions: List of jurisdiction strings
            - legal_bases: List of legal basis strings
            - retention_policy: Retention policy dictionary
        """
        hub_contract = contract.hub_contract_json or {}
        compliance_section = hub_contract.get('privacy_compliance', {})
        
        return {
            'contains_personal_data': compliance_section.get('contains_personal_data', False),
            'personal_data_categories': compliance_section.get('personal_data_categories', []),
            'jurisdictions': compliance_section.get('jurisdictions', []),
            'legal_bases': compliance_section.get('legal_bases', []),
            'retention_policy': compliance_section.get('retention_policy')
        }
    
    @staticmethod
    def get_targeted_pii_categories(contract: Contract) -> List[str]:
        """
        Get targeted PII categories from contract for focused detection (GAP-8.2.2).
        
        Args:
            contract: Contract instance
            
        Returns:
            List of PII category strings for targeted detection
        """
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(contract)
        return policy.get('personal_data_categories', [])
    
    @staticmethod
    def get_regulatory_mapping(contract: Contract) -> List[str]:
        """
        Get jurisdictions from contract for regulatory mapping (GAP-8.2.2).
        
        Args:
            contract: Contract instance
            
        Returns:
            List of jurisdiction strings (GDPR, LGPD, CCPA, etc.)
        """
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(contract)
        return policy.get('jurisdictions', [])
    
    @staticmethod
    def get_legal_bases(contract: Contract) -> List[str]:
        """
        Get legal bases from contract for compliance reporting (GAP-8.2.2).
        
        Args:
            contract: Contract instance
            
        Returns:
            List of legal basis strings (CONSENT, CONTRACT, etc.)
        """
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(contract)
        return policy.get('legal_bases', [])
    
    @staticmethod
    def get_retention_policy(contract: Contract) -> Optional[Dict[str, Any]]:
        """
        Get retention policy from contract for data retention enforcement (GAP-8.2.2).
        
        Args:
            contract: Contract instance
            
        Returns:
            Retention policy dictionary with period and notes, or None
        """
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(contract)
        return policy.get('retention_policy')
    
    @staticmethod
    def map_categories_to_dpv(categories: List[str]) -> List[str]:
        """
        Map personal data categories to DPV vocabulary terms (GAP-8.2.2).
        
        Args:
            categories: List of category strings
            
        Returns:
            List of DPV category identifiers
        """
        dpv_categories = []
        for category in categories:
            dpv_term = get_dpv_category(category)
            if dpv_term:
                # Extract the local name from the URIRef
                dpv_categories.append(str(dpv_term).split('#')[-1] if '#' in str(dpv_term) else category)
            else:
                # Keep original if no mapping found
                dpv_categories.append(category)
        return dpv_categories
    
    @staticmethod
    def map_jurisdictions_to_dpv(jurisdictions: List[str]) -> List[str]:
        """
        Map jurisdictions to DPV vocabulary terms (GAP-8.2.2).
        
        Args:
            jurisdictions: List of jurisdiction strings
            
        Returns:
            List of DPV jurisdiction identifiers
        """
        dpv_jurisdictions = []
        for jurisdiction in jurisdictions:
            dpv_term = get_dpv_jurisdiction(jurisdiction)
            if dpv_term:
                # Extract the local name from the URIRef
                dpv_jurisdictions.append(str(dpv_term).split('#')[-1] if '#' in str(dpv_term) else jurisdiction)
            else:
                # Keep original if no mapping found
                dpv_jurisdictions.append(jurisdiction)
        return dpv_jurisdictions

