"""The lab UI's visual layer: palette, stylesheet, theme toggle, and persisted preferences.

WHY THIS EXISTS
    Both lab applications shipped on stock Streamlit styling. That was acceptable while they were
    only ever driven by a scanner, but they are the thing an audience actually looks at during a
    demonstration -- and "enterprise document assistant" is the impression they need to give, not
    "someone's notebook".

    It also fixes two concrete defects:

    * **There was no theme control at all.** The RAGStrike console had one; the labs did not, so a
      dark-mode user got a white chat window beside a dark console.
    * **Sidebar choices did not survive.** `top_k` and the two inspection checkboxes reset on every
      browser refresh, because `st.session_state` is discarded when the page reloads.

ONE FILE, BOTH LABS
    This module is byte-identical in VulnerableRAG and SecureRAG, like the rest of ``frontend/``.
    The two applications must look the same: if they did not, a difference in a scan result could be
    argued to come from the interface rather than from the security controls, which is the one
    confusion this project exists to remove. Nothing here reads the profile except the accent, and
    that is a *label*, never a functional difference.

WHY THE CSS IS GENERATED RATHER THAN A STATIC FILE
    Every rule refers to a custom property, and the properties come from the palette. Switching
    theme is therefore one re-render with different variables -- no component knows a theme exists.
    A static file would need one copy per theme and would drift the moment someone added a colour.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

# --------------------------------------------------------------------------------------------------
# Palettes
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Palette:
    """Every colour the lab UI draws. Nothing outside this module hardcodes a hex value."""

    name: str
    bg: str
    surface: str
    surface_raised: str
    border: str
    text: str
    text_muted: str
    text_faint: str
    accent: str
    accent_soft: str
    ok: str
    warn: str
    danger: str


DARK = Palette(
    name="dark",
    bg="#0e1117",
    surface="#161b24",
    surface_raised="#1d232e",
    border="#2a3240",
    text="#e6edf3",
    text_muted="#9aa7b4",
    text_faint="#6b7887",
    accent="#3ba3ff",
    accent_soft="rgba(59,163,255,0.14)",
    ok="#2e9e6b",
    warn="#c78a2a",
    danger="#d0453f",
)

LIGHT = Palette(
    name="light",
    bg="#f6f8fa",
    surface="#ffffff",
    surface_raised="#fbfcfe",
    border="#dde3ea",
    text="#111820",
    text_muted="#5a6674",
    text_faint="#8492a1",
    accent="#0b6bcb",
    accent_soft="rgba(11,107,203,0.10)",
    ok="#1b7a4f",
    warn="#9a6a10",
    danger="#b3261e",
)

_PALETTES = {p.name: p for p in (DARK, LIGHT)}

#: Preferences mirrored into the URL so they survive a browser refresh. Streamlit's session state
#: does not, which is why every sidebar choice used to reset on F5.
#:
#: Short names because they are visible in the address bar. Nothing sensitive goes here -- a URL
#: reaches browser history and server logs -- so this is display preferences only.
PERSISTED_PREFS: dict[str, str] = {
    "theme": "t",
    "top_k": "k",
    "show_prompt": "sp",
    "show_raw": "sr",
}

#: The preference name. ``remember()``/``preference()`` store it at session key ``lab.theme``.
_PREF_KEY = "theme"

#: The TOGGLE WIDGET's key -- deliberately NOT ``lab.theme``.
#:
#: They were the same key once, and every page of both labs crashed on load:
#:
#:     StreamlitAPIException: `st.session_state.lab.theme` cannot be modified after the
#:     widget with key `lab.theme` is instantiated.
#:
#: Streamlit locks a widget's key the moment the widget is drawn, and ``remember()`` writes the
#: preference straight afterwards. One name serving as both the widget's identity and the stored
#: preference cannot work -- the write is always "after". Keeping them separate is the fix, and it
#: also keeps the two concerns honest: the widget holds what the checkbox is showing right now,
#: the preference holds what the operator chose.
_TOGGLE_KEY = "lab.theme.toggle"

#: The preference value most recently pushed into the widget, so the seeding step below runs only
#: when the preference actually changed rather than fighting the widget on every rerun.
_SYNCED_KEY = "lab.theme.synced"


def palette_for(name: str) -> Palette:
    """Look up a palette, falling back to dark.

    Falls back rather than raising: a hand-edited URL should not be able to break the page.
    """
    return _PALETTES.get(name, DARK)


# --------------------------------------------------------------------------------------------------
# Preferences
# --------------------------------------------------------------------------------------------------


def load_preferences() -> None:
    """Seed session state from the URL. Call once per page, before anything reads a preference."""
    params = st.query_params
    for key, param in PERSISTED_PREFS.items():
        state_key = f"lab.{key}"
        if state_key in st.session_state:
            continue
        raw = params.get(param)
        if raw in (None, ""):
            continue
        st.session_state[state_key] = _coerce(key, raw)


def remember(key: str, value: Any) -> None:
    """Store a preference and mirror it into the URL, so a refresh keeps it."""
    st.session_state[f"lab.{key}"] = value
    param = PERSISTED_PREFS.get(key)
    if param:
        st.query_params[param] = _encode(value)


def preference(key: str, default: Any) -> Any:
    """Read a preference, falling back to *default*."""
    return st.session_state.get(f"lab.{key}", default)


def _coerce(key: str, raw: str) -> Any:
    """URL values are strings; restore the type the widget expects."""
    if key in {"show_prompt", "show_raw"}:
        return raw == "1"
    if key == "top_k":
        try:
            return int(raw)
        except ValueError:
            return None
    return raw


def _encode(value: Any) -> str:
    return "1" if value is True else "0" if value is False else str(value)


# --------------------------------------------------------------------------------------------------
# The stylesheet
# --------------------------------------------------------------------------------------------------


def _css(palette: Palette) -> str:
    return f"""
