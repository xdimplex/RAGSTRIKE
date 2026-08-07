"""Centralized session state.

Streamlit re-runs the whole script on every interaction, so anything that must survive a click lives
in ``st.session_state``. Left to itself that becomes a global dictionary with string keys typed by
hand at forty call sites, and the first typo is a silent no-op.

This package gives it one key registry and one typed accessor.
"""

from ragstrike.dashboard.state.keys import STATE_KEYS, StateKey
from ragstrike.dashboard.state.store import AppState, session_state

__all__ = ["STATE_KEYS", "AppState", "StateKey", "session_state"]
