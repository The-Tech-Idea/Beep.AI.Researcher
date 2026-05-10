"""Package manager service — safe pip install/uninstall for optional packages.

Provides a controlled interface for admin users to install heavy optional
packages (docling, unstructured, llama-index, etc.) without restarting
the application. All operations are subprocess-based and thread-safe.
"""

from __future__ import annotations

import importlib
import json
import logging
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger(__name__)

_install_lock = threading.Lock()


@dataclass
class PackageInfo:
    """Metadata for an optional package group."""

    key: str
    label: str
    description: str
    packages: List[str]
    feature_flag: str
    size_hint: str = ""
    depends_on: List[str] = field(default_factory=list)

    @property
    def is_installed(self) -> bool:
        return all(_is_pip_installed(pkg) for pkg in self.packages)


# ── Optional package registry ──────────────────────────────────────────────

OPTIONAL_PACKAGES: Dict[str, PackageInfo] = {
    "document_ocr": PackageInfo(
        key="document_ocr",
        label="Document OCR & Layout Analysis",
        description="Advanced PDF parsing, OCR, table recognition, and document understanding via Docling.",
        packages=[
            "docling[easyocr,rapidocr,htmlrender]",
        ],
        feature_flag="document_ocr_enabled",
        size_hint="~2 GB",
    ),
    "rag_ingestion": PackageInfo(
        key="rag_ingestion",
        label="RAG Document Ingestion",
        description="LlamaIndex document store, chunking, vector indexing, and RAG pipelines.",
        packages=[
            "llama-index-core",
            "llama-index-readers-file",
            "pymupdf4llm",
            "PyMuPDF",
        ],
        feature_flag="rag_ingestion_enabled",
        size_hint="~500 MB",
    ),
    "full_text_extraction": PackageInfo(
        key="full_text_extraction",
        label="Full Document Extraction Suite",
        description="unstructured partitioning, pdfplumber, pytesseract, Pillow for fallback document parsing.",
        packages=[
            "unstructured[all-docs,local-inference]",
            "pdfplumber",
            "pytesseract",
            "Pillow",
        ],
        feature_flag="full_text_extraction_enabled",
        size_hint="~1 GB",
        depends_on=["document_ocr"],
    ),
    "s3_storage": PackageInfo(
        key="s3_storage",
        label="S3 / MinIO Storage Backend",
        description="Store documents and uploads on S3-compatible storage.",
        packages=["boto3"],
        feature_flag="s3_storage_enabled",
        size_hint="~50 MB",
    ),
    "azure_storage": PackageInfo(
        key="azure_storage",
        label="Azure Blob Storage Backend",
        description="Store documents and uploads on Azure Blob Storage.",
        packages=["azure-storage-blob"],
        feature_flag="azure_storage_enabled",
        size_hint="~100 MB",
    ),
    "email_oauth2": PackageInfo(
        key="email_oauth2",
        label="OAuth2 Email Integration",
        description="Microsoft 365 and Gmail email sending via OAuth2.",
        packages=[
            "msal",
            "google-api-python-client",
            "google-auth",
            "google-auth-oauthlib",
        ],
        feature_flag="email_oauth2_enabled",
        size_hint="~200 MB",
    ),
    "nlp_readability": PackageInfo(
        key="nlp_readability",
        label="NLP Readability Analysis",
        description="spaCy-based passive voice, hedge detection, and sentence analysis.",
        packages=["spacy"],
        feature_flag="nlp_readability_enabled",
        size_hint="~800 MB",
    ),
}


def _is_pip_installed(package_spec: str) -> bool:
    """Check if a package (ignoring extras) is installed."""
    pkg_name = package_spec.split("[")[0].split(">=")[0].lower().replace("-", "_")
    try:
        importlib.import_module(pkg_name)
        return True
    except ImportError:
        pass
    # Fallback: check pip list
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package_spec.split("[")[0]],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_installed_packages() -> set[str]:
    """Get set of installed package names (lowercase, normalized)."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        packages = json.loads(result.stdout)
        return {p["name"].lower().replace("-", "_") for p in packages}
    except Exception:
        return set()


def install_packages(package_specs: List[str]) -> dict:
    """Install packages via pip. Thread-safe, one install at a time."""
    with _install_lock:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q"] + package_specs,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode == 0:
                logger.info("Installed packages: %s", package_specs)
                return {"ok": True, "message": "Packages installed successfully."}
            else:
                error = result.stderr.strip() or result.stdout.strip()
                logger.error("pip install failed: %s", error)
                return {
                    "ok": False,
                    "message": error[:500] if error else "Unknown error",
                }
        except subprocess.TimeoutExpired:
            return {"ok": False, "message": "Installation timed out after 10 minutes."}
        except Exception as e:
            logger.exception("pip install exception")
            return {"ok": False, "message": str(e)}


def uninstall_packages(package_specs: List[str]) -> dict:
    """Uninstall packages via pip. Thread-safe."""
    with _install_lock:
        try:
            names = [p.split("[")[0] for p in package_specs]
            result = subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", "-q"] + names,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                logger.info("Uninstalled packages: %s", names)
                return {"ok": True, "message": "Packages uninstalled successfully."}
            else:
                error = result.stderr.strip() or result.stdout.strip()
                return {
                    "ok": False,
                    "message": error[:500] if error else "Unknown error",
                }
        except subprocess.TimeoutExpired:
            return {"ok": False, "message": "Uninstall timed out."}
        except Exception as e:
            logger.exception("pip uninstall exception")
            return {"ok": False, "message": str(e)}


def check_optional_feature(feature_key: str) -> dict:
    """Check if an optional feature's packages are installed."""
    info = OPTIONAL_PACKAGES.get(feature_key)
    if info is None:
        return {"available": False, "message": f"Unknown feature: {feature_key}"}

    installed = info.is_installed
    return {
        "available": installed,
        "label": info.label,
        "description": info.description,
        "packages": info.packages,
        "size_hint": info.size_hint,
        "feature_flag": info.feature_flag,
    }
