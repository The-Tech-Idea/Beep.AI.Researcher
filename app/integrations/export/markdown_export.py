"""
Markdown Export — Export projects as structured Markdown (Obsidian-compatible).

Generates a Markdown document with YAML frontmatter, structured sections,
and linked references compatible with Obsidian vaults and static site generators.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from app.core.time_utils import utcnow_naive
from typing import Any, Dict, List, Optional

from ..base_connector import ConnectorInfo, ConnectorType
from .base_export import BaseExportProvider

logger = logging.getLogger(__name__)


class MarkdownExportProvider(BaseExportProvider):
    """
    Export research content as structured Markdown.

    Features:
    - YAML frontmatter with metadata
    - Obsidian-compatible [[wiki-links]] for references
    - Structured sections: Summary, Findings, References, Codes
    - Clean HTML → Markdown conversion
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config=config)

    @property
    def info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="markdown",
            display_name="Markdown (Obsidian)",
            connector_type=ConnectorType.EXPORT,
            description="Export as structured Markdown with YAML frontmatter",
            requires_auth=False,
        )

    def _do_connect(self, credentials: Dict[str, Any]) -> bool:
        return True

    def _do_disconnect(self) -> None:
        pass

    def _do_test(self) -> bool:
        return True

    def get_file_extension(self) -> str:
        return ".md"

    def get_mime_type(self) -> str:
        return "text/markdown"

    # ── Export ────────────────────────────────────────────────────────

    def export_report(self, project_data: Dict[str, Any]) -> str:
        """
        Export project as Markdown with YAML frontmatter.

        project_data keys:
            title, author, date, content, references, codes, tags
        """
        title = project_data.get("title", "Untitled Research Report")
        author = project_data.get("author", "")
        date = project_data.get("date", utcnow_naive().strftime("%Y-%m-%d"))
        tags = project_data.get("tags", [])
        content = project_data.get("content", "")
        references = project_data.get("references", [])
        codes = project_data.get("codes", [])

        # YAML frontmatter
        tag_str = "\n".join(f"  - {t}" for t in tags) if tags else "  - research"
        frontmatter = f"""---
title: "{title}"
author: "{author}"
date: {date}
type: research-report
tags:
{tag_str}
---
"""

        # Convert content
        md_body = self._html_to_markdown(content) if content else ""

        # Build sections
        sections = [frontmatter, f"# {title}\n"]

        if md_body:
            sections.append(md_body)

        # Codes section
        if codes:
            sections.append("\n## Theme Codes\n")
            for code in codes:
                name = code.get("name", "")
                desc = code.get("description", "")
                count = code.get("reference_count", 0)
                sections.append(f"- **{name}** ({count} references) — {desc}")

        # References section
        if references:
            sections.append("\n## References\n")
            for i, ref in enumerate(references, 1):
                line = self._format_reference_md(ref, i)
                sections.append(line)

        return "\n".join(sections) + "\n"

    def export_references(self, references: List[Dict[str, Any]],
                          style: str = "apa") -> str:
        """Export references as a Markdown list."""
        lines = ["# References\n"]
        for i, ref in enumerate(references, 1):
            lines.append(self._format_reference_md(ref, i))
        return "\n".join(lines) + "\n"

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _format_reference_md(ref: Dict[str, Any], index: int) -> str:
        """Format a single reference as a Markdown list item."""
        authors = ref.get("authors", [])
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."

        title = ref.get("title", "Untitled")
        year = ref.get("year") or ref.get("publication_date", "")[:4] or "n.d."
        journal = ref.get("journal", "") or ref.get("publication_title", "")
        doi = ref.get("doi", "")
        url = ref.get("url", "")

        line = f"{index}. {author_str} ({year}). **{title}**."
        if journal:
            line += f" *{journal}*."
        if doi:
            line += f" [doi:{doi}](https://doi.org/{doi})"
        elif url:
            line += f" [{url}]({url})"

        return line

    @staticmethod
    def _html_to_markdown(html: str) -> str:
        """Convert HTML content to clean Markdown."""
        if not html:
            return ""

        text = html

        # Headers
        text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', text, flags=re.DOTALL)
        text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', text, flags=re.DOTALL)
        text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n', text, flags=re.DOTALL)
        text = re.sub(r'<h4[^>]*>(.*?)</h4>', r'#### \1\n', text, flags=re.DOTALL)

        # Bold / Italic
        text = re.sub(r'<(strong|b)>(.*?)</\1>', r'**\2**', text, flags=re.DOTALL)
        text = re.sub(r'<(em|i)>(.*?)</\1>', r'*\2*', text, flags=re.DOTALL)

        # Links
        text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.DOTALL)

        # Images
        text = re.sub(r'<img[^>]*src="([^"]*)"[^>]*alt="([^"]*)"[^>]*/?>',
                       r'![\2](\1)', text, flags=re.DOTALL)

        # Lists
        text = re.sub(r'<ul[^>]*>\s*', '\n', text)
        text = re.sub(r'</ul>\s*', '\n', text)
        text = re.sub(r'<ol[^>]*>\s*', '\n', text)
        text = re.sub(r'</ol>\s*', '\n', text)
        text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1', text, flags=re.DOTALL)

        # Code blocks
        text = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>',
                       r'```\n\1\n```', text, flags=re.DOTALL)
        text = re.sub(r'<code>(.*?)</code>', r'`\1`', text, flags=re.DOTALL)

        # Blockquotes
        text = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>',
                       lambda m: '\n'.join('> ' + l for l in m.group(1).strip().split('\n')),
                       text, flags=re.DOTALL)

        # Paragraphs / breaks
        text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL)
        text = re.sub(r'<br\s*/?>', '\n', text)

        # Remove remaining HTML
        text = re.sub(r'<[^>]+>', '', text)

        # Decode entities
        text = text.replace('&amp;', '&').replace('&lt;', '<')
        text = text.replace('&gt;', '>').replace('&nbsp;', ' ')

        # Clean whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()
