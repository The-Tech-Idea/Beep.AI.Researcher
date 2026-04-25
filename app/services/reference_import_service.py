"""Reference import parsing, dedupe, and batch import helpers."""
from __future__ import annotations

import json
import re

from app.database import db
from app.models.researcher import Reference, ResearchProject
from app.services.reference_service import clean_value, create_reference


def parse_references_content(content: str, content_format: str) -> list[dict]:
    fmt = (content_format or "json").lower()
    if fmt == "json":
        parsed = json.loads(content or "[]")
        if isinstance(parsed, dict):
            parsed = parsed.get("references", [])
        if not isinstance(parsed, list):
            raise ValueError("JSON import payload must be a list or {references: []}")
        return parsed
    if fmt == "bibtex":
        return _parse_bibtex(content)
    if fmt == "ris":
        return _parse_ris(content)
    raise ValueError("Unsupported import format. Use json, bibtex, or ris.")


def import_references(project: ResearchProject, content: str, content_format: str) -> dict:
    entries = parse_references_content(content, content_format)
    index = _build_project_reference_index(project)
    result = {
        "created": 0,
        "skipped": 0,
        "duplicate_skipped": 0,
        "invalid_skipped": 0,
        "errors": [],
        "duplicate_reasons": {
            "citation_key": 0,
            "doi": 0,
            "title_year": 0,
        },
        "reference_ids": [],
    }

    for idx, item in enumerate(entries):
        try:
            title = clean_value(item.get("title"))
            if not title:
                result["skipped"] += 1
                result["invalid_skipped"] += 1
                result["errors"].append({"index": idx, "error": "Missing title"})
                continue

            duplicate_reason, existing_reference = _find_duplicate_reference(
                project,
                item,
                index,
            )
            if existing_reference is not None:
                result["skipped"] += 1
                result["duplicate_skipped"] += 1
                result["duplicate_reasons"][duplicate_reason] += 1
                result["errors"].append(
                    {
                        "index": idx,
                        "error": "Duplicate reference",
                        "reason": duplicate_reason,
                        "reference_id": existing_reference.id,
                        "title": existing_reference.title,
                    }
                )
                continue

            with db.session.begin_nested():
                reference = create_reference(project, item, commit=False)
                db.session.flush()

            result["created"] += 1
            result["reference_ids"].append(reference.id)
            _register_reference_index(index, reference)
        except Exception as exc:
            result["skipped"] += 1
            result["invalid_skipped"] += 1
            result["errors"].append({"index": idx, "error": str(exc)})

    db.session.commit()
    return result


def _build_project_reference_index(project: ResearchProject) -> dict[str, dict[str, Reference]]:
    references = (
        Reference.query
        .filter_by(project_id=project.id)
        .order_by(Reference.id.asc())
        .all()
    )
    index = {
        "citation_key": {},
        "doi": {},
        "title_year": {},
    }
    for reference in references:
        _register_reference_index(index, reference)
    return index


def _register_reference_index(index: dict[str, dict[str, Reference]], reference: Reference) -> None:
    citation_key = clean_value(reference.citation_key)
    if citation_key:
        index["citation_key"].setdefault(citation_key.lower(), reference)

    doi = _normalize_doi(reference.doi)
    if doi:
        index["doi"].setdefault(doi, reference)

    title_year = _build_title_year_key(reference.title, reference.year)
    if title_year:
        index["title_year"].setdefault(title_year, reference)


def _find_duplicate_reference(
    project: ResearchProject,
    item: dict,
    index: dict[str, dict[str, Reference]],
) -> tuple[str | None, Reference | None]:
    citation_key = clean_value(item.get("citation_key"))
    if citation_key:
        existing_reference = index["citation_key"].get(citation_key.lower())
        if existing_reference is not None:
            return "citation_key", existing_reference

    doi = _normalize_doi(item.get("doi"))
    if doi:
        existing_reference = index["doi"].get(doi)
        if existing_reference is not None:
            return "doi", existing_reference

    title_year = _build_title_year_key(item.get("title"), _parse_year(item.get("year")))
    if title_year:
        existing_reference = index["title_year"].get(title_year)
        if existing_reference is not None:
            return "title_year", existing_reference

    return None, None


def _normalize_doi(value) -> str | None:
    doi = clean_value(value)
    if not doi:
        return None

    normalized = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    return normalized or None


def _build_title_year_key(title, year: int | None) -> str | None:
    cleaned_title = clean_value(title)
    if not cleaned_title or year is None:
        return None

    normalized_title = re.sub(r"[^a-z0-9]+", " ", cleaned_title.lower()).strip()
    normalized_title = re.sub(r"\s+", " ", normalized_title)
    if not normalized_title:
        return None
    return f"{normalized_title}|{year}"


