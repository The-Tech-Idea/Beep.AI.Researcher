"""Tests for Phase 4 Readability Service."""

from app.services.readability_service import ReadabilityService


def test_analyse_empty_text():
    result = ReadabilityService().analyse("")
    assert result["word_count"] == 0


def test_analyse_basic_metrics():
    text = "The experiment was conducted over three years. Results suggest a significant improvement. However, more data might be needed."
    result = ReadabilityService().analyse(text)
    assert result["word_count"] > 0
    assert result["sentence_count"] > 0
    assert result["avg_sentence_length"] > 0


def test_passive_voice_detection():
    text = "The results were found to be significant. The experiment was conducted by the team."
    result = ReadabilityService().analyse(text)
    assert result["passive_voice_pct"] > 0


def test_hedge_detection():
    text = "The results might suggest something. Perhaps this is possibly correct. It seems that the approach could work."
    result = ReadabilityService().analyse(text)
    assert result["hedge_density"] > 0


def test_cache_returns_same_result():
    text = "The quick brown fox jumps over the lazy dog."
    result1 = ReadabilityService().analyse(text, use_cache=True)
    result2 = ReadabilityService().analyse(text, use_cache=True)
    assert result1 == result2


def test_jargon_detection():
    text = "Furthermore, the methodology utilized a subsequent approach with respect to the aforementioned framework."
    result = ReadabilityService().analyse(text)
    assert result["jargon_count"] > 0


def test_long_sentence_count():
    # Create a sentence with >30 words
    words = " ".join(["word"] * 35)
    text = f"{words}. Short sentence."
    result = ReadabilityService().analyse(text)
    assert result["long_sentence_count"] >= 1
