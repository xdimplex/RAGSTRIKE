"""Shared UI widgets.

Two of these matter more than they look:

``profile_banner`` is on every page. An operator must never be unsure whether they are looking at the
vulnerable build or the hardened one -- that confusion turns a security demonstration into a
misleading one.

``chunk_viewer`` renders retrieved chunks exactly as the backend returned them, including any hidden
instruction a document was carrying. It does not sanitize what it displays: hiding a weakness in the
presentation layer would make it invisible to the person who is here to learn about it.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from frontend.components.api_client import ApiError


def profile_banner(profile: str) -> None:
    """Unmissable indicator of which build is running.

    Rendered as themed markup rather than ``st.error``/``st.success`` so it takes the lab palette
    like everything else -- Streamlit's alerts keep their own colours and looked pasted on. The
    contrast between the two profiles is deliberately strong: which build an operator is talking to
    is the single fact this lab must never let anyone mistake.
    """
    if profile == "vulnerable":
        title = "⚠️ Vulnerable profile — no security controls active"
        body = (
            "This application follows instructions found in uploaded documents and discloses its "
            "system prompt on request. Local lab only."
        )
        variant = "vulnerable"
    else:
        title = "🛡️ Secure profile — security controls active"
        body = "Retrieved content is fenced as data, and output is filtered before it is returned."
        variant = "secure"

    st.markdown(
        f'<div class="lab-banner lab-banner--{variant}">'
        f'<div class="lab-banner__title">{title}</div>'
        f"<div>{body}</div></div>",
        unsafe_allow_html=True,
    )


def show_api_error(error: ApiError) -> None:
    """Render a backend error as a diagnosis rather than a traceback."""
    st.error(f"**{error.code}** — {error.message}")
    if error.hint:
        st.info(f"**What to do:** {error.hint}")


def metric_row(metrics: list[tuple[str, Any]]) -> None:
    columns = st.columns(len(metrics))
    for column, (label, value) in zip(columns, metrics, strict=False):
        column.metric(label, value)


def chunk_viewer(chunks: list[dict[str, Any]], *, title: str = "Retrieved chunks") -> None:
    """Show retrieved chunks with scores and provenance.

    Rendered verbatim. If a chunk contains "ignore your previous instructions", that is what appears
    here -- which is exactly how an indirect injection becomes visible.
    """
    if not chunks:
        st.info("No chunks were retrieved for this question.")
        return

    st.markdown(f"**{title}** ({len(chunks)})")
    for position, chunk in enumerate(chunks, start=1):
        score = chunk.get("score", 0.0)
        source = chunk.get("source_name", "unknown")
        page = chunk.get("page")
        # Source, position in the document, and relevance -- the three things that explain WHY this
        # passage was chosen, which is the whole point of showing retrieval at all.
        header = (
            f"{position}.  {source}"
            + (f"  ·  page {page}" if page is not None else "")
            + f"  ·  chunk {chunk.get('index', 0)}"
            + f"  ·  relevance {score:.0%}"
        )
        with st.expander(header, expanded=position == 1):
            # Verbatim. If a chunk contains "ignore your previous instructions", that is what shows
            # here -- which is exactly how an indirect injection becomes visible to a reader.
            st.text(chunk.get("text", ""))

    # The internal identifiers (document_id, chunk_id, raw vector distance) used to be printed under
    # every chunk. They are storage keys: they tell a reader nothing about why the passage matched,
    # they made the panel read as debug output, and they are the kind of internal detail a product
    # should not volunteer. Relevance is shown as a percentage instead, which is the same
    # information in the form someone can actually judge.


def source_list(sources: list[str]) -> None:
    """The honest source list -- what was actually retrieved.

    Worth comparing against any citations inside the answer text: the model's citations are not
    checked against this, so a mismatch is weakness V9 on display.
    """
    if not sources:
        st.caption("No sources.")
        return
    st.markdown("**Sources retrieved:** " + ", ".join(f"`{name}`" for name in sources))


def health_badge(healthy: bool, label: str, detail: str = "") -> None:
    if healthy:
        st.markdown(f"✅ **{label}**")
    else:
        st.markdown(f"❌ **{label}** — {detail or 'unavailable'}")
