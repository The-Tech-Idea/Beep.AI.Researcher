"""Phase C.1 — PHI Redaction Service.

Provides regex-based scanning and in-place redaction of Protected Health
Information (PHI) from document text.  No external API calls — pure Python.

Supported entity types:
  SSN        — Social Security Numbers (XXX-XX-XXXX / XXXXXXXXX)
  MRN        — Medical Record Numbers (various hospital formats)
  PHONE      — US/international phone numbers
  EMAIL      — e-mail addresses
  DOB        — Dates of birth (many formats)
  INSURANCE  — Common health-insurance ID patterns
  PROVIDER   — NPI (National Provider Identifier)
  DATE       — Generic dates that may identify a patient
"""
from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────
#  PHI Pattern definitions
# ─────────────────────────────────────────────────────────────

@dataclass
class _Pattern:
    """Internal pattern container."""
    entity_type: str
    compiled: re.Pattern


_RAW_PATTERNS: List[Tuple[str, str]] = [
    # SSN — 123-45-6789 or 123456789
    ('SSN', r'\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b'),

    # US National Provider Identifier — 10-digit numbers preceded by NPI or followed by context
    ('NPI', r'\bNPI[\s:#-]*\d{10}\b|\b\d{10}\s*(?:NPI|npi)\b'),

    # Health insurance member IDs (common: "MEM", "ID:", letter+8-13 digits)
    ('INSURANCE_ID', r'\b(?:MEM|MEMID|MEMBER|INS|INSURANCE)[:\s#-]*[A-Z0-9\-]{6,20}\b'
                     r'|\b[A-Z]{2,4}\d{8,13}\b'),

    # Medical Record Numbers — 5-12 digits optionally preceded by MR#, MRN, etc.
    ('MRN', r'\bMR[N#]?[\s:#-]*\d{5,12}\b|\bmed(?:ical)?\s*rec(?:ord)?\s*(?:number|no\.?|#)?[\s:#-]*\d{5,12}\b'),

    # Dates of birth (many formats)
    ('DOB', (
        r'\bDOB[\s:#-]*\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b'
        r'|\bdate\s+of\s+birth[\s:#-]*\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b'
        r'|\bborn[\s:#:]*\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b'
    )),

    # Generic dates — MM/DD/YYYY, DD-MM-YYYY, YYYY-MM-DD
    ('DATE', r'\b\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}\b|\b\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}\b'),

    # US phone — (123) 456-7890, 123-456-7890, 123.456.7890, +11234567890
    ('PHONE', r'\b(?:\+1\s?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b'),

    # E-mail addresses
    ('EMAIL', r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'),

    # Full names heuristic — "John Smith" / "Dr. Smith" (rough approximation)
    # Kept deliberately conservative to avoid false positives
    ('PERSON_NAME', r'\b(?:Dr|Mr|Mrs|Ms|Miss|Prof)\.?\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b'),
]

_COMPILED: List[_Pattern] = [
    _Pattern(entity_type=et, compiled=re.compile(pat, re.IGNORECASE))
    for et, pat in _RAW_PATTERNS
]


# ─────────────────────────────────────────────────────────────
#  Public API
# ─────────────────────────────────────────────────────────────

@dataclass
class PhiFinding:
    """A single PHI detection result."""
    entity_type: str
    start: int
    end: int
    matched_text: str
    replacement: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return {
            'entity_type': self.entity_type,
            'start': self.start,
            'end': self.end,
            'matched_text': self.matched_text,
            'replacement': self.replacement,
        }


def scan_text(text: str) -> List[PhiFinding]:
    """Return a list of PHI findings in *text* without modifying it.

    Overlapping matches are deduplicated — the first-matched type wins.
    """
    if not text:
        return []

    findings: List[PhiFinding] = []
    occupied: set[Tuple[int, int]] = set()

    for pattern in _COMPILED:
        for m in pattern.compiled.finditer(text):
            s, e = m.start(), m.end()
            # Skip if this span overlaps an already-found span
            if any(os <= s < oe or os < e <= oe for (os, oe) in occupied):
                continue
            findings.append(PhiFinding(
                entity_type=pattern.entity_type,
                start=s, end=e,
                matched_text=m.group(),
            ))
            occupied.add((s, e))

    findings.sort(key=lambda f: f.start)
    return findings


def redact_text(
    text: str,
    replacement: str = '[REDACTED]',
    entity_types: Optional[List[str]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Redact PHI from *text*.

    Returns:
        (redacted_text, redaction_map)
        - redacted_text: text with PHI replaced by *replacement*
        - redaction_map: list of PhiFinding dicts with the replacement included
    """
    if not text:
        return text, []

    findings = scan_text(text)

    # Optionally filter to requested entity types
    if entity_types:
        upper = {t.upper() for t in entity_types}
        findings = [f for f in findings if f.entity_type.upper() in upper]

    # Build redacted string by iterating findings in reverse order
    result = text
    redaction_map: List[Dict[str, Any]] = []

    for f in reversed(findings):
        repl = replacement
        f.replacement = repl
        result = result[:f.start] + repl + result[f.end:]
        redaction_map.append(f.to_dict())

    redaction_map.sort(key=lambda d: d['start'])
    return result, redaction_map


def redact_document(document, replacement: str = '[REDACTED]') -> Dict[str, Any]:
    """Redact PHI from a ``ResearcherDocument`` instance in place.

    Saves the original text in ``phi_backup_json`` if the attribute exists,
    then writes the redacted text to ``text_content``.

    Returns a summary dict.
    """
    original = document.text_content or ''
    if not original:
        return {'status': 'skipped', 'reason': 'no text_content', 'findings_count': 0}

    redacted, redaction_map = redact_text(original, replacement=replacement)

    # Backup original text if model supports it
    if hasattr(document, 'phi_backup_json') and not getattr(document, 'phi_backup_json', None):
        document.phi_backup_json = {'original_text': original, 'redacted_at': None}

    document.text_content = redacted

    if hasattr(document, 'phi_detected'):
        document.phi_detected = bool(redaction_map)
    if hasattr(document, 'phi_redacted'):
        document.phi_redacted = True

    return {
        'status': 'ok',
        'findings_count': len(redaction_map),
        'entity_type_counts': _count_by_type(redaction_map),
        'redaction_map': redaction_map,
    }


def phi_report(text: str) -> Dict[str, Any]:
    """Generate a PHI scan report for *text* without modifying it."""
    findings = scan_text(text)
    return {
        'phi_found': bool(findings),
        'total_findings': len(findings),
        'entity_type_counts': _count_by_type([f.to_dict() for f in findings]),
        'findings': [f.to_dict() for f in findings],
    }


def _count_by_type(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for f in findings:
        et = f.get('entity_type', 'UNKNOWN')
        counts[et] = counts.get(et, 0) + 1
    return counts
