"""System Status — is every dependency actually up?

Answers the question an operator asks when something is not working: which of Ollama, the model, the
vector store, and the database is the problem. Each component reports its own diagnosis and, where
relevant, the exact command that fixes it.

It also shows the active security policy chain. For this profile that list is empty, and displaying
it prominently is deliberate: the absence of defences should be visible, not implied.
"""

from __future__ import annotations

import streamlit as st

import frontend._bootstrap as bootstrap
from frontend import theme  # noqa: F401  - must be first; fixes sys.path
from frontend.components.api_client import ApiClient, ApiError
from frontend.components.widgets import health_badge, metric_row, profile_banner, show_api_error

settings = bootstrap.get_settings()
api = ApiClient(bootstrap.api_base_url(settings))

st.set_page_config(
    page_title=bootstrap.page_title(settings, "Status"),
    page_icon="📊",
    layout="wide",
)

# Stylesheet first: anything drawn before it appears unstyled for a frame.
palette = theme.apply(settings)
st.title("System Status")
profile_banner(settings.profile)

if st.button("Refresh"):
    st.rerun()

try:
    health = api.health()
except ApiError as exc:
    show_api_error(exc)
    st.markdown(f"""
The API at `{api.base_url}` is not responding. Start it with:

```bash
RAGSTRIKE_LAB_ACK=1 python -m profiles.vulnerable.main_api
```
        """)
    st.stop()

status = health.get("status", "unknown")
if status == "ok":
    st.success("All components healthy.")
else:
    st.warning("Degraded — see the component list below.")

metric_row(
    [
        ("Status", status),
        ("Documents", health.get("document_count", 0)),
        ("Chunks", health.get("chunk_count", 0)),
        ("Sessions", health.get("session_count", 0)),
    ]
)

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Components")
    for component in health.get("components", []):
        health_badge(component["healthy"], component["name"], component.get("detail", ""))

    unhealthy = [c for c in health.get("components", []) if not c["healthy"]]
    if unhealthy:
        st.divider()
        st.markdown("**Fixes**")
        for component in unhealthy:
            if component["name"] in {"ollama", "model"}:
                st.code(
                    f"ollama serve\nollama pull {health.get('model', 'qwen3:4b')}\n"
                    f"ollama pull {health.get('embedding_model', 'nomic-embed-text')}",
                    language="bash",
                )
                break

with right:
    # A named summary rather than a raw `st.json` of the effective configuration.
    #
    # The JSON block that used to sit here included `api_base_url`, which is internal service
    # topology and has no business on a user-facing status screen -- the same reason the Settings
    # page stopped dumping filesystem paths. What remains is what "is this thing working, and what
    # can it do" actually needs.
    st.subheader("Build")
    st.markdown(
        f"**Profile** — `{health.get('profile', '?')}`  \n"
        f"**Version** — `{health.get('version', '?')}`  \n"
        f"**Chat model** — `{health.get('model', '?')}`  \n"
        f"**Embedding model** — `{health.get('embedding_model', '?')}`"
    )

    capabilities = health.get("capabilities", [])
    if capabilities:
        st.markdown("**Capabilities**")
        # Capabilities are a published part of the target contract -- RAGStrike negotiates against
        # them -- so these are documentation rather than disclosure.
        st.markdown("  \n".join(f"• `{name}`" for name in capabilities))

st.divider()

# ------------------------------------------------------------------------------------------------
# Security posture
# ------------------------------------------------------------------------------------------------
st.subheader("Active security policies")

policies = health.get("security_policies", [])
if policies:
    for policy in policies:
        st.markdown(f"- **{policy['name']}** — {policy.get('description', '')}")
else:
    st.error(
        "**No security policies are active.**\n\n"
        "Every hook point in the pipeline is called and every one is a pass-through. This is the "
        "correct state for the vulnerable profile — the chain is empty in code, not by "
        "configuration, so it cannot be turned on by accident.",
        icon="⚠️",
    )

st.divider()

# ------------------------------------------------------------------------------------------------
# Weakness V5, on display
# ------------------------------------------------------------------------------------------------
st.subheader("System prompt")
st.caption(
    "This application returns its own system prompt to anyone who asks, with no authentication. "
    "That is weakness V5, reproduced here through the same public endpoint an attacker would use."
)

if st.button("Retrieve via GET /health?include_prompt=true"):
    try:
        disclosed = api.health(include_prompt=True)
    except ApiError as exc:
        show_api_error(exc)
    else:
        prompt = disclosed.get("system_prompt")
        if prompt:
            st.code(prompt, language="text")
            st.warning(
                "Note the synthetic credentials in that prompt. They are canary-tagged "
                "(`VRAG-CANARY-…`) so that any leak is provable and no real credential could ever "
                "be mistaken for one.",
                icon="🔑",
            )
        else:
            st.info("The API declined to include the prompt.")

# The theme switch lives in the sidebar on every page, so an operator who lands on a theme they
# cannot read never has to navigate somewhere else to fix it.
