"""About -- what RAGStrike is, what it refuses to do, and how to read its output.

RESPONSIBILITY
    Say plainly what the tool claims and what it does not. A security tool whose limitations are
    only in its documentation gets quoted by its dashboard.
"""

from __future__ import annotations

from ragstrike.dashboard.assets.branding import PRODUCT_NAME, TAGLINE
from ragstrike.dashboard.components.cards import summary_card
from ragstrike.dashboard.context import PageContext
from ragstrike.dashboard.layouts.page_layout import html, page_header, section

WHAT_IT_IS = """
RAGStrike is an extensible offensive security evaluation framework for retrieval-augmented
generation systems. It executes attack packs against a target, analyzes the responses with
deterministic detectors, scores the result with published arithmetic, and produces a report in which
every finding traces back to the exact request, response, detector, and calculation that produced it.
"""

WHAT_IT_IS_NOT = """
It is not a guarantee. A clean scan means the shipped packs did not find the weaknesses they test
for -- not that none exist. Coverage is reported alongside every grade for exactly this reason: a
grade computed from half the intended cases is a different claim from one computed from all of them.
"""

OUT_OF_SCOPE = (
    "Detection evasion",
    "WAF bypass",
    "Rate-limit circumvention",
    "Mass or untargeted scanning",
    "Any feature whose primary value is testing systems the operator is not authorized to test",
)

PRINCIPLES = {
    "Authorization is a record, not a checkbox": "Every target carries who authorized testing it and "
    "under what reference. No scan starts without one, and the record is carried into every report.",
    "Local by default": "A fresh install can only reach this machine. Pointing RAGStrike elsewhere "
    "takes two deliberate steps, because accidentally scanning a third party is an incident.",
    "Scores are arithmetic": "Risk is computed, not judged by a model. The full calculation is "
    "reproduced in the report so any reader can check it by hand.",
    "Detection is deterministic": "Findings come from canaries and pattern detectors with recorded "
    "evidence. The same target, same seed, and same corpus produce the same result.",
    "Recommendations are retrieved": "Remediation text comes from a reviewed catalog, not from a "
    "model improvising advice about a system it has not seen.",
}


def render(context: PageContext) -> None:
    page_header(f"About {PRODUCT_NAME}", TAGLINE)

    import streamlit as st

    section("What it is")
    st.write(WHAT_IT_IS.strip())

    section("What it is not")
    st.write(WHAT_IT_IS_NOT.strip())

    section("Design principles")
    for title, body in PRINCIPLES.items():
        with st.expander(title):
            st.write(body)

    section("Permanently out of scope")
    for item in OUT_OF_SCOPE:
        st.write(f"- {item}")
    st.caption("Recorded so the boundary is not relitigated in every feature discussion.")

    section("This build")
    versions = context.services.status.versions()
    html(
        summary_card(
            "Versions",
            {
                "Engine": versions.engine or "unknown (backend not reachable)",
                "Plugin API": versions.plugin_api or "unknown",
                "Scoring model": versions.scoring_model or "unknown",
                "Dashboard transport": context.services.transport.describe(),
                "Theme": context.config.theme,
            },
            footer="Apache-2.0. The dashboard is an HTTP client of the API and never imports the "
            "engine (ADR-010) -- an import-linter contract fails CI if it tries.",
        )
    )
