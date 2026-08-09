"""Settings — what an ordinary user of this assistant is entitled to see.

WHY THIS PAGE NO LONGER DUMPS THE EFFECTIVE CONFIGURATION
    It used to render seven ``st.json`` blocks containing the model base URL, the API and UI ports,
    the chunk size and overlap, the similarity threshold, and the absolute filesystem paths of the
    upload directory, the Chroma store, the corpus, the SQLite database, and the log directory.

    Two things were wrong with that.

    1. **It is an information-disclosure surface.** Internal paths and service URLs are exactly what
       an attacker enumerates first, and a product that volunteers them on a settings screen has
       done that work for them. It also sat oddly in a project whose own security policy classifies
       infrastructure detail as Internal.

    2. **It is not what a settings page is for.** Raw JSON of an internal dataclass is a debug view.
       A user wants to know which assistant they are talking to and how it uses their documents.

    The operator has not lost anything: the effective configuration is still in
    ``configs/config.yaml`` and ``profiles/<profile>/config.yaml``, which are the audited source of
    truth, and the runtime view is on ``/health``. Neither is reachable by someone who merely has
    the chat UI open.

WHAT DELIBERATELY *STAYS*
    The profile banner and the security-posture summary. Which build you are talking to is the one
    fact this lab must never hide -- that is the entire point of shipping a vulnerable twin.
"""

from __future__ import annotations

import streamlit as st

import frontend._bootstrap as bootstrap
from frontend import theme  # noqa: F401  - must precede any project import
from frontend.components.api_client import ApiClient, ApiError
from frontend.components.widgets import profile_banner

settings = bootstrap.get_settings()
api = ApiClient(bootstrap.api_base_url(settings))

IS_SECURE = settings.profile == "secure"

st.set_page_config(
    page_title=bootstrap.page_title(settings, "Settings"),
    page_icon="⚙️",
    layout="wide",
)

# Stylesheet first: anything drawn before it appears unstyled for a frame.
palette = theme.apply(settings)
st.title("Settings")
profile_banner(settings.profile)

st.caption("How this assistant is configured to answer your questions.")

# --------------------------------------------------------------------------------------------------
# Assistant + retrieval, side by side. Bordered containers rather than bare JSON so the page reads
# as a product surface rather than a debug dump.
# --------------------------------------------------------------------------------------------------
left, right = st.columns(2, gap="large")

with left, st.container(border=True):
    st.markdown("#### Assistant")
    st.markdown(
        f"**Language model** — `{settings.model.name}`  \n"
        "Runs entirely on this machine. Nothing you type and no document you upload is sent to a "
        "third-party service."
    )
    st.markdown(
        "**Answer style** — deterministic. The same question over the same documents produces the "
        "same answer, which is what makes a security finding reproducible."
        if settings.model.temperature == 0
        else "**Answer style** — varied. Repeated questions may produce different wording."
    )

with right, st.container(border=True):
    st.markdown("#### Answering from your documents")
    st.markdown(
        f"**Passages consulted per question** — {settings.retrieval.top_k}  \n"
        "Each answer is grounded in the most relevant passages from the documents you have "
        "uploaded. Every answer shows the passages it used, so you can always check the source."
    )
    if not IS_SECURE:
        st.markdown(
            "**Relevance filtering** — none. Passages are returned however poor the match, so a "
            "question the corpus cannot answer still pulls in text."
        )
    else:
        st.markdown(
            "**Relevance filtering** — active. Passages below the relevance floor are dropped "
            "rather than padded into the answer."
        )

# --------------------------------------------------------------------------------------------------
# Security posture. The one thing this lab must always state plainly.
# --------------------------------------------------------------------------------------------------
st.divider()

with st.container(border=True):
    st.markdown("#### Security posture")
    try:
        policies = api.health().get("security_policies", [])
    except ApiError:
        policies = None

    if policies is None:
        st.warning("The API is not responding, so the active controls cannot be confirmed.")
    elif policies:
        st.success(f"**{len(policies)} security controls active.**")
        # Names only. What each one does is documentation, not a runtime disclosure.
        st.markdown("  \n".join(f"• `{name}`" for name in policies))
    else:
        st.error(
            "**No security controls are active.** This build follows instructions found in "
            "uploaded documents and will disclose its own configuration on request. That is "
            "intentional, and it is why this application must only ever run on a local lab machine."
        )

st.caption(
    "Operators: the full effective configuration lives in `configs/config.yaml` and "
    "`profiles/<profile>/config.yaml`, and the runtime view is on the API's `/health` endpoint."
)

# The theme switch lives in the sidebar on every page, so an operator who lands on a theme they
# cannot read never has to navigate somewhere else to fix it.
