"""Chat — ask questions and see exactly what produced the answer.

Every answer is shown with its retrieved chunks, its sources, its response time, and its chunk count.
The assembled prompt is available on request.

That transparency is the point. An injection you cannot inspect is an injection you can only guess
at; being able to read the exact text that reached the model is what turns "the answer looks odd"
into "here is the instruction, in chunk 2, from this document".
"""

from __future__ import annotations

import contextlib

import streamlit as st

import frontend._bootstrap as bootstrap
from frontend import theme  # noqa: F401  - must precede any project import
from frontend.components.api_client import ApiClient, ApiError
from frontend.components.widgets import chunk_viewer, profile_banner, show_api_error, source_list

settings = bootstrap.get_settings()
api = ApiClient(bootstrap.api_base_url(settings))

st.set_page_config(
    page_title=bootstrap.page_title(settings, "Chat"),
    page_icon="💬",
    layout="wide",
)

# Stylesheet first: anything drawn before it appears unstyled for a frame.
palette = theme.apply(settings)
st.title("Chat")
profile_banner(settings.profile)

# ------------------------------------------------------------------------------------------------
# Conversation state
#
# WHY THE KEYS ARE NAMESPACED AND SEEDED FROM THE URL
#     The chat used to vanish when the operator clicked Upload Documents and came back. Two causes,
#     and both had to be fixed:
#
#     1. Streamlit discards `st.session_state` when the websocket drops. The starlette/streamlit
#        incompatibility fixed earlier in this project made every gzipped response 500, which killed
#        the connection constantly -- so the session reset mid-conversation.
#     2. Session state never survives a browser refresh at all.
#
#     The session id is now mirrored into the URL, so a refresh or a reconnect rejoins the SAME
#     server-side conversation instead of silently starting a new one. The turns themselves stay in
#     session state: they can be long, and a URL is not a transcript store.
#
#     `chat.` prefixes keep these from colliding with any other page's state -- generic names like
#     "turns" are exactly the kind of thing two pages pick independently.
# ------------------------------------------------------------------------------------------------
SESSION_KEY = "chat.session_id"
TURNS_KEY = "chat.turns"

if SESSION_KEY not in st.session_state:
    # A session id in the URL means "rejoin that conversation" -- after a refresh, or after the
    # connection dropped and Streamlit handed us a brand-new session.
    st.session_state[SESSION_KEY] = st.query_params.get("s") or None
if TURNS_KEY not in st.session_state:
    st.session_state[TURNS_KEY] = []

# ------------------------------------------------------------------------------------------------
# Controls
# ------------------------------------------------------------------------------------------------
with st.sidebar:
    st.subheader("Query options")

    # Every one of these is seeded from, and written back to, the URL. They used to reset on every
    # browser refresh -- so an operator who set up an inspection view, refreshed, and asked their
    # question again silently got a DIFFERENT view than the one they had configured.
    top_k = st.slider(
        "Passages to retrieve",
        1,
        20,
        int(theme.preference("top_k", settings.retrieval.top_k)),
        help="How many document passages are consulted for each answer.",
    )
    if top_k != theme.preference("top_k", settings.retrieval.top_k):
        theme.remember("top_k", top_k)

    show_prompt = st.checkbox(
        "Show the assembled prompt",
        value=bool(theme.preference("show_prompt", False)),
        help="Returns the exact text sent to the model, including the system prompt.",
    )
    if show_prompt != bool(theme.preference("show_prompt", False)):
        theme.remember("show_prompt", show_prompt)

    show_raw = st.checkbox(
        "Show raw model output",
        value=bool(theme.preference("show_raw", False)),
        help="Before post-processing. An injection is often visible here first.",
    )
    if show_raw != bool(theme.preference("show_raw", False)):
        theme.remember("show_raw", show_raw)

    st.divider()
    st.caption(
        f"Session: `{st.session_state[SESSION_KEY] or 'new'}`\n\n"
        f"History is **unbounded** (weakness V8): every prior turn is replayed into every prompt."
    )
    if st.button("New session"):
        if st.session_state[SESSION_KEY]:
            # The session may not exist server-side yet; clearing it locally is enough either way.
            with contextlib.suppress(ApiError):
                api.reset_session(st.session_state[SESSION_KEY])
        st.session_state[SESSION_KEY] = None
        st.session_state[TURNS_KEY] = []
        # Drop it from the URL too, or the next refresh would rejoin the conversation the operator
        # just asked to end.
        st.query_params.pop("s", None)
        st.rerun()

# ------------------------------------------------------------------------------------------------
# History
# ------------------------------------------------------------------------------------------------
for turn in st.session_state[TURNS_KEY]:
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        st.write(turn["answer"])
        meta = st.columns(3)
        meta[0].caption(f"⏱ {turn['elapsed_ms']} ms")
        meta[1].caption(f"📄 {turn['chunk_count']} chunks")
        meta[2].caption(f"🤖 {turn['model']}")
        source_list(turn.get("sources", []))
        with st.expander("Retrieved context"):
            chunk_viewer(turn.get("retrieved_chunks", []))
        if turn.get("prompt"):
            with st.expander("Assembled prompt (exactly what the model received)"):
                st.code(turn["prompt"], language="text")
        if turn.get("raw_response"):
            with st.expander("Raw model output"):
                st.code(turn["raw_response"], language="text")

# ------------------------------------------------------------------------------------------------
# Input
# ------------------------------------------------------------------------------------------------
question = st.chat_input("Ask a question about the ingested documents…")

if question:
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"), st.spinner("Thinking…"):
        try:
            result = api.chat(
                question,
                session_id=st.session_state[SESSION_KEY],
                top_k=top_k,
                include_prompt=show_prompt or show_raw,
            )
        except ApiError as exc:
            show_api_error(exc)
        else:
            st.session_state[SESSION_KEY] = result["session_id"]
            # Mirror it into the URL. This is what lets a refresh, or a dropped websocket, rejoin
            # the same server-side conversation rather than silently starting a fresh one -- which
            # matters here beyond convenience, because session memory is itself under test (V8).
            st.query_params["s"] = str(result["session_id"])
            st.session_state[TURNS_KEY].append(
                {
                    "question": question,
                    "answer": result["answer"],
                    "elapsed_ms": result["elapsed_ms"],
                    "chunk_count": result["chunk_count"],
                    "model": result["model"],
                    "sources": result.get("sources", []),
                    "retrieved_chunks": result.get("retrieved_chunks", []),
                    "prompt": result.get("prompt") if show_prompt else None,
                    "raw_response": result.get("raw_response") if show_raw else None,
                }
            )
            st.rerun()

if not st.session_state[TURNS_KEY]:
    st.info(
        "Ask something about your documents. Every answer arrives with the chunks that produced it, "
        "so you can always check whether the model used the corpus — or something the corpus told "
        "it to do."
    )

# The theme switch lives in the sidebar on every page, so an operator who lands on a theme they
# cannot read never has to navigate somewhere else to fix it.
with st.sidebar:
    st.divider()
    theme.render_theme_toggle()
