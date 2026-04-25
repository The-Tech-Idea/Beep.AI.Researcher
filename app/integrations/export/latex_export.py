"""
LaTeX Export — Generate .tex files with BibTeX bibliography.

Exports project reports as LaTeX documents with properly formatted
citations and a companion .bib file.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from ..base_connector import ConnectorInfo, ConnectorType
from .base_export import BaseExportProvider

logger = logging.getLogger(__name__)


class LaTeXExportProvider(BaseExportProvider):
    """
    Export research content as LaTeX + BibTeX.

    No external service needed — this is a local format converter.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config=config)

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="latex",
            display_name="LaTeX / BibTeX",
            connector_type=ConnectorType.EXPORT,
            description="Export reports as LaTeX documents with BibTeX bibliography",
            requires_auth=False,
        )

    def _do_connect(self, credentials: Dict[str, Any]) -> bool:
        return True

    def _do_disconnect(self) -> None:
        pass

    def _do_test(self) -> bool:
        return True

    def get_file_extension(self) -> str:
        return ".tex"

    def get_mime_type(self) -> str:
        return "application/x-latex"

    # ── Export ────────────────────────────────────────────────────────

    def export_report(self, project_data: Dict[str, Any]) -> str:
        """
        Export project as a LaTeX document.

        project_data keys:
            title, author, date, content (HTML or plain text),
            references (list of dicts), codes (list of dicts)
        """
        title = self._escape(project_data.get("title", "Untitled Research Report"))
        author = self._escape(project_data.get("author", ""))
        date = project_data.get("date", r"\today")
        content = project_data.get("content", "")

        # Convert HTML content to LaTeX
        latex_body = self._html_to_latex(content)

        # Build document
        doc = rf"""\documentclass[12pt,a4paper]{{article}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{amsmath,amssymb}}
\usepackage{{graphicx}}
\usepackage{{hyperref}}
\usepackage{{natbib}}
\usepackage{{geometry}}
\geometry{{margin=1in}}

\title{{{title}}}
\author{{{author}}}
\date{{{date}}}

\begin{{document}}

\maketitle

{latex_body}

\bibliographystyle{{apalike}}
\bibliography{{references}}

\end{{document}}
"""
        return doc

    def export_references(self, references: List[Dict[str, Any]],
                          style: str = "bibtex") -> str:
        """Export references as a .bib BibTeX file."""
        entries = []
        for i, ref in enumerate(references):
            entry = self._to_bibtex_entry(ref, i)
            if entry:
                entries.append(entry)
        return "\n\n".join(entries) + "\n"

    # ── BibTeX generation ────────────────────────────────────────────

    def _to_bibtex_entry(self, ref: Dict[str, Any], index: int) -> str:
        """Convert a reference dict to a BibTeX entry."""
        # Generate citation key
        authors = ref.get("authors", [])
        year = ref.get("year") or ref.get("publication_date", "")[:4] or "nd"
        if authors:
            first_author = authors[0].split()[-1].lower()  # last name
        else:
            first_author = "unknown"
        cite_key = re.sub(r'[^a-z0-9]', '', f"{first_author}{year}_{index}")

        # Determine entry type
        source_type = ref.get("source_type", "article").lower()
        type_map = {
            "article": "article",
            "journal_article": "article",
            "book": "book",
            "chapter": "incollection",
            "book_chapter": "incollection",
            "conference": "inproceedings",
            "conference_paper": "inproceedings",
            "thesis": "phdthesis",
            "report": "techreport",
        }
        bib_type = type_map.get(source_type, "misc")

        # Build fields
        fields = []
        title = ref.get("title", "Untitled")
        fields.append(f"  title = {{{self._escape(title)}}}")

        if authors:
            bib_authors = " and ".join(self._escape(a) for a in authors)
            fields.append(f"  author = {{{bib_authors}}}")

        if year != "nd":
            fields.append(f"  year = {{{year}}}")

        journal = ref.get("journal", "") or ref.get("publication_title", "")
        if journal:
            fields.append(f"  journal = {{{self._escape(journal)}}}")

        doi = ref.get("doi", "")
        if doi:
            fields.append(f"  doi = {{{doi}}}")

        url = ref.get("url", "")
        if url:
            fields.append(f"  url = {{{url}}}")

        volume = ref.get("volume", "")
        if volume:
            fields.append(f"  volume = {{{volume}}}")

        pages = ref.get("pages", "")
        if pages:
            fields.append(f"  pages = {{{pages}}}")

        fields_str = ",\n".join(fields)
        return f"@{bib_type}{{{cite_key},\n{fields_str}\n}}"

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _escape(text: str) -> str:
        """Escape LaTeX special characters."""
        if not text:
            return ""
        chars = {
            '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
            '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}',
            '^': r'\textasciicircum{}',
        }
        for ch, replacement in chars.items():
            text = text.replace(ch, replacement)
        return text

    @staticmethod
    def _html_to_latex(html: str) -> str:
        """Simple HTML → LaTeX converter."""
        if not html:
            return ""

        text = html
        # Headers
        text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\\section{\1}', text, flags=re.DOTALL)
        text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\\subsection{\1}', text, flags=re.DOTALL)
        text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\\subsubsection{\1}', text, flags=re.DOTALL)

        # Bold / Italic
        text = re.sub(r'<(strong|b)>(.*?)</\1>', r'\\textbf{\2}', text, flags=re.DOTALL)
        text = re.sub(r'<(em|i)>(.*?)</\1>', r'\\textit{\2}', text, flags=re.DOTALL)

        # Lists
        text = re.sub(r'<ul[^>]*>', r'\\begin{itemize}', text)
        text = re.sub(r'</ul>', r'\\end{itemize}', text)
        text = re.sub(r'<ol[^>]*>', r'\\begin{enumerate}', text)
        text = re.sub(r'</ol>', r'\\end{enumerate}', text)
        text = re.sub(r'<li[^>]*>(.*?)</li>', r'\\item \1', text, flags=re.DOTALL)

        # Paragraphs / line breaks
        text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL)
        text = re.sub(r'<br\s*/?>', r'\\\\\n', text)

        # Remove remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Clean multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()
