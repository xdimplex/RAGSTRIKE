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

# REBUILD THE TRANSCRIPT AFTER A REFRESH.
#
# Streamlit throws session state away on F5, so the turns list came back empty while the session id
# survived in the URL. The conversation was still on the server -- and still being replayed into
# every subsequent prompt -- but the screen showed none of it, which reads as "my chat vanished".
#
# Only the question and answer are restored. The per-turn diagnostics (timings, chunk counts) are
# not recorded server-side, and inventing them would be worse than omitting them.
if st.session_state[SESSION_KEY] and not st.session_state[TURNS_KEY]:
    with contextlib.suppress(ApiError):
        recorded = api.session_history(st.session_state[SESSION_KEY]).get("turns", [])
        restored: list[dict] = []
        for turn in recorded:
            if turn.get("role") == "user":
                restored.append({"question": turn.get("content", ""), "answer": ""})
            elif restored:
                restored[-1]["answer"] = turn.get("content", "")
        st.session_state[TURNS_KEY] = [
            {
                "question": t["question"],
                "answer": t["answer"],
                "elapsed_ms": 0,
                "chunk_count": 0,
                "model": "",
                "sources": [],
                "retrieved_chunks": [],
            }
            for t in restored
            if t["answer"]
        ]

# ------------------------------------------------------------------------------------------------
# Controls
# ------------------------------------------------------------------------------------------------
# QUERY OPTIONS REMOVED.
#
# The sidebar carried a retrieval-depth slider and three diagnostic checkboxes. None of them belong
# in front of a person asking a question about a document: `top_k` is a retrieval-tuning knob whose
# correct value is the one in `configs/config.yaml`, and the other three expose the assembled
# prompt, the raw model output, and the retrieved chunks -- internal detail, and on the HARDENED lab
# detail that should not be leaving the system at all.
#
# The values still exist as configuration; what is gone is the invitation for a user to change them.
# The demo in GUIDE/ shows retrieval through the scanner, which is where that belongs.
top_k = int(settings.retrieval.top_k)
show_prompt = False
show_raw = False
show_retrieval = False

# THE SIDEBAR SESSION PANEL WAS REMOVED.
#
# It showed the raw conversation id and a "New session" button. The id is an internal database key
# -- a reader gains nothing from seeing 32 characters of hex, and it made the panel look like debug
# output left switched on. The session still exists and is still carried in the URL; it is simply
# not put in front of the user.
#
# Starting a fresh conversation is now "Clear chat", at the bottom of the page where the
# conversation ends, rather than a control competing with the navigation.

# ------------------------------------------------------------------------------------------------
# History
# ------------------------------------------------------------------------------------------------
for turn in st.session_state[TURNS_KEY]:
    with st.chat_message("user"):
        st.write(turn["question"])
    with st.chat_message("assistant"):
        st.write(turn["answer"])
        # The diagnostics are behind the sidebar's "Show retrieval details". A reader asking about a
        # document does not need the chunk indices and relevance scores that produced the answer, and
        # on the hardened lab they are internal detail with no reason to leave the system.
        if show_retrieval:
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
        "Ask a question about the documents you have uploaded. Answers are drawn from those "
        "documents."
    )

# The theme switch lives in the sidebar on every page, so an operator who lands on a theme they
# cannot read never has to navigate somewhere else to fix it.
