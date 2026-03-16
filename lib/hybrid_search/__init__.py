"""Hybrid Search Module - BM25 + Vector Search with RRF Fusion."""

try:
    from .wrapper import HybridSearchWrapper

    HYBRID_SEARCH_AVAILABLE = True
except ImportError as e:
    HYBRID_SEARCH_AVAILABLE = False
    HybridSearchWrapper = None  # type: ignore[misc, assignment]
    _import_error = e

__version__ = "0.1.0"
__all__ = ["HybridSearchWrapper", "HYBRID_SEARCH_AVAILABLE"]
