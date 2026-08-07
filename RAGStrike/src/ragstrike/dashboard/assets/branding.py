"""The wordmark and product strings."""

from __future__ import annotations

from ragstrike.dashboard.components.html import escape, style, tag

PRODUCT_NAME = "RAGStrike"
TAGLINE = "Offensive security evaluation for RAG systems"

#: A crosshair over a document: retrieval under test. Drawn with ``currentColor`` so it inherits the
#: accent from the theme rather than carrying a colour of its own.
LOGO_SVG = (
    '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" '
    'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
    '<path d="M5 3h9l5 5v13H5z" stroke="currentColor" stroke-width="1.6" '
    'stroke-linejoin="round"/>'
    '<path d="M14 3v5h5" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>'
    '<circle cx="12" cy="14" r="3.4" stroke="currentColor" stroke-width="1.6"/>'
    '<path d="M12 9.2v1.6M12 17.2v1.6M7.4 14h1.6M15 14h1.6" stroke="currentColor" '
    'stroke-width="1.6" stroke-linecap="round"/>'
    "</svg>"
)


def wordmark(accent: str, text_colour: str, *, subtitle: str = "") -> str:
    """The logo plus product name, as used in the sidebar header."""
    mark = tag("span", LOGO_SVG, style=style({"color": accent, "line-height": "0"}))
    name = tag(
        "span",
        escape(PRODUCT_NAME),
        style=style(
            {
                "color": text_colour,
                "font-weight": "700",
                "font-size": "1.05rem",
                "letter-spacing": "0.02em",
            }
        ),
    )
    head = tag("div", mark + name, class_="rs-row")
    if not subtitle:
        return head
    return head + tag("div", escape(subtitle), class_="rs-metric__hint")