def _parse_year(value) -> int | None:
    cleaned = clean_value(value)
    if not cleaned:
        return None
    if str(cleaned).isdigit():
        return int(cleaned)
    return None


def _parse_bibtex(content: str) -> list[dict]:
    entries = []
    pattern = re.compile(
        r"@(?P<type>\w+)\s*\{\s*(?P<key>[^,]+)\s*,(?P<body>[\s\S]*?)\n\}\s*(?=@|$)",
        re.MULTILINE,
    )
    field_pattern = re.compile(r"(\w+)\s*=\s*(\{[^{}]*\}|\"[^\"]*\"|[^,\n]+)\s*,?", re.MULTILINE)
    for match in pattern.finditer(content or ""):
        entry_type = match.group("type").strip().lower()
        key = match.group("key").strip()
        body = match.group("body")
        fields = {}
        for field_match in field_pattern.finditer(body):
            field_name = field_match.group(1).lower()
            raw_value = field_match.group(2).strip()
            if raw_value.startswith("{") and raw_value.endswith("}"):
                raw_value = raw_value[1:-1]
            if raw_value.startswith('"') and raw_value.endswith('"'):
                raw_value = raw_value[1:-1]
            fields[field_name] = raw_value.strip()
        entries.append(
            {
                "citation_key": key,
                "source_type": _normalize_source_type(entry_type),
                "title": fields.get("title"),
                "authors": _parse_authors(fields.get("author")),
                "year": fields.get("year"),
                "source": fields.get("journal") or fields.get("publisher") or fields.get("booktitle"),
                "volume": fields.get("volume"),
                "issue": fields.get("number"),
                "pages": fields.get("pages"),
                "doi": fields.get("doi"),
                "url": fields.get("url"),
                "abstract": fields.get("abstract"),
                "keywords": _parse_keywords(fields.get("keywords")),
            }
        )
    return entries


def _parse_ris(content: str) -> list[dict]:
    entries = []
    current = {}
    authors = []
    keywords = []
    for line in (content or "").splitlines():
        if not line.strip():
            continue
        if line.startswith("ER"):
            if authors:
                current["authors"] = authors
            if keywords:
                current["keywords"] = keywords
            entries.append(current)
            current = {}
            authors = []
            keywords = []
            continue
        if " - " not in line:
            continue
        tag, value = line.split(" - ", 1)
        tag = tag.strip().upper()
        value = value.strip()
        if tag == "TY":
            current["source_type"] = _normalize_source_type(value.lower())
        elif tag in {"TI", "T1"}:
            current["title"] = value
        elif tag == "AU":
            authors.append(value)
        elif tag in {"PY", "Y1"}:
            current["year"] = value[:4]
        elif tag in {"JO", "JF", "T2"}:
            current["source"] = value
        elif tag == "VL":
            current["volume"] = value
        elif tag == "IS":
            current["issue"] = value
        elif tag == "SP":
            current["pages"] = value
        elif tag == "DO":
            current["doi"] = value
        elif tag == "UR":
            current["url"] = value
        elif tag == "AB":
            current["abstract"] = value
        elif tag == "KW":
            keywords.append(value)
        elif tag == "ID":
            current["citation_key"] = value
    if current:
        if authors:
            current["authors"] = authors
        if keywords:
            current["keywords"] = keywords
        entries.append(current)
    return entries


def _normalize_source_type(raw_type: str | None) -> str:
    value = (clean_value(raw_type) or "other").lower()
    mapping = {
        "article": "journal",
        "inproceedings": "conference",
        "proceedings": "conference",
        "misc": "other",
        "online": "website",
        "web": "website",
    }
    return mapping.get(value, value)


def _parse_authors(raw_authors):
    if not raw_authors:
        return []
    if isinstance(raw_authors, list):
        return [str(author).strip() for author in raw_authors if str(author).strip()]
    if isinstance(raw_authors, str):
        if ";" in raw_authors:
            return [author.strip() for author in raw_authors.split(";") if author.strip()]
        if " and " in raw_authors.lower():
            return [author.strip() for author in re.split(r"\s+[Aa][Nn][Dd]\s+", raw_authors) if author.strip()]
        return [raw_authors.strip()] if raw_authors.strip() else []
    return []


def _parse_keywords(raw_keywords):
    if not raw_keywords:
        return []
    if isinstance(raw_keywords, list):
        return [str(keyword).strip() for keyword in raw_keywords if str(keyword).strip()]
    if isinstance(raw_keywords, str):
        return [keyword.strip() for keyword in re.split(r"[;,]", raw_keywords) if keyword.strip()]
    return []