<style>
:root {{
  --lab-bg: {palette.bg};
  --lab-surface: {palette.surface};
  --lab-raised: {palette.surface_raised};
  --lab-border: {palette.border};
  --lab-text: {palette.text};
  --lab-muted: {palette.text_muted};
  --lab-faint: {palette.text_faint};
  --lab-accent: {palette.accent};
  --lab-accent-soft: {palette.accent_soft};
  --lab-ok: {palette.ok};
  --lab-warn: {palette.warn};
  --lab-danger: {palette.danger};
  --lab-radius: 10px;

  /* Streamlit's OWN theme variables, redefined from the palette. This is what makes the toggle
     repaint native widgets rather than only our own markup -- without it the page is half dark. */
  --background-color: {palette.bg};
  --secondary-background-color: {palette.surface};
  --text-color: {palette.text};
  --primary-color: {palette.accent};
}}

html, body, .stApp,
[data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
  background: var(--lab-bg);
  color: var(--lab-text);
  /* Leads with faces that may not be installed, then falls through to ones that are. The project
     runs offline, so a webfont is not an option and an unresolvable stack drops to Times. */
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto,
               'Helvetica Neue', 'Noto Sans', 'Liberation Sans', Arial, sans-serif;
}}
[data-testid="stHeader"] {{ border-bottom: 1px solid var(--lab-border); }}
[data-testid="stMainBlockContainer"], section.main > div.block-container {{ max-width: 1180px; }}

h1, h2, h3, h4, h5, h6, p, span, label, li, div {{ color: var(--lab-text); }}
h1 {{ font-weight: 650; letter-spacing: -0.02em; }}
a, a:visited {{ color: var(--lab-accent); }}
[data-testid="stCaptionContainer"], small {{ color: var(--lab-muted) !important; }}

/* -- sidebar ------------------------------------------------------------------------------- */
[data-testid="stSidebar"] {{
  background: var(--lab-surface);
  border-right: 1px solid var(--lab-border);
}}
[data-testid="stSidebar"] * {{ color: var(--lab-text); }}

/* -- cards --------------------------------------------------------------------------------- */
[data-testid="stVerticalBlockBorderWrapper"] {{
  border-radius: var(--lab-radius) !important;
  border-color: var(--lab-border) !important;
  background: var(--lab-surface);
}}

/* -- inputs -------------------------------------------------------------------------------- */
input, textarea, select,
.stTextInput input, .stNumberInput input, .stTextArea textarea {{
  background: var(--lab-raised) !important;
  color: var(--lab-text) !important;
  border: 1px solid var(--lab-border) !important;
  border-radius: 8px !important;
}}
input::placeholder, textarea::placeholder {{ color: var(--lab-faint) !important; }}
input:focus, textarea:focus {{
  border-color: var(--lab-accent) !important;
  box-shadow: 0 0 0 2px var(--lab-accent-soft) !important;
}}
[data-baseweb="select"] > div, [data-baseweb="input"] > div {{
  background: var(--lab-raised) !important;
  border-color: var(--lab-border) !important;
  border-radius: 8px !important;
}}
[data-baseweb="popover"], [role="listbox"] {{
  background: var(--lab-raised) !important;
  border: 1px solid var(--lab-border) !important;
}}

