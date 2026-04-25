"""Helpers shared by Phase 1 AI discovery services."""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date, datetime
from typing import Iterable


STOP_WORDS = {
    "a", "about", "after", "all", "also", "an", "and", "are", "as", "at",
    "be", "been", "between", "by", "can", "could", "for", "from", "had",
    "has", "have", "how", "in", "into", "is", "it", "its", "may", "more",
    "most", "not", "of", "on", "or", "our", "over", "such", "than", "that",
    "the", "their", "them", "these", "this", "those", "to", "using", "use",
    "used", "via", "was", "we", "were", "what", "when", "which", "while",
    "with", "within", "without", "your",
}


def collapse_whitespace(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_for_match(value: str | None) -> str:
    text = collapse_whitespace(value).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def normalize_identifier(value: str | None) -> str | None:
    text = collapse_whitespace(value)
    if not text:
        return None
    text = text.strip().lower()
    if text.startswith("https://doi.org/"):
        text = text.split("https://doi.org/", 1)[1]
    return text.strip(" /") or None


def normalize_topic_list(topics: Iterable[str] | None, *, limit: int = 20) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw_topic in topics or []:
        topic = collapse_whitespace(raw_topic)
        if len(topic) < 2:
            continue
        key = topic.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(topic)
        if len(cleaned) >= limit:
            break
    return cleaned


def tokenize_text(text: str | None) -> list[str]:
    tokens = re.findall(r"[a-z][a-z0-9-]{2,}", normalize_for_match(text))
    return [token for token in tokens if token not in STOP_WORDS]


def extract_candidate_topics(texts: Iterable[str], *, max_candidates: int = 20) -> list[tuple[str, float]]:
    documents: list[list[str]] = []
    for text in texts:
        tokens = tokenize_text(text)
        if len(tokens) >= 2:
            documents.append(tokens)

    if not documents:
        return []

    term_counts: Counter[str] = Counter()
    doc_counts: Counter[str] = Counter()
    total_documents = len(documents)

    for tokens in documents:
        doc_terms: list[str] = []
        doc_terms.extend(tokens)
        doc_terms.extend(
            f"{tokens[index]} {tokens[index + 1]}"
            for index in range(len(tokens) - 1)
            if tokens[index] != tokens[index + 1]
        )

        seen_terms: set[str] = set()
        for term in doc_terms:
            if not _is_valid_topic_term(term):
                continue
            term_counts[term] += 1
            if term not in seen_terms:
                doc_counts[term] += 1
                seen_terms.add(term)

    scored: list[tuple[str, float]] = []
    for term, frequency in term_counts.items():
        document_frequency = doc_counts.get(term, 1)
        idf = math.log((1 + total_documents) / (1 + document_frequency)) + 1.0
        score = float(frequency) * idf
        scored.append((term, score))

    scored.sort(key=lambda item: (-item[1], -len(item[0]), item[0]))
    return scored[:max_candidates]


def _is_valid_topic_term(term: str) -> bool:
    if len(term) < 4:
        return False
    if term in STOP_WORDS:
        return False
    if term.count(" ") >= 3:
        return False
    if re.fullmatch(r"\d+", term):
        return False
    words = term.split()
    return all(word not in STOP_WORDS and len(word) >= 3 for word in words)


def average_vector(vectors: Iterable[list[float]]) -> list[float]:
    vector_list = [vector for vector in vectors if vector]
    if not vector_list:
        return []
    length = len(vector_list[0])
    if any(len(vector) != length for vector in vector_list):
        return []
    return [sum(vector[index] for vector in vector_list) / len(vector_list) for index in range(length)]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def compute_topic_overlap(text: str | None, topics: Iterable[str]) -> tuple[float, str | None]:
    normalized_text = normalize_for_match(text)
    if not normalized_text:
        return 0.0, None

    best_topic = None
    best_score = 0.0
    for raw_topic in topics:
        topic = normalize_for_match(raw_topic)
        if not topic:
            continue
        if topic in normalized_text:
            score = min(1.0, len(topic.split()) / 3.0 + 0.35)
        else:
            topic_tokens = set(topic.split())
            text_tokens = set(normalized_text.split())
            if not topic_tokens:
                continue
            score = len(topic_tokens & text_tokens) / float(len(topic_tokens))
        if score > best_score:
            best_score = score
            best_topic = raw_topic
    return best_score, best_topic


def build_candidate_text(*parts: str | None) -> str:
    return " ".join(part for part in (collapse_whitespace(value) for value in parts) if part)


def parse_publication_date(value: str | date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = collapse_whitespace(value)
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date()
        except ValueError:
            continue
    return None


def canonical_external_id(source: str, *, source_id: str | None = None, doi: str | None = None, title: str | None = None) -> str:
    normalized_doi = normalize_identifier(doi)
    if normalized_doi:
        return f"doi:{normalized_doi}"

    normalized_source_id = normalize_identifier(source_id)
    if normalized_source_id:
        return f"{source}:{normalized_source_id}"

    title_key = normalize_for_match(title)
    if title_key:
        return f"{source}:title:{title_key}"
    return f"{source}:unknown"


def split_external_id(value: str | None) -> tuple[str | None, str | None]:
    text = collapse_whitespace(value)
    if not text or ":" not in text:
        return None, normalize_identifier(text)
    scheme, raw_value = text.split(":", 1)
    return scheme, normalize_identifier(raw_value)


def source_to_reference_type(source: str | None) -> str:
    lookup = {
        "arxiv": "arxiv",
        "pubmed": "pubmed",
        "crossref": "journal",
        "semantic_scholar": "journal",
    }
    return lookup.get((source or "").strip().lower(), "other")