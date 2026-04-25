"""Education domain plugin (Phase C.2).

Hooks: citation format validation (APA/MLA/Chicago), research methodology
classification, FERPA-sensitive term detection, and Bloom's taxonomy tagging.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.services.plugin_base import PluginBase, PluginMetadata, HookContext, HookResult

logger = logging.getLogger(__name__)


# ─── FERPA sensitive terms ────────────────────────────────────

FERPA_TERMS: List[str] = [
    'student id', 'student number', 'enrollment status', 'grades', 'transcript',
    'gpa', 'grade point', 'disciplinary record', 'special education',
    'iep', 'individualized education', '504 plan', 'financial aid',
    'tuition', 'attendance record', 'student address', 'date of birth',
]

# ─── Citation patterns ────────────────────────────────────────

# APA: Author, A. A. (Year). Title. Journal, vol(issue), pages.
_APA_RE = re.compile(
    r'[A-Z][a-z]+,\s+[A-Z]\.(?:\s+[A-Z]\.)?'  # Author last, Initials
    r'\s+\(\d{4}\)\.\s+'                        # (Year).
    r'.{10,}',                                  # Rest of citation
    re.DOTALL,
)

# MLA: Author Last, First. "Title." Journal vol.issue (year): pages.
_MLA_RE = re.compile(
    r'[A-Z][a-z]+,\s+[A-Z][a-z]+\.'
    r'\s+"[^"]+\."\s+\w+',
    re.DOTALL,
)

# Bloom's taxonomy levels
BLOOMS_KEYWORDS: Dict[str, List[str]] = {
    'remember': ['define', 'list', 'recall', 'state', 'repeat', 'identify'],
    'understand': ['explain', 'describe', 'summarize', 'paraphrase', 'classify'],
    'apply': ['apply', 'demonstrate', 'use', 'solve', 'illustrate'],
    'analyze': ['analyze', 'compare', 'contrast', 'differentiate', 'examine'],
    'evaluate': ['evaluate', 'justify', 'critique', 'defend', 'support'],
    'create': ['create', 'design', 'construct', 'develop', 'compose'],
}

# Research methodology keywords
METHODOLOGY_KEYWORDS: Dict[str, List[str]] = {
    'qualitative': ['thematic analysis', 'grounded theory', 'ethnography',
                    'case study', 'phenomenology', 'interview', 'focus group'],
    'quantitative': ['regression', 'correlation', 'anova', 'survey', 'experiment',
                     'chi-square', 'statistical', 'sample size', 'randomized'],
    'mixed_methods': ['mixed methods', 'triangulation', 'concurrent design',
                      'sequential explanatory', 'convergent'],
    'systematic_review': ['systematic review', 'meta-analysis', 'prisma',
                          'literature review', 'scoping review'],
}


class EducationPlugin(PluginBase):
    """Education domain plugin."""

    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)

    # ── Required lifecycle hooks ─────────────────────────────

    async def on_plugin_load(self, context: HookContext) -> HookResult:
        logger.info("EducationPlugin loaded")
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

        if 'citation' in field_name or 'reference' in field_name:
            citation_type = self.detect_citation_style(field_value)
            if citation_type:
                suggestions.append(f"Detected citation style: {citation_type}")

        return HookResult(
            success=True, plugin_name=self.metadata.name,
            hook_point=context.hook_point, execution_time_ms=2.0,
            data={'suggestions': suggestions}, suggestions=suggestions,
        )

    async def on_document_upload(self, context: HookContext) -> HookResult:
        text = context.data.get('text_content', '')
        ferpa = self.detect_ferpa_terms(text)
        methodology = self.classify_methodology(text)
        return HookResult(
            success=True, plugin_name=self.metadata.name,
            hook_point=context.hook_point, execution_time_ms=10.0,
            data={
                'ferpa_terms_detected': ferpa,
                'methodology': methodology,
                'contains_student_data': bool(ferpa),
            },
        )

    async def on_document_analysis(self, context: HookContext) -> HookResult:
        return await self.on_document_upload(context)

    # ── Domain helpers ───────────────────────────────────────

    def detect_citation_style(self, text: str) -> Optional[str]:
        """Heuristically detect APA, MLA, or Chicago style."""
        if _APA_RE.search(text):
            return 'APA'
        if _MLA_RE.search(text):
            return 'MLA'
        # Chicago: numbered footnotes (1. Author, "Title," …)
        if re.search(r'^\s*\d+\.\s+[A-Z]', text, re.MULTILINE):
            return 'Chicago'
        return None

    def format_citation_apa(self, author: str, year: int, title: str,
                             journal: str, volume: Optional[str] = None,
                             issue: Optional[str] = None, pages: Optional[str] = None) -> str:
        """Generate a basic APA citation string."""
        vol_part = f', {volume}' if volume else ''
        iss_part = f'({issue})' if issue else ''
        pages_part = f', {pages}' if pages else ''
        return f'{author} ({year}). {title}. {journal}{vol_part}{iss_part}{pages_part}.'

    def detect_ferpa_terms(self, text: str) -> List[str]:
        """Return FERPA-sensitive terms found in text."""
        lower = text.lower()
        return [term for term in FERPA_TERMS if term in lower]

    def classify_methodology(self, text: str) -> Optional[str]:
        """Return the most likely research methodology, or None."""
        lower = text.lower()
        scores: Dict[str, int] = {}
        for methodology, keywords in METHODOLOGY_KEYWORDS.items():
            scores[methodology] = sum(1 for kw in keywords if kw in lower)
        if not any(scores.values()):
            return None
        return max(scores, key=lambda k: scores[k])

    def tag_blooms_level(self, text: str) -> Optional[str]:
        """Return the best-matching Bloom's taxonomy level for text."""
        lower = text.lower()
        scores: Dict[str, int] = {}
        for level, keywords in BLOOMS_KEYWORDS.items():
            scores[level] = sum(1 for kw in keywords if kw in lower)
        if not any(scores.values()):
            return None
        return max(scores, key=lambda k: scores[k])
