"""Government domain plugin (Phase C.2).

Hooks: CFR/USC citation parsing, public-comment sentiment analysis,
agency registry matching, and FOIA request classification.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.plugin_base import PluginBase, PluginMetadata, HookContext, HookResult

logger = logging.getLogger(__name__)


# ─── Federal Register citation patterns ──────────────────────

# CFR: 45 C.F.R. § 164.502  or  45 CFR 164.502
_CFR_RE = re.compile(
    r'(\d+)\s*C\.?F\.?R\.?\s*(?:§|sec(?:tion)?\.?)?\s*(\d+(?:\.\d+)*)',
    re.IGNORECASE,
)

# USC: 5 U.S.C. § 552  or  5 USC 552
_USC_RE = re.compile(
    r'(\d+)\s*U\.?S\.?C\.?\s*(?:§|sec(?:tion)?\.?)?\s*(\d+[a-z]?(?:-\d+)?)',
    re.IGNORECASE,
)

# FOIA exemptions (b)(1)-(b)(9)
_FOIA_EXEMPTION_RE = re.compile(r'\(b\)\(([1-9])\)', re.IGNORECASE)

# Federal agencies (partial list)
FEDERAL_AGENCIES: Dict[str, str] = {
    'HHS': 'Department of Health and Human Services',
    'DOE': 'Department of Energy',
    'EPA': 'Environmental Protection Agency',
    'FDA': 'Food and Drug Administration',
    'FTC': 'Federal Trade Commission',
    'SEC': 'Securities and Exchange Commission',
    'FCC': 'Federal Communications Commission',
    'USDA': 'Department of Agriculture',
    'DOJ': 'Department of Justice',
    'DHS': 'Department of Homeland Security',
    'DOD': 'Department of Defense',
    'DOS': 'Department of State',
    'DOT': 'Department of Transportation',
    'ED': 'Department of Education',
    'SBA': 'Small Business Administration',
    'OPM': 'Office of Personnel Management',
}


class GovernmentPlugin(PluginBase):
    """Government / public-sector domain plugin."""

    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)

    # ── Required lifecycle hooks ─────────────────────────────

    async def on_plugin_load(self, context: HookContext) -> HookResult:
        logger.info("GovernmentPlugin loaded")
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
        field_name = context.data.get('field_name', '').lower()
        field_value = str(context.data.get('extracted_value', ''))
        suggestions: List[str] = []

        if 'citation' in field_name or 'regulation' in field_name or 'cfr' in field_name:
            citations = self.parse_cfr_citations(field_value)
            for c in citations:
                suggestions.append(f"CFR: {c['title_number']} C.F.R. § {c['section']}")

        if 'agency' in field_name:
            matched = self.match_agency(field_value)
            if matched:
                suggestions.append(f"Agency: {matched}")

        return HookResult(
            success=True, plugin_name=self.metadata.name,
            hook_point=context.hook_point, execution_time_ms=2.0,
            data={'suggestions': suggestions}, suggestions=suggestions,
        )

    async def on_document_upload(self, context: HookContext) -> HookResult:
        text = context.data.get('text_content', '')
        cfr = self.parse_cfr_citations(text)
        usc = self.parse_usc_citations(text)
        agencies = self.extract_agency_mentions(text)
        foia_exempt = self.detect_foia_exemptions(text)
        return HookResult(
            success=True, plugin_name=self.metadata.name,
            hook_point=context.hook_point, execution_time_ms=12.0,
            data={
                'cfr_citations': cfr,
                'usc_citations': usc,
                'agencies_mentioned': agencies,
                'foia_exemptions': foia_exempt,
            },
        )

    async def on_document_analysis(self, context: HookContext) -> HookResult:
        return await self.on_document_upload(context)

    # ── Domain helpers ───────────────────────────────────────

    def parse_cfr_citations(self, text: str) -> List[Dict[str, str]]:
        """Extract CFR citations from text."""
        results = []
        for m in _CFR_RE.finditer(text):
            results.append({
                'title_number': m.group(1),
                'section': m.group(2),
                'raw': m.group(0),
            })
        return results

    def parse_usc_citations(self, text: str) -> List[Dict[str, str]]:
        """Extract U.S.C. citations from text."""
        results = []
        for m in _USC_RE.finditer(text):
            results.append({
                'title_number': m.group(1),
                'section': m.group(2),
                'raw': m.group(0),
            })
        return results

    def extract_agency_mentions(self, text: str) -> List[Dict[str, str]]:
        """Find federal agency acronyms mentioned in text."""
        found = []
        for acronym, full_name in FEDERAL_AGENCIES.items():
            pattern = r'\b' + re.escape(acronym) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                found.append({'acronym': acronym, 'full_name': full_name})
        return found

    def match_agency(self, text: str) -> Optional[str]:
        """Return the full agency name for an acronym, or None."""
        upper = text.strip().upper()
        return FEDERAL_AGENCIES.get(upper)

    def detect_foia_exemptions(self, text: str) -> List[str]:
        """Return list of cited FOIA exemptions (e.g. '(b)(1)')."""
        return [f'(b)({m.group(1)})' for m in _FOIA_EXEMPTION_RE.finditer(text)]

    def classify_public_comment_sentiment(self, text: str) -> str:
        """Very simple sentiment classifier for public comments: support|oppose|neutral."""
        lower = text.lower()
        support_words = ['support', 'agree', 'favor', 'endorse', 'approve', 'welcome', 'urge adoption']
        oppose_words = ['oppose', 'disagree', 'object', 'reject', 'against', 'harmful', 'urge withdrawal']
        s_score = sum(1 for w in support_words if w in lower)
        o_score = sum(1 for w in oppose_words if w in lower)
        if s_score > o_score:
            return 'support'
        if o_score > s_score:
            return 'oppose'
        return 'neutral'
