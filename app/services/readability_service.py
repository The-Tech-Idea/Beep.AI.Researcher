"""Phase 4 Readability Service — rule-based passive voice, hedge, and length metrics."""

from __future__ import annotations

import hashlib
import re
from typing import Any

# Passive voice markers — common "be" + past participle patterns
_PASSIVE_PATTERNS = [
    r"\b(?:is|are|was|were|be|been|being)\s+\w+ed\b",
    r"\b(?:is|are|was|were|be|been|being)\s+(?:given|taken|made|done|found|shown|known|thought|seen|said|used|written)\b",
]

# Hedging language — words that weaken claims
_HEDGE_WORDS = {
    "might",
    "could",
    "may",
    "perhaps",
    "possibly",
    "probably",
    "likely",
    "unlikely",
    "appears",
    "seems",
    "suggests",
    "indicates",
    "suggestive",
    "potential",
    "tentative",
    "somewhat",
    "rather",
    "fairly",
    "relatively",
    "to some extent",
    "it is possible",
    "it appears",
    "it seems",
    "we believe",
    "we think",
    "one might argue",
}

# Jargon/heavy academic markers
_JARGON_PATTERNS = [
    r"\b(?:utilize|methodology|furthermore|heretofore|notwithstanding|aforementioned|subsequent to|in order to|with respect to|in regard to)\b",
]

# Transition word quality indicators
_GOOD_TRANSITIONS = {
    "however",
    "therefore",
    "consequently",
    "moreover",
    "furthermore",
    "nevertheless",
    "additionally",
    "similarly",
    "conversely",
    "specifically",
    "in contrast",
    "as a result",
}


class ReadabilityService:
    """Pure-Python readability metrics: passive voice, hedging, sentence length, jargon."""

    _cache: dict[str, dict[str, Any]] = {}

    def analyse(self, text: str, *, use_cache: bool = True) -> dict[str, Any]:
        """Return readability metrics for the given text."""
        if not text or not text.strip():
            return {
                "passive_voice_pct": 0.0,
                "hedge_density": 0.0,
                "avg_sentence_length": 0.0,
                "long_sentence_count": 0,
                "jargon_count": 0,
                "word_count": 0,
            }

        content_hash = hashlib.md5(text.encode("utf-8")).hexdigest()
        if use_cache and content_hash in self._cache:
            return self._cache[content_hash]

        words = text.split()
        word_count = len(words)
        sentences = self._split_sentences(text)

        passive_count = self._count_passive(text)
        passive_pct = (passive_count / max(1, len(sentences))) * 100

        hedge_count = self._count_hedges(words)
        hedge_density = (hedge_count / max(1, word_count)) * 100

        sentence_lengths = [len(s.split()) for s in sentences]
        avg_length = sum(sentence_lengths) / max(1, len(sentence_lengths))
        long_sentences = sum(1 for l in sentence_lengths if l > 30)

        jargon_count = self._count_jargon(text)

        result = {
            "passive_voice_pct": round(passive_pct, 1),
            "hedge_density": round(hedge_density, 2),
            "avg_sentence_length": round(avg_length, 1),
            "long_sentence_count": long_sentences,
            "jargon_count": jargon_count,
            "word_count": word_count,
            "sentence_count": len(sentences),
        }

        if use_cache:
            self._cache[content_hash] = result

        return result

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split text into sentences using simple heuristic."""
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s for s in sentences if s.strip()]

    @staticmethod
    def _count_passive(text: str) -> int:
        """Count passive voice constructions."""
        count = 0
        for pattern in _PASSIVE_PATTERNS:
            count += len(re.findall(pattern, text, re.IGNORECASE))
        return count

    @staticmethod
    def _count_hedges(words: list[str]) -> int:
        """Count hedging words."""
        lower_words = {w.lower().strip(".,;:()\"'") for w in words}
        return sum(1 for w in lower_words if w in _HEDGE_WORDS)

    @staticmethod
    def _count_jargon(text: str) -> int:
        """Count jargon/wordy constructions."""
        count = 0
        for pattern in _JARGON_PATTERNS:
            count += len(re.findall(pattern, text, re.IGNORECASE))
        return count
