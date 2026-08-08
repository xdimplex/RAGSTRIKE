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
    """The logo plus product name, as used in the sidebar header.

    WHY THIS HAS ITS OWN CLASSES INSTEAD OF REUSING ``rs-row``/``rs-metric__hint``
        It used to, and the sidebar header rendered as a pile: "RAGStrike" sitting on top of its own
        tagline, with the connection line and the API URL overlapping both.

        Two causes, and both needed the header to stop borrowing generic classes.

        ``line-height: 0`` on the logo span collapsed the row's line box to nothing, so the block
        after it began before the text had finished. It was there to stop the inline SVG adding
        descender space -- correct instinct, wrong tool: ``display: flex`` on the row already
        removes that, and zeroing the line height removes the text's height as well.

        ``rs-metric__hint`` sets a font size and a colour and nothing else. That is fine for one
        caption in a card; the header stacks THREE of them, and with no line-height and no margin
        they had nothing keeping them apart.
    """
    mark = tag("span", LOGO_SVG, class_="rs-brand__mark", style=style({"color": accent}))
    name = tag(
        "span",
        escape(PRODUCT_NAME),
        class_="rs-brand__name",
        style=style({"color": text_colour}),
    )
    head = tag("div", mark + name, class_="rs-brand__head")
    if subtitle:
        head += tag("div", escape(subtitle), class_="rs-brand__tagline")
    return tag("div", head, class_="rs-brand")
