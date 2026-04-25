"""Real Estate domain plugin (Phase C.2).

Hooks: zoning classification, cap-rate calculation, lease-term extraction,
title-defect detection, and address normalization.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.services.plugin_base import PluginBase, PluginMetadata, HookContext, HookResult

logger = logging.getLogger(__name__)


# ─── Quick-reference data ────────────────────────────────────

ZONING_CODES: Dict[str, str] = {
    'R1': 'Single-Family Residential', 'R2': 'Two-Family Residential',
    'R3': 'Multi-Family Residential', 'R4': 'High-Density Residential',
    'C1': 'Neighborhood Commercial', 'C2': 'General Commercial',
    'C3': 'Heavy Commercial', 'I1': 'Light Industrial',
    'I2': 'General Industrial', 'I3': 'Heavy Industrial',
    'MX': 'Mixed Use', 'AG': 'Agricultural', 'OS': 'Open Space',
    'PD': 'Planned Development',
}

TITLE_DEFECT_KEYWORDS: List[str] = [
    'encumbrance', 'lien', 'easement', 'deed restriction', 'lis pendens',
    'cloud on title', 'judgment lien', 'tax lien', 'mechanic lien',
    'undisclosed heir', 'forgery', 'fraud', 'adverse claim', 'boundary dispute',
]


class RealEstatePlugin(PluginBase):
    """Real estate domain plugin."""

    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)

    # ── Required lifecycle hooks ─────────────────────────────

    async def on_plugin_load(self, context: HookContext) -> HookResult:
        logger.info("RealEstatePlugin loaded")
        return HookResult(
            success=True, plugin_name=self.metadata.name,
            hook_point=context.hook_point, execution_time_ms=5.0,
        )

    async def on_plugin_unload(self, context: HookContext) -> HookResult:
        return HookResult(
            success=True, plugin_name=self.metadata.name,
            hook_point=context.hook_point, execution_time_ms=1.0,
        )

    async def on_extraction(self, context: HookContext) -> HookResult:
        """Enrich extracted real-estate fields."""
        field_name = context.data.get('field_name', '').lower()
        field_value = str(context.data.get('extracted_value', ''))
        suggestions: List[str] = []

        if 'zoning' in field_name:
            zoning_info = self.classify_zoning(field_value)
            if zoning_info.get('description'):
                suggestions.append(f"Zoning: {zoning_info['description']}")

        if 'address' in field_name:
            normalized = self.normalize_address(field_value)
            if normalized:
                suggestions.append(f"Normalized: {normalized}")

        return HookResult(
            success=True, plugin_name=self.metadata.name,
            hook_point=context.hook_point, execution_time_ms=2.0,
            data={'suggestions': suggestions}, suggestions=suggestions,
        )

    async def on_document_upload(self, context: HookContext) -> HookResult:
        """Scan document for title defects and leases."""
        text = context.data.get('text_content', '')
        defects = self.detect_title_defects(text)
        leases = self.extract_lease_terms(text)
        return HookResult(
            success=True, plugin_name=self.metadata.name,
            hook_point=context.hook_point, execution_time_ms=10.0,
            data={'title_defects': defects, 'lease_terms': leases},
        )

    async def on_document_analysis(self, context: HookContext) -> HookResult:
        return await self.on_document_upload(context)

    # ── Domain helpers ───────────────────────────────────────

    def classify_zoning(self, code: str) -> Dict[str, Any]:
        """Look up a zoning code description."""
        normalized = code.strip().upper()
        description = ZONING_CODES.get(normalized, '')
        return {
            'code': normalized,
            'description': description,
            'is_residential': normalized.startswith('R'),
            'is_commercial': normalized.startswith('C'),
            'is_industrial': normalized.startswith('I'),
        }

    def calculate_cap_rate(self, noi: float, property_value: float) -> Optional[float]:
        """Return cap rate as a percentage, or None if inputs invalid."""
        if not property_value:
            return None
        return round((noi / property_value) * 100, 2)

    def detect_title_defects(self, text: str) -> List[str]:
        """Return list of title-defect keywords found in text (case-insensitive)."""
        found = []
        lower_text = text.lower()
        for kw in TITLE_DEFECT_KEYWORDS:
            if kw in lower_text:
                found.append(kw)
        return found

    def extract_lease_terms(self, text: str) -> Dict[str, Any]:
        """Extract basic lease term indicators from text."""
        results: Dict[str, Any] = {}

        # Monthly rent
        rent_m = re.search(r'\$[\d,]+(?:\.\d{2})?\s*(?:per|/)\s*month', text, re.IGNORECASE)
        if rent_m:
            results['monthly_rent_text'] = rent_m.group()

        # Lease duration
        dur_m = re.search(r'(\d+)[\s-]*(year|month|day)s?\s*(?:lease|term)', text, re.IGNORECASE)
        if dur_m:
            results['duration'] = f"{dur_m.group(1)} {dur_m.group(2)}(s)"

        # Renewal option
        if re.search(r'option\s+to\s+renew|renewal\s+option', text, re.IGNORECASE):
            results['renewal_option'] = True

        return results

    def normalize_address(self, address: str) -> str:
        """Minimal address normalization: expand common abbreviations."""
        ABBREV = {
            r'\bSt\b': 'Street', r'\bAve\b': 'Avenue', r'\bBlvd\b': 'Boulevard',
            r'\bDr\b': 'Drive', r'\bRd\b': 'Road', r'\bLn\b': 'Lane',
            r'\bCt\b': 'Court', r'\bPl\b': 'Place', r'\bN\b': 'North',
            r'\bS\b': 'South', r'\bE\b': 'East', r'\bW\b': 'West',
        }
        result = address.strip()
        for pattern, expansion in ABBREV.items():
            result = re.sub(pattern, expansion, result)
        return result
