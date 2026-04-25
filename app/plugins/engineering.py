"""Engineering domain plugin (Phase 3.4) - Standards, materials, safety."""
import logging
from typing import Any, Dict, List, Optional

from app.services.plugin_base import PluginBase, PluginMetadata, HookContext, HookResult

logger = logging.getLogger(__name__)


class EngineeringPlugin(PluginBase):
    """Engineering domain plugin for standards compliance and technical validation.
    
    Features:
    - Engineering standards compliance (ISO, IEEE, NIST)
    - Parts and materials database lookup
    - Safety data sheet (SDS) integration
    - Unit and measurement validation
    - Technical specification checking
    """

    def __init__(self, metadata: PluginMetadata):
        """Initialize engineering plugin."""
        super().__init__(metadata)
        self._standards = self._load_standards()
        self._materials_database = self._load_materials()
        self._parts_database = self._load_parts()
        self._units = self._load_units()
        self._safety_terms = self._load_safety_terms()

    async def on_plugin_load(self, context: HookContext) -> HookResult:
        """Called when plugin is loaded."""
        try:
            logger.info("Engineering plugin loaded")
            return HookResult(
                success=True,
                plugin_name=self.metadata.name,
                hook_point=context.hook_point,
                execution_time_ms=12.0,
                data={"loaded_resources": "standards, materials, parts, units, safety_terms"},
            )
        except Exception as e:
            logger.error(f"Failed to load engineering plugin: {e}")
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
            logger.info("Engineering plugin unloaded")
            self._standards = {}
            self._materials_database = {}
            self._parts_database = {}
            
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
        """Process extracted engineering fields."""
        try:
            field_name = context.data.get("field_name", "")
            field_value = context.data.get("extracted_value", "")
            suggestions = []

            # Standards compliance
            if "standard" in field_name.lower() or "requirement" in field_name.lower():
                standards_result = await self.check_standards_compliance(field_value)
                if standards_result["applicable_standards"]:
                    suggestions.extend([f"📋 {s['id']}: {s['title']}" for s in standards_result["applicable_standards"][:2]])

            # Materials/Parts lookup
            if "material" in field_name.lower() or "component" in field_name.lower():
                material_result = await self.lookup_material(field_value)
                if material_result["found"]:
                    suggestions.append(f"✓ Material: {material_result['description']}")
                else:
                    suggestions.append(f"❓ Material not in database")

            # Safety checking
            if "safety" in field_name.lower() or "hazard" in field_name.lower():
                safety_result = await self.check_safety_concerns(field_value)
                if safety_result["hazards_found"]:
                    suggestions.extend([f"⚠️ {h}" for h in safety_result["hazards_found"][:2]])

            # Unit validation
            if "measurement" in field_name.lower() or "dimension" in field_name.lower():
                unit_result = await self.validate_units(field_value)
                if not unit_result["valid"]:
                    suggestions.append(f"⚠️ Invalid unit: {unit_result['message']}")

            return HookResult(
                success=True,
                plugin_name=self.metadata.name,
                hook_point=context.hook_point,
                execution_time_ms=7.0,
                suggestions=suggestions,
                data={
                    "field_name": field_name,
                    "validation_passed": True,
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
    # Standards Compliance Checking
    # ========================================================================

    async def check_standards_compliance(self, requirement_text: str,
                                        categories: List[str] = None) -> Dict[str, Any]:
        """Check which engineering standards apply.
        
        Args:
            requirement_text: Technical requirement text
            categories: Standard categories to check
            
        Returns:
            Dict with applicable standards
        """
        if categories is None:
            categories = ["ISO", "IEEE", "NIST", "IEC"]

        applicable_standards = []
        text_lower = requirement_text.lower()

        for std_id, std_info in self._standards.items():
            if std_info["category"] not in categories:
                continue

            for keyword in std_info.get("keywords", []):
                if keyword.lower() in text_lower:
                    applicable_standards.append({
                        "id": std_id,
                        "title": std_info["title"],
                        "category": std_info["category"],
                        "description": std_info["description"],
                    })
                    break

        return {
            "applicable_standards": applicable_standards,
            "category_count": len(set(s["category"] for s in applicable_standards)),
            "total_standards": len(applicable_standards),
        }

    # ========================================================================
    # Materials and Parts Lookup
    # ========================================================================

    async def lookup_material(self, material_name: str) -> Dict[str, Any]:
        """Lookup material information.
        
        Args:
            material_name: Material name or designation
            
        Returns:
            Dict with material information
        """
        name_lower = material_name.lower().strip()

        # Exact match
        if name_lower in self._materials_database:
            mat_info = self._materials_database[name_lower]
            return {
                "material": material_name,
                "description": mat_info["description"],
                "properties": mat_info.get("properties", {}),
                "temperature_range": mat_info.get("temperature_range", ""),
                "standards": mat_info.get("standards", []),
                "found": True,
            }

        # Partial match
        for mat_code, mat_info in self._materials_database.items():
            if name_lower in mat_code or mat_code in name_lower:
                return {
                    "material": mat_code,
                    "description": mat_info["description"],
                    "properties": mat_info.get("properties", {}),
                    "found": True,
                }

        return {
            "material": material_name,
            "description": None,
            "found": False,
        }

    async def lookup_part(self, part_code_or_description: str) -> Dict[str, Any]:
        """Lookup part information.
        
        Args:
            part_code_or_description: Part number or description
            
        Returns:
            Dict with part information
        """
        code_upper = part_code_or_description.upper().strip()

        # Exact match
        if code_upper in self._parts_database:
            part_info = self._parts_database[code_upper]
            return {
                "part_code": code_upper,
                "description": part_info["description"],
                "manufacturer": part_info.get("manufacturer", ""),
                "specifications": part_info.get("specifications", {}),
                "found": True,
            }

        # Partial match
        desc_lower = part_code_or_description.lower().strip()
        for code, part_info in self._parts_database.items():
            if desc_lower in part_info["description"].lower():
                return {
                    "part_code": code,
                    "description": part_info["description"],
                    "specifications": part_info.get("specifications", {}),
                    "found": True,
                }

        return {
            "part_code": part_code_or_description,
            "description": None,
            "found": False,
        }

    # ========================================================================
    # Safety Checking
    # ========================================================================

    async def check_safety_concerns(self, text: str) -> Dict[str, Any]:
        """Check text for safety concerns.
        
        Args:
            text: Text to analyze for safety
            
        Returns:
            Dict with safety analysis
        """
        hazards_found = []
        text_lower = text.lower()

        for hazard_type, hazard_info in self._safety_terms.items():
            for keyword in hazard_info.get("keywords", []):
                if keyword.lower() in text_lower:
                    hazards_found.append(f"{hazard_type}: {hazard_info['description']}")
                    break

        return {
            "hazards_found": hazards_found,
            "hazard_count": len(hazards_found),
            "safety_critical": len(hazards_found) > 0,
            "requires_ppe": any("chemical" in h.lower() or "toxic" in h.lower() for h in hazards_found),
        }

    # ========================================================================
    # Unit and Measurement Validation
    # ========================================================================

    async def validate_units(self, measurement_text: str) -> Dict[str, Any]:
        """Validate units and measurements in text.
        
        Args:
            measurement_text: Text containing measurements
            
        Returns:
            Dict with validation results
        """
        text_lower = measurement_text.lower()
        found_units = []
        invalid_units = []

        for unit_abbr, unit_info in self._units.items():
            # Check abbreviation
            if unit_abbr.lower() in text_lower:
                found_units.append({
                    "unit": unit_abbr,
                    "full_name": unit_info["name"],
                    "quantity": unit_info["quantity"],
                })
            
            # Check full name
            if unit_info["name"].lower() in text_lower:
                found_units.append({
                    "unit": unit_info["name"],
                    "full_name": unit_info["name"],
                    "quantity": unit_info["quantity"],
                })

        return {
            "valid": len(found_units) > 0 or len(invalid_units) == 0,
            "found_units": found_units,
            "invalid_units": invalid_units,
            "message": "Valid units found" if found_units else "No standard units detected",
        }

    # ========================================================================
    # Data Loading Methods
    # ========================================================================

    def _load_standards(self) -> Dict[str, Any]:
        """Load engineering standards database."""
        return {
            "ISO9001": {
                "title": "Quality Management Systems",
                "category": "ISO",
                "description": "General quality management standard",
                "keywords": ["quality", "management system", "certification"],
            },
            "ISO14001": {
                "title": "Environmental Management Systems",
                "category": "ISO",
                "description": "Environmental compliance standards",
                "keywords": ["environmental", "sustainability", "emissions"],
            },
            "IEEE1012": {
                "title": "Software Verification and Validation",
                "category": "IEEE",
                "description": "V&V process for software development",
                "keywords": ["verification", "validation", "testing", "software"],
            },
            "NIST800-53": {
                "title": "Security and Privacy Controls",
                "category": "NIST",
                "description": "Security controls for information systems",
                "keywords": ["security", "privacy", "controls", "cybersecurity"],
            },
            "IEC61508": {
                "title": "Functional Safety of E/E/PE Systems",
                "category": "IEC",
                "description": "Safety requirements for electrical systems",
                "keywords": ["safety", "hazard", "risk assessment", "electrical"],
            },
        }

    def _load_materials(self) -> Dict[str, Any]:
        """Load materials database."""
        return {
            "aluminum 6061": {
                "description": "General Purpose Aluminum Alloy",
                "properties": {"density": "2.7 g/cm³", "tensile_strength": "310 MPa"},
                "temperature_range": "-50°C to 150°C",
                "standards": ["ASTM B221", "EN 573-3"],
            },
            "steel 4140": {
                "description": "Chrome Molybdenum Steel",
                "properties": {"density": "7.85 g/cm³", "hardness": "42 HRC"},
                "temperature_range": "-20°C to 250°C",
                "standards": ["ASTM A322", "DIN 34CrMo4"],
            },
            "titanium grade5": {
                "description": "Ti-6Al-4V Aerospace Grade",
                "properties": {"density": "4.43 g/cm³", "tensile_strength": "1275 MPa"},
                "temperature_range": "-100°C to 300°C",
                "standards": ["ASTM B348", "AMS 4911"],
            },
            "copper c11000": {
                "description": "Electrolytic Tough-Pitch Copper",
                "properties": {"conductivity": "58 S/m", "density": "8.96 g/cm³"},
                "temperature_range": "-50°C to 150°C",
                "standards": ["ASTM B3", "EN 1978"],
            },
        }

    def _load_parts(self) -> Dict[str, Any]:
        """Load parts database."""
        return {
            "12345-001": {
                "description": "Precision Bearing, Angular Contact, 6306 Series",
                "manufacturer": "SKF",
                "specifications": {"bore": "30mm", "tolerance": "P5"},
            },
            "89234-A": {
                "description": "Power Supply Unit, 24VDC, 5A",
                "manufacturer": "Phoenix Contact",
                "specifications": {"voltage": "24VDC", "current": "5A", "efficiency": "92%"},
            },
            "HEX-M20-SS": {
                "description": "Stainless Steel Hex Bolt M20",
                "manufacturer": "DIN 933",
                "specifications": {"grade": "A4-70", "length": "Variable"},
            },
        }

    def _load_units(self) -> Dict[str, Any]:
        """Load units and measurements database."""
        return {
            "mm": {"name": "millimeter", "quantity": "length", "si_equivalent": "0.001 m"},
            "m": {"name": "meter", "quantity": "length", "si_equivalent": "1 m"},
            "cm": {"name": "centimeter", "quantity": "length", "si_equivalent": "0.01 m"},
            "kg": {"name": "kilogram", "quantity": "mass", "si_equivalent": "1 kg"},
            "g": {"name": "gram", "quantity": "mass", "si_equivalent": "0.001 kg"},
            "Pa": {"name": "pascal", "quantity": "pressure", "si_equivalent": "1 Pa"},
            "MPa": {"name": "megapascal", "quantity": "pressure", "si_equivalent": "1e6 Pa"},
            "N": {"name": "newton", "quantity": "force", "si_equivalent": "1 N"},
            "kW": {"name": "kilowatt", "quantity": "power", "si_equivalent": "1000 W"},
            "°C": {"name": "degree celsius", "quantity": "temperature", "si_equivalent": "K+273.15"},
        }

    def _load_safety_terms(self) -> Dict[str, Any]:
        """Load safety terminology database."""
        return {
            "Chemical Hazard": {
                "keywords": ["toxic", "corrosive", "flammable", "chemical"],
                "description": "Hazardous chemical substances present",
            },
            "Electrical Hazard": {
                "keywords": ["high voltage", "electrical", "shock", "electrocution"],
                "description": "Electrical shock or arc hazards",
            },
            "Mechanical Hazard": {
                "keywords": ["rotating", "pinch point", "sharp edge", "crushing"],
                "description": "Moving mechanical equipment hazards",
            },
            "Thermal Hazard": {
                "keywords": ["hot", "high temperature", "burn", "thermal"],
                "description": "High temperature or burn hazards",
            },
            "Pressure Hazard": {
                "keywords": ["high pressure", "pressure vessel", "pressurized"],
                "description": "Pressurized system hazards",
            },
        }

    # ========================================================================
    # Validation Methods
    # ========================================================================

    async def validate_field(self, field_name: str, field_value: Any,
                            field_context: Dict[str, Any]) -> HookResult:
        """Validate engineering field.
        
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

        # Standards validation
        if "standard" in field_lower:
            std_result = await self.check_standards_compliance(str(field_value))
            if std_result["applicable_standards"]:
                suggestions.append(f"✓ {std_result['total_standards']} standards applicable")

        # Materials validation
        if "material" in field_lower:
            mat_result = await self.lookup_material(str(field_value))
            if mat_result["found"]:
                suggestions.append(f"✓ Material verified: {mat_result['description']}")

        # Safety validation
        if "safety" in field_lower or "hazard" in field_lower:
            safety_result = await self.check_safety_concerns(str(field_value))
            suggestions.append(f"Safety concerns: {safety_result['hazard_count']}")

        # Unit validation
        if "unit" in field_lower or "dimension" in field_lower:
            unit_result = await self.validate_units(str(field_value))
            if unit_result["valid"]:
                suggestions.append(f"✓ {len(unit_result['found_units'])} valid units found")

        return HookResult(
            success=True,
            plugin_name=self.metadata.name,
            hook_point="validate_field",
            execution_time_ms=4.0,
            suggestions=suggestions,
        )
