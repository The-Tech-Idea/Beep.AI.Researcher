"""Search provider implementations"""

from .pubmed import PubMedProvider
from .arxiv import ArxivProvider

# Phase 2 — New providers
try:
    from .semantic_scholar import SemanticScholarProvider
except ImportError:
    SemanticScholarProvider = None

try:
    from .crossref import CrossRefProvider
except ImportError:
    CrossRefProvider = None

try:
    from .openalex import OpenAlexProvider
except ImportError:
    OpenAlexProvider = None

# Phase 03 — Book providers
try:
    from .open_library import OpenLibraryProvider
except ImportError:
    OpenLibraryProvider = None

try:
    from .google_books import GoogleBooksProvider
except ImportError:
    GoogleBooksProvider = None

__all__ = [
    'PubMedProvider',
    'ArxivProvider',
    'SemanticScholarProvider',
    'CrossRefProvider',
    'OpenAlexProvider',
    'OpenLibraryProvider',
    'GoogleBooksProvider',
]
