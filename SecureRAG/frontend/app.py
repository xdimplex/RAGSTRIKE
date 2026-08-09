"""Lab home page — serves BOTH profiles from one file.

Streamlit entry point:

    streamlit run frontend/app.py --server.port 8601   # vulnerable
    streamlit run frontend/app.py --server.port 8602   # secure

The other pages live in ``frontend/pages/`` and Streamlit discovers them automatically.

WHY EVERYTHING HERE IS DERIVED FROM ``settings.profile``
    This file previously hardcoded "VulnerableRAG" in its title, its description, and its start
    command, and listed the nine weaknesses as though they applied. SecureRAG ships a copy of this
    same frontend, so the hardened lab introduced itself as the vulnerable one -- the most
    misleading thing either application could say about itself, and the exact opposite of what the
    differential comparison depends on a reader understanding.

    Anything that differs between the labs is now looked up from the profile, so the two can never
    drift apart again by someone editing one copy.
"""

from __future__ import annotations

import streamlit as st

import frontend._bootstrap as bootstrap
from frontend import theme  # noqa: F401  - must be first; fixes sys.path
from frontend.components.api_client import ApiClient
from frontend.components.widgets import metric_row, profile_banner

settings = bootstrap.get_settings()
api = ApiClient(bootstrap.api_base_url(settings))

APP_NAME = bootstrap.app_name(settings)
IS_SECURE = settings.profile == "secure"

st.set_page_config(
    page_title=bootstrap.page_title(settings),
    page_icon=bootstrap.app_icon(settings),
    layout="wide",
)

# Stylesheet first: anything drawn before it appears unstyled for a frame.
palette = theme.apply(settings)

st.title(APP_NAME)
st.caption(
    "A hardened Retrieval-Augmented Generation application — the control group."
    if IS_SECURE
    else "An intentionally vulnerable Retrieval-Augmented Generation application."
)

profile_banner(settings.profile)

reachable, detail = api.reachable()
if not reachable:
    st.warning(
        f"The API at `{api.base_url}` is not responding.\n\n"
        f"Start it with:\n\n"
        f"```bash\nRAGSTRIKE_LAB_ACK=1 python -m profiles.{settings.profile}.main_api\n```\n\n"
        f"Detail: `{detail}`"
    )
else:
    try:
        health = api.health()
        metric_row(
            [
                ("Documents", health.get("document_count", 0)),
                ("Chunks indexed", health.get("chunk_count", 0)),
                ("Model", health.get("model", "?")),
                ("Security policies", len(health.get("security_policies", []))),
            ]
        )
        # The policy count is the one number that distinguishes the two labs at a glance, so it is
        # explained rather than left for the reader to interpret -- in both directions.
        if IS_SECURE:
            st.caption(
                "Seven active security policies is the correct state for this profile. Compare the "
                "count against VulnerableRAG, where it is zero."
            )
        elif not health.get("security_policies"):
            st.caption(
                "Zero security policies is the correct state for this profile. The count is shown "
                "so it is never a surprise."
            )
    except Exception as exc:  # noqa: BLE001 - the home page must render regardless
        st.warning(f"Could not read health: {exc}")

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("What this is")
    if IS_SECURE:
        st.markdown("""
A working RAG application — upload PDFs, ask questions, get answers grounded in your documents —
built as the **byte-for-byte twin of VulnerableRAG with every defensive control switched on**.

It exists to be attacked *and to hold*. It is what makes a RAGStrike finding checkable: an attack
that fires against both labs is measuring something other than the control it claims to measure.

**The pipeline**

- **Ingest** — document → extract → chunk → embed → ChromaDB
- **Answer** — question → retrieve → prompt → Ollama → answer

Every stage has a policy hook. This profile registers **seven**, so every hook is enforced.
        """)
    else:
        st.markdown("""
A working RAG application — upload PDFs, ask questions, get answers grounded in your documents —
built with **every defensive control deliberately left out**.

It exists to be attacked. RAGStrike scans it, and the results are only meaningful because the
weaknesses here are known, documented, and reproducible.

**The pipeline**

- **Ingest** — document → extract → chunk → embed → ChromaDB
- **Answer** — question → retrieve → prompt → Ollama → answer

Every stage has a policy hook. This profile registers **none**, so every hook is a pass-through.
        """)

with right:
    if IS_SECURE:
        st.subheader("The seven controls")
        st.markdown("""
| Control | Closes |
|---|---|
| `context_sanitizer` | V1, V2 — strips hidden and zero-width text at ingest and chunk |
| `input_validator` | V6 — bounds length and normalizes at the HTTP boundary |
| `retrieval_filter` | V7 — drops chunks failing relevance or permission rules |
| `session_bounder` | V8 — caps how much history is replayed |
| `citation_grounder` | V9 — checks every citation against what was retrieved |
| `output_filter` | V3 — scans the answer for what must never leave |
| `secret_masker` | V4, V5 — masks credential-shaped strings in prompt and response |

The prompt template also fences retrieved context inside a **startup-random nonce**, so a document
cannot close the fence early. Details: `docs/controls.md`
        """)
    else:
        st.subheader("The nine weaknesses")
        st.markdown("""
| | Weakness |
|---|---|
| V1 | Weak prompt template — context concatenated with no delimiters |
| V2 | No context sanitization — hidden and zero-width text stored verbatim |
| V3 | No output filtering — model output returned raw |
| V4 | No secret masking — synthetic credentials sit in the system prompt |
| V5 | No prompt protection — system prompt returned on request |
| V6 | No input validation — unlimited length, no normalization |
| V7 | No retrieval filtering — no ACL, no allowlist, no scoping |
| V8 | Unbounded session memory — history replayed in full |
| V9 | Fabricated citations — sources come from model output |

Reproductions: `docs/vulnerabilities.md`
        """)

st.divider()

st.subheader("Getting started")
st.markdown("""
1. **Upload Documents** — add a PDF, or run `python scripts/seed_corpus.py` for a sample corpus.
2. **Chat** — ask a question and watch the retrieved chunks alongside the answer.
3. **System Status** — check Ollama, the vector store, and the database.
4. **Settings** — inspect the effective configuration and rebuild the index.
    """)

st.info(
    "**Safety.** This application binds to loopback and refuses to start without "
    "`RAGSTRIKE_LAB_ACK=1`. Do not change either. Read `docs/LAB_SAFETY.md`.",
    icon="🔒",
)

# The theme switch lives in the sidebar on every page, so an operator who lands on a theme they
# cannot read never has to navigate somewhere else to fix it.
