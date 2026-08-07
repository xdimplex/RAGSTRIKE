"""HTML assembly helpers.

WHY ESCAPING MATTERS MORE HERE THAN IN AN ORDINARY APP
    Every component below renders with ``unsafe_allow_html=True``, and much of what it renders is
    *attacker-influenced by design*: payload text, target responses, plugin descriptions from a
    third-party pack, finding titles built from matched spans. A dashboard that pretty-prints an
    injection payload without escaping it has an XSS hole whose exploit is literally the tool's own
    test corpus.

    So: no component interpolates a value into markup without passing it through :func:`escape`, and
    a test asserts that a payload containing a ``<script>`` tag comes out inert.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from html import escape as _escape


def escape(value: object) -> str:
    """Escape a value for use in HTML text or a quoted attribute."""
    return _escape(str(value), quote=True)


def classes(*names: str | None) -> str:
    """Join class names, dropping the empty ones."""
    return " ".join(name for name in names if name)


def style(declarations: Mapping[str, str | None]) -> str:
    """Build a ``style`` attribute value from a mapping, skipping empty declarations.

    **Escaping happens in** :func:`tag`, **not here.** This function's output is always passed as
    ``tag(..., style=...)``, and escaping in both places produced ``&amp;quot;`` -- safe, but
    rendered as literal noise in the CSS. Escaping exactly once, at the point the value becomes an
    attribute, is the property a test pins.
    """
    parts = [f"{prop}:{value}" for prop, value in declarations.items() if value]
    return ";".join(parts)


def tag(name: str, content: str = "", **attributes: str | None) -> str:
    """Build one element.

    Attribute names use a trailing underscore to avoid Python keywords (``class_`` -> ``class``) and
    single underscores become hyphens (``data_id`` -> ``data-id``). Values are escaped; content is
    *not*, because it is normally the already-escaped output of another builder.
    """
    rendered = []
    for raw_key, value in attributes.items():
        if value is None or value == "":
            continue
        key = raw_key.rstrip("_").replace("_", "-")
        rendered.append(f'{key}="{escape(value)}"')
    attrs = (" " + " ".join(rendered)) if rendered else ""
    return f"<{name}{attrs}>{content}</{name}>"


def join(parts: Iterable[str]) -> str:
    """Concatenate fragments, dropping empties."""
    return "".join(part for part in parts if part)
