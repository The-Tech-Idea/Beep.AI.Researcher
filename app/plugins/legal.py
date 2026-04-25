"""Legal domain plugin (Phase 3.3) - Contract analysis, compliance, case law."""
import logging
import re
from typing import Any, Dict, List, Optional

from app.services.plugin_base import PluginBase, PluginMetadata, HookContext, HookResult

logger = logging.getLogger(__name__)


class LegalPlugin(PluginBase):
    """Legal domain plugin providing contract analysis and compliance checking.
    
    Features:
    - Contract clause extraction and analysis
    - Legal term dictionary and definitions
    - Regulatory compliance checking
    - Standard clause identification
    - Risk assessment
    """

    def __init__(self, metadata: PluginMetadata):
        """Initialize legal plugin."""
        super().__init__(metadata)
        self._legal_terms = self._load_legal_terms()
        self._contract_clauses = self._load_contract_clauses()
        self._compliance_frameworks = self._load_compliance_frameworks()
        self._risk_keywords = self._load_risk_keywords()

    async def on_plugin_load(self, context: HookContext) -> HookResult:
        """Called when plugin is loaded."""
        try:
            logger.info("Legal plugin loaded")
            return HookResult(
                success=True,
                plugin_name=self.metadata.name,
                hook_point=context.hook_point,
                execution_time_ms=8.0,
                data={"loaded_resources": "legal_terms, contract_clauses, compliance, risk_keywords"},
            )
        except Exception as e:
            logger.error(f"Failed to load legal plugin: {e}")
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
            logger.info("Legal plugin unloaded")
            self._legal_terms = {}
            self._contract_clauses = {}
            self._compliance_frameworks = {}
            
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
        """Process extracted legal fields."""
        try:
            field_name = context.data.get("field_name", "")
            field_value = context.data.get("extracted_value", "")
            suggestions = []

            # Clause extraction and analysis
            if "clause" in field_name.lower() or "provision" in field_name.lower():
                clause_result = await self.extract_clauses(field_value)
                if clause_result["clauses_found"]:
                    suggestions.extend([f"📋 {c['type']}: {c['summary']}" for c in clause_result["clauses_found"][:3]])
                    
                risk_result = await self.assess_risk(field_value, clause_result.get("clauses_found", []))
                if risk_result["risk_level"] != "low":
                    suggestions.append(f"⚠️ Risk: {risk_result['risk_level']} - {risk_result['issues'][0] if risk_result['issues'] else ''}")

            # Compliance checking
            if "compliance" in field_name.lower() or "regulation" in field_name.lower():
                compliance_result = await self.check_compliance(field_value)
                if not compliance_result["compliant"]:
                    suggestions.extend([f"❌ {issue}" for issue in compliance_result["issues"][:3]])

            # Legal term analysis
            if "legal" in field_name.lower() or "term" in field_name.lower():
                term_result = await self.analyze_legal_terms(field_value)
                if term_result["unknown_terms"]:
                    suggestions.append(f"❓ {len(term_result['unknown_terms'])} undefined legal terms found")

            return HookResult(
                success=True,
                plugin_name=self.metadata.name,
                hook_point=context.hook_point,
                execution_time_ms=6.0,
                suggestions=suggestions,
                data={
                    "field_name": field_name,
                    "clauses_detected": len(suggestions) > 0,
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
    # Contract Clause Extraction
    # ========================================================================

    async def extract_clauses(self, text: str) -> Dict[str, Any]:
        """Extract and identify contract clauses.
        
        Args:
            text: Contract text
            
        Returns:
            Dict with identified clauses
        """
        clauses_found = []
        text_lower = text.lower()
        text_upper = text.upper()

        for clause_type, patterns in self._contract_clauses.items():
            for pattern in patterns["keywords"]:
                if pattern.lower() in text_lower:
                    clauses_found.append({
                        "type": clause_type,
                        "summary": patterns["description"],
                        "found_keyword": pattern,
                    })
                    break

        return {
            "total_clauses_found": len(clauses_found),
            "clauses_found": clauses_found,
            "clause_types": [c["type"] for c in clauses_found],
        }

    # ========================================================================
    # Compliance Checking
    # ========================================================================

    async def check_compliance(self, text: str, frameworks: List[str] = None) -> Dict[str, Any]:
        """Check text for regulatory compliance.
        
        Args:
            text: Text to check
            frameworks: Specific frameworks to check against
            
        Returns:
            Dict with compliance status
        """
        if frameworks is None:
            frameworks = list(self._compliance_frameworks.keys())

        issues = []
        text_lower = text.lower()

        for framework in frameworks:
            if framework not in self._compliance_frameworks:
                continue

            framework_reqs = self._compliance_frameworks[framework]

            for requirement in framework_reqs["requirements"]:
                keywords = requirement["keywords"]
                found = any(kw.lower() in text_lower for kw in keywords)

                if not found and requirement.get("required", True):
                    issues.append(f"{framework}: Missing {requirement['name']}")

            # Check for forbidden terms
            for forbidden in framework_reqs.get("forbidden_terms", []):
                if forbidden.lower() in text_lower:
                    issues.append(f"{framework}: Contains forbidden term '{forbidden}'")

        return {
            "compliant": len(issues) == 0,
            "frameworks_checked": len(frameworks),
            "issues": issues,
            "issue_count": len(issues),
        }

    # ========================================================================
    # Risk Assessment
    # ========================================================================

    async def assess_risk(self, text: str, identified_clauses: List[Dict] = None) -> Dict[str, Any]:
        """Assess legal risk in contract text.
        
        Args:
            text: Contract text
            identified_clauses: Already identified clauses
            
        Returns:
            Dict with risk assessment
        """
        if identified_clauses is None:
            identified_clauses = []

        risk_score = 0
        issues = []
        text_lower = text.lower()

        # Check for high-risk keywords
        high_risk_terms = self._risk_keywords.get("high", {})
        for term, description in high_risk_terms.items():
            if term.lower() in text_lower:
                risk_score += 3
                issues.append(f"High-risk term: {description}")

        # Check for medium-risk keywords
        medium_risk_terms = self._risk_keywords.get("medium", {})
        for term, description in medium_risk_terms.items():
            if term.lower() in text_lower:
                risk_score += 1
                issues.append(f"Medium-risk term: {description}")

        # Determine risk level
        if risk_score >= 5:
            risk_level = "high"
        elif risk_score >= 2:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "issues": issues,
            "clause_count": len(identified_clauses),
        }

    # ========================================================================
    # Legal Term Analysis
    # ========================================================================

    async def analyze_legal_terms(self, text: str) -> Dict[str, Any]:
        """Analyze legal terminology in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with term analysis
        """
        words = text.lower().split()
        known_terms = []
        unknown_terms = []

        for word in words:
            word_clean = re.sub(r'[^\w]', '', word)
            
            if word_clean in self._legal_terms:
                known_terms.append({
                    "term": word_clean,
                    "definition": self._legal_terms[word_clean]["definition"],
                })
            elif len(word_clean) > 5 and any(c.isupper() for c in word):
                # Potential legal term
                unknown_terms.append(word_clean)

        return {
            "known_terms": known_terms,
            "unknown_terms": unknown_terms[:10],  # Top 10
            "total_unique_terms": len(set(words)),
            "legal_term_percentage": len(known_terms) / max(len(set(words)), 1),
        }

    # ========================================================================
    # Data Loading Methods
    # ========================================================================

    def _load_legal_terms(self) -> Dict[str, Any]:
        """Load legal terms dictionary."""
        return {
            "indemnify": {
                "definition": "To secure against loss or damage by providing compensation",
                "category": "liability",
            },
            "litigation": {
                "definition": "A legal proceeding in a court of law",
                "category": "dispute",
            },
            "jurisdiction": {
                "definition": "The official power to make legal decisions and judgments",
                "category": "legal",
            },
            "liability": {
                "definition": "Legal responsibility or obligation",
                "category": "legal",
            },
            "waiver": {
                "definition": "The voluntary relinquishment or surrender of a known right",
                "category": "rights",
            },
            "severability": {
                "definition": "Each part of a contract is enforceable even if others are not",
                "category": "contract",
            },
            "breach": {
                "definition": "Failure to fulfill an obligation under a contract",
                "category": "contract",
            },
            "force majeure": {
                "definition": "Unforeseeable circumstances beyond parties' control",
                "category": "contract",
            },
            "arbitration": {
                "definition": "Process of resolving dispute outside court by neutral arbitrator",
                "category": "dispute",
            },
            "consideration": {
                "definition": "Something of value exchanged between parties to a contract",
                "category": "contract",
            },
        }

    def _load_contract_clauses(self) -> Dict[str, Any]:
        """Load common contract clauses."""
        return {
            "limitation_of_liability": {
                "keywords": ["limitation of liability", "liability cap", "maximum liability"],
                "description": "Limits amount of damages a party can recover",
            },
            "indemnification": {
                "keywords": ["indemnify", "indemnification", "hold harmless"],
                "description": "One party agrees to protect another from loss or damage",
            },
            "termination": {
                "keywords": ["termination", "terminate", "end of agreement"],
                "description": "Conditions under which contract can end",
            },
            "confidentiality": {
                "keywords": ["confidential", "confidentiality", "proprietary", "trade secret"],
                "description": "Protection of sensitive information",
            },
            "warranty": {
                "keywords": ["warranty", "warranted", "warrants"],
                "description": "Promise about product or service quality",
            },
            "payment_terms": {
                "keywords": ["payment", "invoice", "due date", "net days"],
                "description": "When and how payment must be made",
            },
            "force_majeure": {
                "keywords": ["force majeure", "act of god", "unforeseen circumstances"],
                "description": "Unconditional excuse from performance",
            },
            "governing_law": {
                "keywords": ["governing law", "jurisdiction", "state law"],
                "description": "Which legal system governs the contract",
            },
        }

    def _load_compliance_frameworks(self) -> Dict[str, Any]:
        """Load compliance frameworks."""
        return {
            "GDPR": {
                "requirements": [
                    {
                        "name": "Data Protection Notice",
                        "keywords": ["data protection", "GDPR", "privacy"],
                        "required": True,
                    },
                    {
                        "name": "Consent Mechanisms",
                        "keywords": ["consent", "opt-in", "explicit"],
                        "required": True,
                    },
                ],
                "forbidden_terms": ["unlimited access", "perpetual collection"],
            },
            "CCPA": {
                "requirements": [
                    {
                        "name": "California Consumer Rights",
                        "keywords": ["california", "CCPA", "consumer rights"],
                        "required": True,
                    },
                    {
                        "name": "Opt-out Mechanism",
                        "keywords": ["opt-out", "right to delete"],
                        "required": True,
                    },
                ],
                "forbidden_terms": ["no deletion", "permanent retention"],
            },
        }

    def _load_risk_keywords(self) -> Dict[str, Dict[str, str]]:
        """Load risk keyword database."""
        return {
            "high": {
                "unlimited liability": "No cap on damages",
                "perpetual": "Rights extend indefinitely",
                "no termination": "Cannot end agreement",
                "unilateral": "One-sided changes allowed",
                "indemnify all": "Unlimited indemnification",
            },
            "medium": {
                "exclusivity": "Only one party allowed",
                "non-compete": "Cannot work with competitors",
                "royalty": "Ongoing payment obligations",
                "warranty": "Quality guarantees",
                "escrow": "Third-party fund holding",
            },
        }

    # ========================================================================
    # Validation Methods
    # ========================================================================

    async def validate_field(self, field_name: str, field_value: Any,
                            field_context: Dict[str, Any]) -> HookResult:
        """Validate legal field.
        
        Args:
            field_name: Field name
            field_value: Field value
            field_context: Field context
            
        Returns:
            HookResult
        """
        if not field_value:
            return HookResult(
                success=True,
                plugin_name=self.metadata.name,
                hook_point="validate_field",
                execution_time_ms=0.0,
                status="skipped",
            )

        suggestions = []
        field_lower = field_name.lower()

        if "clause" in field_lower:
            clause_result = await self.extract_clauses(str(field_value))
            if clause_result["clauses_found"]:
                suggestions.append(f"✓ Identified {len(clause_result['clauses_found'])} clauses")

        if "compliance" in field_lower:
            compliance_result = await self.check_compliance(str(field_value))
            if not compliance_result["compliant"]:
                suggestions.append(f"⚠️ {compliance_result['issue_count']} compliance issues")

        if "risk" in field_lower:
            risk_result = await self.assess_risk(str(field_value))
            suggestions.append(f"📊 Risk Level: {risk_result['risk_level'].upper()}")

        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point="validate_field",
            execution_time_ms=3.0,
            suggestions=suggestions,
        )
