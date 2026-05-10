"""Deterministic citation formatter for project references (Phase 06).

Wraps the Reference model's ``to_apa`` / ``to_mla`` / ``to_chicago`` /
``to_bibtex`` methods and adds convenience batch operations used by the
report-writing routes.  LLM is intentionally NOT used here — output is
reproducible and easier to test.

Supported styles: ``apa``, ``mla``, ``chicago``, ``bibtex``.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.models.researcher.researcher_references import Reference

# Styles offered to callers.
SUPPORTED_STYLES = ("apa", "mla", "chicago", "bibtex")

# CSL style registry — 50+ academic styles grouped by field
CSL_STYLES = {
    # Social Sciences
    "apa": "APA 7th",
    "asa": "ASA",
    "apsa": "APSA",
    # Humanities
    "mla": "MLA 9th",
    "chicago": "Chicago 17th",
    "mhra": "MHRA",
    "turabian": "Turabian",
    # Medicine / Health
    "vancouver": "Vancouver",
    "ama": "AMA",
    "jama": "JAMA",
    "bmj": "BMJ",
    "lancet": "The Lancet",
    "nejm": "NEJM",
    "nursing": "Nursing",
    # Science / Engineering
    "ieee": "IEEE",
    "nature": "Nature",
    "cell": "Cell",
    "science": "Science",
    "acm": "ACM",
    "aps": "APS",
    "acs": "ACS",
    "aiaa": "AIAA",
    # Law
    "bluebook": "Bluebook",
    "oscola": "OSCOLA",
    # Education
    "apa-ed": "APA Education",
    "harvard": "Harvard",
    "harvard-anglia": "Harvard (Anglia)",
    "harvard-leeds": "Harvard (Leeds)",
    "harvard-uwe": "Harvard (UWE)",
    "harvard-westernsyd": "Harvard (Western Syd)",
    # Business
    "apa-bus": "APA Business",
    "jbl": "Journal of Business Logistics",
    # General / International
    "iso690": "ISO 690",
    "gb7714": "GB/T 7714",
    "din1505": "DIN 1505",
    "gost": "GOST",
    "council-of-science-editors": "CSE",
    "elsevier-harvard": "Elsevier Harvard",
    "elsevier-vancouver": "Elsevier Vancouver",
    "springer-basic": "Springer Basic",
    "springer-lncs": "Springer LNCS",
    "taylor-francis-harvard": "Taylor & Francis Harvard",
    "sage-harvard": "SAGE Harvard",
    "copernicus": "Copernicus",
    "frontiers": "Frontiers",
    "mdpi": "MDPI",
    "peerj": "PeerJ",
    "plos": "PLOS",
    "rsc": "RSC",
}


# ---------------------------------------------------------------------------
# Single-reference formatting
# ---------------------------------------------------------------------------


def format_reference(ref: Reference, style: str) -> str:
    """Return a formatted citation string for *ref* in the requested *style*.

    Falls back gracefully if the model method raises — the caller always gets
    a string back.
    """
    style = (style or "apa").lower()
    try:
        if style == "apa":
            return ref.to_apa()
        if style == "mla":
            return ref.to_mla()
        if style == "chicago":
            return ref.to_chicago()
        if style == "bibtex":
            return ref.to_bibtex()
    except Exception:
        pass
    # Generic fallback — at minimum return author + year + title
    authors = ref.get_authors()
    first_author = authors[0] if authors else "Unknown"
    year = ref.year or "n.d."
    return f"{first_author} ({year}). {ref.title}."


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------


def format_reference_list(
    refs: List[Reference],
    style: str,
    sort: bool = True,
) -> List[Dict[str, Any]]:
    """Format a list of references.

    Returns a list of dicts::

        [{"id": 1, "citation_key": "Smith2020", "formatted": "Smith, J. (2020)…"}, …]

    If *sort* is True the list is sorted alphabetically by the formatted text
    (standard for APA/MLA/Chicago reference lists).
    """
    results = [
        {
            "id": ref.id,
            "citation_key": ref.citation_key,
            "formatted": format_reference(ref, style),
        }
        for ref in refs
    ]
    if sort and style != "bibtex":
        results.sort(key=lambda r: r["formatted"].lower())
    return results


# ---------------------------------------------------------------------------
# Citation-key scanner
# ---------------------------------------------------------------------------

# Matches common author-year in-text patterns:
#   (Smith, 2020)  (Smith et al., 2020)  Smith (2020)  [Smith 2020]
_AUTHOR_YEAR_RE = re.compile(
    r"[\(\[]?\s*([A-Z][A-Za-z'\-]+(?:\s+et\s+al\.?)?)"  # author part
    r"[,\s]+(\d{4}(?:[a-z])?)\s*[\)\]]?",  # year part
    re.UNICODE,
)


def scan_citation_markers(
    text: str,
    project_refs: List[Reference],
) -> Dict[str, Any]:
    """Scan *text* for author-year citation markers and match against library.

    Returns::

        {
            "markers": [
                {
                    "raw": "(Smith, 2020)",
                    "author": "Smith",
                    "year": "2020",
                    "matched_ref_id": 3,          // null if no match
                    "matched_citation_key": "Smith2020",
                }
            ],
            "unmatched_count": 1,
            "matched_count": 2,
        }
    """
    # Build a lookup: (lowercased-last-name, year) → ref
    _ref_index: Dict[Tuple[str, str], Reference] = {}
    for ref in project_refs:
        authors = ref.get_authors()
        if not authors or not ref.year:
            continue
        raw_first = authors[0]
        # Last name: take last token if comma-separated or space-separated
        if "," in raw_first:
            last = raw_first.split(",")[0].strip()
        else:
            last = raw_first.strip().split()[-1]
        _ref_index[(last.lower(), str(ref.year))] = ref

    markers = []
    for m in _AUTHOR_YEAR_RE.finditer(text):
        raw = m.group(0).strip()
        author_part = m.group(1).strip()
        year_part = m.group(2).strip()

        # Normalise author token (strip "et al.")
        base_author = re.sub(r"\s+et\s+al\.?", "", author_part, flags=re.I).strip()
        last_tok = base_author.split()[-1] if base_author.split() else base_author

        matched = _ref_index.get((last_tok.lower(), year_part))
        markers.append(
            {
                "raw": raw,
                "author": author_part,
                "year": year_part,
                "matched_ref_id": matched.id if matched else None,
                "matched_citation_key": matched.citation_key if matched else None,
            }
        )

    unmatched = sum(1 for r in markers if r["matched_ref_id"] is None)
    return {
        "markers": markers,
        "unmatched_count": unmatched,
        "matched_count": len(markers) - unmatched,
    }
