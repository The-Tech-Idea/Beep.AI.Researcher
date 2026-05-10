"""Package availability checker — checks if optional heavy packages are installed.

Used by templates to conditionally show/hide feature buttons based on whether
the underlying packages are installed. Admin users install packages from
Admin > Optional Packages.
"""

from __future__ import annotations

import importlib
from typing import Dict

# Optional package groups and their required packages
OPTIONAL_PACKAGES: Dict[str, list[str]] = {
    "document_ocr": ["docling"],
    "rag_ingestion": ["llama_index", "pymupdf4llm"],
    "full_text_extraction": ["unstructured", "pdfplumber", "pytesseract"],
    "s3_storage": ["boto3"],
    "azure_storage": ["azure.storage.blob"],
    "email_oauth2": ["msal", "googleapiclient"],
    "nlp_readability": ["spacy"],
}

# Feature-to-package mapping
FEATURE_PACKAGES: Dict[str, str] = {
    # Document extraction features
    "docling_extraction": "document_ocr",
    "document_auto_extract": "document_ocr",
    # RAG features
    "rag_ingestion": "rag_ingestion",
    "rag_collection_setup": "rag_ingestion",
    # Full text extraction
    "full_text_extraction": "full_text_extraction",
    "unstructured_partition": "full_text_extraction",
    # Storage features
    "s3_storage": "s3_storage",
    "azure_storage": "azure_storage",
    # Email features
    "email_oauth2": "email_oauth2",
    # NLP features
    "nlp_readability": "nlp_readability",
    "spacy_analysis": "nlp_readability",
}

_cache: Dict[str, bool] = {}


def is_package_installed(package_name: str) -> bool:
    """Check if a single package is installed."""
    if package_name in _cache:
        return _cache[package_name]

    try:
        importlib.import_module(package_name)
        _cache[package_name] = True
        return True
    except ImportError:
        _cache[package_name] = False
        return False


def is_feature_available(feature: str) -> bool:
    """Check if a feature is available (its required package is installed)."""
    package_group = FEATURE_PACKAGES.get(feature)
    if package_group is None:
        return True  # No dependency, always available

    required_packages = OPTIONAL_PACKAGES.get(package_group, [])
    if not required_packages:
        return True

    return all(is_package_installed(pkg) for pkg in required_packages)


def get_package_status() -> Dict[str, bool]:
    """Get status of all optional package groups."""
    status = {}
    for group_name, packages in OPTIONAL_PACKAGES.items():
        status[group_name] = all(is_package_installed(pkg) for pkg in packages)
    return status


def get_feature_status() -> Dict[str, bool]:
    """Get availability status of all features."""
    status = {}
    for feature in FEATURE_PACKAGES:
        status[feature] = is_feature_available(feature)
    return status


def clear_cache() -> None:
    """Clear the installation cache (for testing)."""
    _cache.clear()
