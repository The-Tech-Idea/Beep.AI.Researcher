"""Medical domain plugin (Phase 3.2) - Drug interactions, ICD-10, CPT, HIPAA."""
import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.services.plugin_base import PluginBase, PluginMetadata, HookContext, HookResult

logger = logging.getLogger(__name__)


class MedicalPlugin(PluginBase):
    """Medical domain plugin providing clinical validation and data enrichment.
    
    Features:
    - Drug interaction checking
    - ICD-10 code validation and suggestion
    - CPT code lookup
    - Medical abbreviation expansion
    - HIPAA compliance checking
    """

    def __init__(self, metadata: PluginMetadata):
        """Initialize medical plugin."""
        super().__init__(metadata)
        self._drug_database = self._load_drug_database()
        self._icd10_codes = self._load_icd10_codes()
        self._cpt_codes = self._load_cpt_codes()
        self._medical_abbreviations = self._load_abbreviations()
        self._hipaa_sensitive_terms = self._load_hipaa_terms()

    async def on_plugin_load(self, context: HookContext) -> HookResult:
        """Called when plugin is loaded."""
        try:
            logger.info("Medical plugin loaded")
            return HookResult(
                success=True,
                plugin_name=self.metadata.name,
                hook_point=context.hook_point,
                execution_time_ms=10.0,
                data={"loaded_resources": "drug_db, icd10, cpt, abbreviations, hipaa_terms"},
            )
        except Exception as e:
            logger.error(f"Failed to load medical plugin: {e}")
            return HookResult(
                success=False,
                plugin_name=self.metadata.name,
                hook_point=context.hook_point,
                execution_time_ms=0.0,
                status="error",
                error_message=str(e),
            )

    async def on_plugin_unload(self, context: HookContext) -> HookResult:
        """Called when plugin is unloaded."""
        try:
            logger.info("Medical plugin unloaded")
            self._drug_database = {}
            self._icd10_codes = {}
            self._cpt_codes = {}
            
            return HookResult(
                success=True,
                plugin_name=self.metadata.name,
                hook_point=context.hook_point,
                execution_time_ms=2.0,
            )
        except Exception as e:
            return HookResult(
                success=False,
                plugin_name=self.metadata.name,
                hook_point=context.hook_point,
                execution_time_ms=0.0,
                status="error",
                error_message=str(e),
            )

    async def on_extraction(self, context: HookContext) -> HookResult:
        """Process extracted medical fields."""
        try:
            field_name = context.data.get("field_name", "")
            field_value = context.data.get("extracted_value", "")
            suggestions = []

            # ICD-10 validation
            if "diagnosis" in field_name.lower() or "icd" in field_name.lower():
                icd_result = await self.validate_icd10(field_value)
                if icd_result["suggestions"]:
                    suggestions.extend(icd_result["suggestions"])

            # CPT code validation
            if "procedure" in field_name.lower() or "cpt" in field_name.lower():
                cpt_result = await self.lookup_cpt(field_value)
                if cpt_result["code"]:
                    suggestions.append(f"CPT-{cpt_result['code']}: {cpt_result['description']}")

            # Drug/Medication validation
            if "medication" in field_name.lower() or "drug" in field_name.lower():
                interact_result = await self.check_drug_interactions(field_value, context.data.get("other_drugs", []))
                if interact_result["interactions"]:
                    suggestions.extend([f"⚠️ {i}" for i in interact_result["interactions"]])

            # HIPAA checking
            hipaa_result = await self.check_hipaa_compliance(field_value)
            if not hipaa_result["compliant"]:
                suggestions.append(f"⚠️ HIPAA: {hipaa_result['issue']}")

            return HookResult(
                success=True,
                plugin_name=self.metadata.name,
                hook_point=context.hook_point,
                execution_time_ms=5.0,
                suggestions=suggestions,
                data={
                    "field_name": field_name,
                    "validation_passed": True,
                    "suggestion_count": len(suggestions),
                },
            )

        except Exception as e:
            logger.error(f"Error in on_extraction: {e}")
            return HookResult(
                success=False,
                plugin_name=self.metadata.name,
                hook_point=context.hook_point,
                execution_time_ms=0.0,
                status="error",
                error_message=str(e),
            )

    # ========================================================================
    # Drug Interaction Checking
    # ========================================================================

    async def check_drug_interactions(self, drug_name: str, 
                                     other_drugs: List[str] = None) -> Dict[str, Any]:
        """Check for drug-drug interactions.
        
        Args:
            drug_name: Primary drug name
            other_drugs: List of other drugs to check against
            
        Returns:
            Dict with interactions list
        """
        if other_drugs is None:
            other_drugs = []

        interactions = []
        drug_normalized = drug_name.lower().strip()

        # Check against known drug database
        if drug_normalized in self._drug_database:
            drug_info = self._drug_database[drug_normalized]
            
            for other_drug in other_drugs:
                other_normalized = other_drug.lower().strip()
                if other_normalized in drug_info.get("interactions", []):
                    severity = drug_info["interactions"][other_normalized].get("severity", "moderate")
                    description = drug_info["interactions"][other_normalized].get("description", "")
                    interactions.append(f"{drug_name} + {other_drug} ({severity}): {description}")

        return {
            "drug": drug_name,
            "interactions": interactions,
            "has_interactions": len(interactions) > 0,
        }

    # ========================================================================
    # ICD-10 Code Validation
    # ========================================================================

    async def validate_icd10(self, code_or_term: str) -> Dict[str, Any]:
        """Validate and suggest ICD-10 codes.
        
        Args:
            code_or_term: ICD-10 code or diagnosis term
            
        Returns:
            Dict with validation results and suggestions
        """
        code_normalized = code_or_term.upper().strip()
        suggestions = []
        is_valid = False

        # Check if exact code match
        if code_normalized in self._icd10_codes:
            is_valid = True
            return {
                "code": code_normalized,
                "description": self._icd10_codes[code_normalized]["description"],
                "is_valid": True,
                "suggestions": [],
            }

        # Search by term
        term_lower = code_or_term.lower().strip()
        for code, info in self._icd10_codes.items():
            desc_lower = info["description"].lower()
            if term_lower in desc_lower or code.startswith(code_normalized):
                suggestions.append(f"{code}: {info['description']}")

        return {
            "code": code_or_term,
            "is_valid": is_valid,
            "suggestions": suggestions[:5],  # Top 5 suggestions
            "suggestion_count": len(suggestions),
        }

    # ========================================================================
    # CPT Code Lookup
    # ========================================================================

    async def lookup_cpt(self, code_or_description: str) -> Dict[str, Any]:
        """Lookup CPT code information.
        
        Args:
            code_or_description: CPT code or procedure description
            
        Returns:
            Dict with CPT information
        """
        code_upper = code_or_description.upper().strip()
        
        # Check exact code match
        if code_upper in self._cpt_codes:
            info = self._cpt_codes[code_upper]
            return {
                "code": code_upper,
                "description": info["description"],
                "category": info.get("category", ""),
                "found": True,
            }

        # Search by description
        desc_lower = code_or_description.lower().strip()
        for code, info in self._cpt_codes.items():
            if desc_lower in info["description"].lower():
                return {
                    "code": code,
                    "description": info["description"],
                    "category": info.get("category", ""),
                    "found": True,
                }

        return {
            "code": code_or_description,
            "description": None,
            "found": False,
        }

    # ========================================================================
    # Medical Abbreviation Expansion
    # ========================================================================

    async def expand_abbreviation(self, abbreviation: str) -> Dict[str, Any]:
        """Expand medical abbreviation.
        
        Args:
            abbreviation: Medical abbreviation
            
        Returns:
            Dict with expansion
        """
        abbrev_upper = abbreviation.upper().strip()
        
        if abbrev_upper in self._medical_abbreviations:
            expansion = self._medical_abbreviations[abbrev_upper]
            return {
                "abbreviation": abbrev_upper,
                "expansion": expansion["meaning"],
                "category": expansion.get("category", ""),
                "found": True,
            }

        return {
            "abbreviation": abbrev_upper,
            "expansion": None,
            "found": False,
        }

    # ========================================================================
    # HIPAA Compliance Checking
    # ========================================================================

    async def check_hipaa_compliance(self, text: str) -> Dict[str, Any]:
        """Check text for HIPAA-sensitive information.
        
        Args:
            text: Text to check
            
        Returns:
            Dict with compliance status
        """
        text_lower = text.lower()
        sensitive_found = []

        for term in self._hipaa_sensitive_terms:
            if term.lower() in text_lower:
                sensitive_found.append(term)

        return {
            "text_sample": text[:50],
            "compliant": len(sensitive_found) == 0,
            "sensitive_terms_found": sensitive_found,
            "issue": f"Contains {len(sensitive_found)} potentially sensitive terms" if sensitive_found else None,
        }

    # ========================================================================
    # Data Loading Methods
    # ========================================================================

    def _load_drug_database(self) -> Dict[str, Any]:
        """Load drug interaction database."""
        return {
            "warfarin": {
                "category": "anticoagulant",
                "interactions": {
                    "aspirin": {
                        "severity": "high",
                        "description": "Increased bleeding risk",
                    },
                    "ibuprofen": {
                        "severity": "high",
                        "description": "Increased GI bleeding risk",
                    },
                },
            },
            "metformin": {
                "category": "antidiabetic",
                "interactions": {
                    "alcohol": {
                        "severity": "moderate",
                        "description": "Increased lactic acidosis risk",
                    },
                },
            },
            "lisinopril": {
                "category": "ace_inhibitor",
                "interactions": {
                    "potassium_supplement": {
                        "severity": "high",
                        "description": "Hyperkalemia risk",
                    },
                },
            },
        }

    def _load_icd10_codes(self) -> Dict[str, Any]:
        """Load ICD-10 code database."""
        return {
            "I10": {"description": "Essential (primary) hypertension"},
            "E11": {"description": "Type 2 diabetes mellitus"},
            "J45": {"description": "Asthma"},
            "M79.3": {"description": "Muscle spasm"},
            "F41": {"description": "Anxiety disorders"},
            "E78": {"description": "Abdominal obesity"},
            "I50": {"description": "Heart failure"},
            "J44": {"description": "Chronic obstructive pulmonary disease (COPD)"},
        }

    def _load_cpt_codes(self) -> Dict[str, Any]:
        """Load CPT code database."""
        return {
            "99213": {
                "description": "Office visit, established patient, low to moderate complexity",
                "category": "E&M",
            },
            "99214": {
                "description": "Office visit, established patient, moderate to high complexity",
                "category": "E&M",
            },
            "90834": {
                "description": "Psychotherapy, 45 minutes",
                "category": "Mental Health",
            },
            "93000": {
                "description": "Electrocardiogram (ECG), 12-lead",
                "category": "Diagnostic",
            },
            "85025": {
                "description": "Complete blood count (CBC) with differential",
                "category": "Lab",
            },
        }

    def _load_abbreviations(self) -> Dict[str, Any]:
        """Load medical abbreviations database."""
        return {
            "BP": {"meaning": "Blood Pressure", "category": "vital_signs"},
            "HR": {"meaning": "Heart Rate", "category": "vital_signs"},
            "RR": {"meaning": "Respiratory Rate", "category": "vital_signs"},
            "T": {"meaning": "Temperature", "category": "vital_signs"},
            "CBC": {"meaning": "Complete Blood Count", "category": "lab"},
            "BMP": {"meaning": "Basic Metabolic Panel", "category": "lab"},
            "CMP": {"meaning": "Comprehensive Metabolic Panel", "category": "lab"},
            "ECG": {"meaning": "Electrocardiogram", "category": "diagnostic"},
            "EHR": {"meaning": "Electronic Health Record", "category": "system"},
            "EMR": {"meaning": "Electronic Medical Record", "category": "system"},
        }

    def _load_hipaa_terms(self) -> List[str]:
        """Load HIPAA-sensitive terms list."""
        return [
            "SSN",
            "social security",
            "medical record number",
            "MRN",
            "patient id",
            "account number",
            "credit card",
            "date of birth",
            "DOB",
            "mother's maiden name",
            "address",
            "phone number",
            "email",
            "insurance",
            "health plan",
            "beneficiary",
        ]

    # ========================================================================
    # Validation Methods
    # ========================================================================

    async def validate_field(self, field_name: str, field_value: Any,
                            field_context: Dict[str, Any]) -> HookResult:
        """Validate extraction field.
        
        Args:
            field_name: Field name
            field_value: Field value
            field_context: Field context
            
        Returns:
            HookResult
        """
        suggestions = []

        if not field_value:
            return HookResult(
                success=True,
                plugin_name=self.metadata.name,
                hook_point="validate_field",
                execution_time_ms=0.0,
                status="skipped",
            )

        # Route to appropriate validator
        field_lower = field_name.lower()

        if "diagnosis" in field_lower or "icd" in field_lower:
            result = await self.validate_icd10(str(field_value))
            if result["suggestions"]:
                suggestions = result["suggestions"]

        elif "procedure" in field_lower or "cpt" in field_lower:
            result = await self.lookup_cpt(str(field_value))
            if result["found"]:
                suggestions.append(f"✓ Valid CPT: {result['code']}")
            else:
                suggestions.append("⚠️ CPT code not found, check format")

        elif "medication" in field_lower or "drug" in field_lower:
            hipaa_result = await self.check_hipaa_compliance(str(field_value))
            if not hipaa_result["compliant"]:
                suggestions.append(f"⚠️ HIPAA: {hipaa_result['issue']}")

        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point="validate_field",
            execution_time_ms=2.0,
            suggestions=suggestions,
        )
