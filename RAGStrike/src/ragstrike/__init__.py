"""RAGStrike -- an extensible offensive security evaluation framework for RAG systems.

Version constants only. No import-time side effects, deliberately: the plugin registry is populated
explicitly at the composition root, never as a consequence of importing this package.
"""

__all__ = ["PLUGIN_API_VERSION", "__version__"]

#: Application version. Follows SemVer.
__version__ = "1.0.0"

#: Plugin API version, deliberately independent of ``__version__`` (ADR-015).
#:
#: Attack packs declare a compatible range against *this* value, not the application version. An
#: ecosystem in which every application patch release signals a potential break to every
#: third-party pack author is an ecosystem with no third-party packs.
#:
#: MAJOR -- breaking contract change; MINOR -- additive; PATCH -- clarification.
PLUGIN_API_VERSION = "1.0.0"