/* -- buttons ------------------------------------------------------------------------------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
  border-radius: 8px;
  font-weight: 600;
  border: 1px solid var(--lab-border);
  background: var(--lab-raised);
  color: var(--lab-text);
  transition: background .12s ease, border-color .12s ease;
}}
.stButton > button:hover {{ border-color: var(--lab-accent); background: var(--lab-accent-soft); }}
.stButton > button[kind="primary"] {{
  background: var(--lab-accent); border-color: var(--lab-accent); color: #fff;
}}

/* -- the file drop zone -------------------------------------------------------------------- */
[data-testid="stFileUploaderDropzone"] {{
  background: var(--lab-raised);
  border: 1.5px dashed var(--lab-border);
  border-radius: var(--lab-radius);
  transition: border-color .15s ease, background .15s ease;
}}
[data-testid="stFileUploaderDropzone"]:hover {{
  border-color: var(--lab-accent);
  background: var(--lab-accent-soft);
}}

/* -- the conversation feed ------------------------------------------------------------------ */
[data-testid="stChatMessage"] {{
  background: var(--lab-surface);
  border: 1px solid var(--lab-border);
  border-radius: var(--lab-radius);
  padding: 14px 16px;
  margin-bottom: 10px;
}}
/* The assistant's turn carries a left rule in the accent, so the eye can find answers when
   scrolling a long conversation without reading the avatars. */
[data-testid="stChatMessage"]:nth-child(even) {{ border-left: 3px solid var(--lab-accent); }}
[data-testid="stChatInput"] textarea {{ background: var(--lab-raised) !important; }}

/* -- expanders, code, alerts ---------------------------------------------------------------- */
div[data-testid="stExpander"] details {{
  border: 1px solid var(--lab-border);
  border-radius: var(--lab-radius);
  background: var(--lab-surface);
}}
code, pre, [data-testid="stCode"] {{
  background: var(--lab-raised) !important;
  color: var(--lab-text) !important;
  border-radius: 8px;
  font-family: 'JetBrains Mono', ui-monospace, 'DejaVu Sans Mono',
               'Liberation Mono', Consolas, monospace !important;
}}
[data-testid="stAlert"] {{ border-radius: var(--lab-radius); }}

/* -- the profile banner --------------------------------------------------------------------- */
.lab-banner {{
  border-radius: var(--lab-radius);
  padding: 12px 16px;
  margin-bottom: 14px;
  font-size: 0.9rem;
  border: 1px solid;
}}
.lab-banner--vulnerable {{
  background: rgba(208,69,63,0.10); border-color: var(--lab-danger); color: var(--lab-text);
}}
.lab-banner--secure {{
  background: rgba(46,158,107,0.10); border-color: var(--lab-ok); color: var(--lab-text);
}}
.lab-banner__title {{ font-weight: 700; letter-spacing: .04em; text-transform: uppercase;
                      font-size: .74rem; }}

/* -- scrollbars, so dark is dark to the edges ----------------------------------------------- */
* {{ scrollbar-color: var(--lab-border) transparent; }}
::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{
  background: var(--lab-border); border-radius: 999px; border: 2px solid var(--lab-bg);
}}

#MainMenu, footer {{ visibility: hidden; }}
</style>
"""


# --------------------------------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------------------------------


def apply(settings: Any) -> Palette:
    """Load preferences, write the stylesheet, and return the active palette.

    Call once per page, immediately after ``st.set_page_config``. Anything rendered before it
    appears unstyled for a frame.
    """
    load_preferences()
    palette = palette_for(str(preference("theme", "dark")))
    st.markdown(_css(palette), unsafe_allow_html=True)
    return palette


def render_theme_toggle() -> None:
    """The dark/light switch. Draw it inside a ``with st.sidebar:`` block.

    Order matters here, and it is the whole reason this is a function rather than two lines at each
    call site. The widget must be SEEDED BEFORE it is drawn, because Streamlit refuses writes to a
    widget's key afterwards -- and a widget with a key ignores its ``value=`` argument once it holds
    state, so seeding is the only way the stored preference reaches the switch at all.
    """
    current = str(preference(_PREF_KEY, "dark"))

    # Seed first, draw second. Never the other way round.
    if st.session_state.get(_SYNCED_KEY) != current:
        st.session_state[_TOGGLE_KEY] = current != "light"
        st.session_state[_SYNCED_KEY] = current

    wants_dark = st.toggle("Dark theme", key=_TOGGLE_KEY, help="Remembered across a refresh.")

    chosen = "dark" if wants_dark else "light"
    if chosen != current:
        # Writes `lab.theme`, which is NOT the widget's key -- see _TOGGLE_KEY.
        remember(_PREF_KEY, chosen)
        st.session_state[_SYNCED_KEY] = chosen
        # Re-run so the stylesheet is rebuilt from the new palette; without it the switch appears
        # to do nothing until the operator's next interaction.
        st.rerun()
