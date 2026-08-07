"""The stylesheet, generated from a palette and the design tokens.

WHY GENERATED AND NOT A .CSS FILE
    Every component emits HTML that refers to ``var(--rs-*)``. Generating the variable block from a
    :class:`~ragstrike.dashboard.theme.palette.Palette` means switching theme is a single re-render
    with different variables -- no component knows a theme exists. A static file would need one copy
    per theme and would drift the moment someone added a colour.

WHY IT OVERRIDES STREAMLIT
    Streamlit's defaults read as a notebook. A security console needs denser rows, flatter surfaces,
    and a monospace bias for evidence. The overrides below are limited to spacing, surface, and type
    -- not to behaviour -- so a Streamlit upgrade degrades the look rather than breaking the app.
"""

from __future__ import annotations

from ragstrike.dashboard.theme.palette import Palette
from ragstrike.dashboard.theme.tokens import TOKENS, Tokens


def css_variables(palette: Palette, tokens: Tokens = TOKENS) -> str:
    """The ``:root`` custom-property block. Kept separate so tests can assert on it directly."""
    return f"""
:root {{
  --rs-bg: {palette.background};
  --rs-surface: {palette.surface};
  --rs-surface-raised: {palette.surface_raised};
  --rs-border: {palette.border};
  --rs-border-strong: {palette.border_strong};
  --rs-text: {palette.text};
  --rs-text-muted: {palette.text_muted};
  --rs-text-faint: {palette.text_faint};
  --rs-accent: {palette.accent};
  --rs-accent-soft: {palette.accent_soft};
  --rs-ok: {palette.ok};
  --rs-warn: {palette.warn};
  --rs-danger: {palette.danger};
  --rs-info: {palette.info};
  --rs-neutral: {palette.neutral};
  --rs-critical: {palette.critical};
  --rs-high: {palette.high};
  --rs-medium: {palette.medium};
  --rs-low: {palette.low};
  --rs-informational: {palette.informational};
  --rs-space-xs: {tokens.space_xs};
  --rs-space-sm: {tokens.space_sm};
  --rs-space-md: {tokens.space_md};
  --rs-space-lg: {tokens.space_lg};
  --rs-space-xl: {tokens.space_xl};
  --rs-radius-sm: {tokens.radius_sm};
  --rs-radius-md: {tokens.radius_md};
  --rs-radius-lg: {tokens.radius_lg};
  --rs-font-mono: {tokens.font_mono};
  --rs-font-sans: {tokens.font_sans};
  --rs-text-xs: {tokens.text_xs};
  --rs-text-sm: {tokens.text_sm};
  --rs-text-md: {tokens.text_md};
  --rs-text-lg: {tokens.text_lg};
  --rs-text-xl: {tokens.text_xl};
  --rs-text-hero: {tokens.text_hero};
  --rs-tracking: {tokens.label_tracking};
}}
""".strip()


_COMPONENTS = """
.rs-label {
  font-size: var(--rs-text-xs);
  letter-spacing: var(--rs-tracking);
  text-transform: uppercase;
  color: var(--rs-text-faint);
  font-weight: 600;
}

/* Panels, not cards.
 *
 * A card floats; a panel is a bounded region of a workspace. The distinction is the whole visual
 * difference between a dashboard and a tool: Burp Suite, Wireshark and a SIEM are built from
 * abutting panels with hard edges and their own header strips, so the eye can tell instantly which
 * region it is reading. Softer, floating cards with generous padding read as a web page.
 *
 * A top accent rule replaces the drop shadow -- shadows imply layers above the page, which is the
 * wrong metaphor for a fixed workspace. */
.rs-card {
  position: relative;
  background: var(--rs-surface);
  border: 1px solid var(--rs-border);
  border-radius: var(--rs-radius-sm);
  padding: var(--rs-space-md) var(--rs-space-md);
  margin-bottom: var(--rs-space-sm);
}
.rs-card::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 2px;
  background: linear-gradient(90deg, var(--rs-border-strong), transparent 65%);
  border-radius: var(--rs-radius-sm) var(--rs-radius-sm) 0 0;
}
.rs-card--raised { background: var(--rs-surface-raised); }
.rs-card__title {
  font-size: var(--rs-text-md);
  font-weight: 600;
  color: var(--rs-text);
  margin: 0;
}
.rs-card__body { color: var(--rs-text-muted); font-size: var(--rs-text-sm); }
.rs-card__foot {
  border-top: 1px solid var(--rs-border);
  margin-top: var(--rs-space-md);
  padding-top: var(--rs-space-sm);
  font-size: var(--rs-text-xs);
  color: var(--rs-text-faint);
}

/* The accent rail is what makes a wall of cards scannable: colour is on the edge, not the fill,
   so twelve HIGH findings do not turn the page into a warning light. */
.rs-card--accented { border-left: 3px solid var(--rs-accent); }

.rs-metric { display: flex; flex-direction: column; gap: var(--rs-space-xs); }
.rs-metric__value {
  font-size: var(--rs-text-xl);
  font-weight: 650;
  color: var(--rs-text);
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}
.rs-metric__delta { font-size: var(--rs-text-xs); font-weight: 600; }
.rs-metric__hint { font-size: var(--rs-text-xs); color: var(--rs-text-faint); }

.rs-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: var(--rs-text-xs);
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
  border: 1px solid currentColor;
}
.rs-badge__dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: currentColor; flex: 0 0 auto;
}

.rs-grade {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 74px; height: 74px;
  border-radius: var(--rs-radius-lg);
  font-size: var(--rs-text-hero);
  font-weight: 700;
  border: 2px solid currentColor;
  line-height: 1;
}

.rs-bar {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: var(--rs-border);
  overflow: hidden;
}
.rs-bar__fill { height: 100%; border-radius: 999px; transition: width 240ms ease; }
.rs-bar__meta {
  display: flex; justify-content: space-between;
  font-size: var(--rs-text-xs); color: var(--rs-text-faint);
  margin-top: var(--rs-space-xs);
}

.rs-stack { display: flex; flex-direction: column; gap: var(--rs-space-xs); }
.rs-row { display: flex; align-items: center; gap: var(--rs-space-sm); flex-wrap: wrap; }
.rs-row--split { justify-content: space-between; }

.rs-log {
  background: var(--rs-bg);
  border: 1px solid var(--rs-border);
  border-radius: var(--rs-radius-sm);
  font-family: var(--rs-font-mono);
  font-size: var(--rs-text-xs);
  line-height: 1.55;
  max-height: 340px;
  overflow-y: auto;
  padding: var(--rs-space-sm) var(--rs-space-md);
}
.rs-log__line { display: flex; gap: var(--rs-space-sm); white-space: pre-wrap; word-break: break-word; }
.rs-log__ts { color: var(--rs-text-faint); flex: 0 0 auto; }
.rs-log__lvl { flex: 0 0 62px; font-weight: 650; }

.rs-timeline { position: relative; padding-left: var(--rs-space-lg); }
.rs-timeline::before {
  content: ""; position: absolute; left: 5px; top: 4px; bottom: 4px;
  width: 2px; background: var(--rs-border);
}
.rs-timeline__item { position: relative; padding-bottom: var(--rs-space-md); }
.rs-timeline__dot {
  position: absolute; left: calc(-1 * var(--rs-space-lg) + 1px); top: 4px;
  width: 10px; height: 10px; border-radius: 50%;
  border: 2px solid var(--rs-bg);
}
.rs-timeline__title { font-size: var(--rs-text-sm); font-weight: 600; color: var(--rs-text); }
.rs-timeline__meta { font-size: var(--rs-text-xs); color: var(--rs-text-faint); }

.rs-empty {
  border: 1px dashed var(--rs-border-strong);
  border-radius: var(--rs-radius-md);
  padding: var(--rs-space-xl) var(--rs-space-lg);
  text-align: center;
  color: var(--rs-text-muted);
}
.rs-empty__icon { font-size: 1.7rem; opacity: 0.75; }
.rs-empty__title { font-size: var(--rs-text-md); font-weight: 600; color: var(--rs-text); margin-top: var(--rs-space-sm); }
.rs-empty__body { font-size: var(--rs-text-sm); margin-top: var(--rs-space-xs); }

.rs-toast {
  border-radius: var(--rs-radius-sm);
  border-left: 3px solid currentColor;
  padding: var(--rs-space-sm) var(--rs-space-md);
  font-size: var(--rs-text-sm);
  margin-bottom: var(--rs-space-sm);
}

.rs-overlay {
  display: flex; align-items: center; gap: var(--rs-space-sm);
  border: 1px solid var(--rs-border);
  background: var(--rs-surface);
  border-radius: var(--rs-radius-md);
  padding: var(--rs-space-md) var(--rs-space-lg);
  color: var(--rs-text-muted);
  font-size: var(--rs-text-sm);
}
.rs-overlay__spinner {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid var(--rs-border-strong);
  border-top-color: var(--rs-accent);
  animation: rs-spin 800ms linear infinite;
}
@keyframes rs-spin { to { transform: rotate(360deg); } }

.rs-kv { display: grid; grid-template-columns: minmax(90px, 32%) 1fr; gap: var(--rs-space-xs) var(--rs-space-md); }
.rs-kv__k { color: var(--rs-text-faint); font-size: var(--rs-text-xs); text-transform: uppercase; letter-spacing: var(--rs-tracking); }
.rs-kv__v { color: var(--rs-text); font-size: var(--rs-text-sm); word-break: break-word; }
.rs-mono { font-family: var(--rs-font-mono); font-size: var(--rs-text-xs); }

.rs-banner {
  border-radius: var(--rs-radius-sm);
  padding: var(--rs-space-sm) var(--rs-space-md);
  font-size: var(--rs-text-sm);
  border: 1px solid currentColor;
  margin-bottom: var(--rs-space-md);
}

/* The page header, as a console toolbar rather than a document title.
 *
 * A tool announces which module you are in; it does not present a headline. So: a left accent rule
 * marking the active region, a compressed title, and the subtitle inline beside it rather than
 * stacked beneath -- which recovers a whole line of vertical space on every page, on a screen where
 * the operator wants rows. */
.rs-header {
  display: flex;
  align-items: baseline;
  gap: var(--rs-space-md);
  flex-wrap: wrap;
  border-bottom: 1px solid var(--rs-border);
  border-left: 3px solid var(--rs-accent);
  padding: 0 0 var(--rs-space-sm) var(--rs-space-md);
  margin-bottom: var(--rs-space-md);
}
.rs-header__title {
  font-size: var(--rs-text-lg);
  font-weight: 650;
  color: var(--rs-text);
  margin: 0;
  letter-spacing: -0.01em;
}
.rs-header__sub {
  font-size: var(--rs-text-xs);
  color: var(--rs-text-faint);
  margin: 0;
}

/* A horizontal strip of key/value readouts -- the status rail a tool carries under its toolbar.
   Monospaced values so columns of numbers align down the page. */
.rs-rail {
  display: flex;
  flex-wrap: wrap;
  gap: var(--rs-space-lg);
  padding: var(--rs-space-sm) var(--rs-space-md);
  background: var(--rs-surface);
  border: 1px solid var(--rs-border);
  border-radius: var(--rs-radius-sm);
  margin-bottom: var(--rs-space-md);
}
.rs-rail__item { display: flex; flex-direction: column; gap: 1px; }
.rs-rail__label {
  font-size: var(--rs-text-xs);
  letter-spacing: var(--rs-tracking);
  text-transform: uppercase;
  color: var(--rs-text-faint);
}
.rs-rail__value {
  font-family: var(--rs-font-mono);
  font-size: var(--rs-text-sm);
  color: var(--rs-text);
  font-variant-numeric: tabular-nums;
}

/* Section headings inside a panel: a rule with a label sitting on it, the way a grouped control
   panel is labelled in an engineering tool. */
.rs-section {
  display: flex;
  align-items: center;
  gap: var(--rs-space-sm);
  margin: var(--rs-space-lg) 0 var(--rs-space-sm);
  font-size: var(--rs-text-xs);
  letter-spacing: var(--rs-tracking);
  text-transform: uppercase;
  color: var(--rs-text-faint);
  font-weight: 600;
}
.rs-section::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--rs-border);
}
"""

#: Fixed data tables. See `widgets/tables.py` for why these are hand-rolled rather than
#: `st.dataframe` -- in short: resizable columns, no theme, and a pandas dependency to draw text.
_TABLES = """
.rs-table-wrap {
  border: 1px solid var(--rs-border);
  border-radius: var(--rs-radius-md);
  overflow: auto;
  background: var(--rs-surface);
  margin-bottom: var(--rs-space-md);
}

.rs-table {
  /* The whole point: widths come from the stylesheet, and a user cannot drag them. */
  table-layout: fixed;
  width: 100%;
  border-collapse: collapse;
  font-size: var(--rs-text-sm);
}

.rs-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--rs-surface-raised);
  border-bottom: 1px solid var(--rs-border-strong);
  color: var(--rs-text-faint);
  font-size: var(--rs-text-xs);
  font-weight: 600;
  letter-spacing: var(--rs-tracking);
  text-transform: uppercase;
  text-align: left;
  padding: 10px 12px;
  white-space: nowrap;
}

.rs-table tbody td {
  border-bottom: 1px solid var(--rs-border);
  padding: 9px 12px;
  color: var(--rs-text);
  /* Long ids and long titles must not blow the column open; the full value is in the tooltip. */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rs-table tbody tr:last-child td { border-bottom: none; }
.rs-table tbody tr:hover td { background: var(--rs-surface-raised); }

.rs-t-mono { font-family: var(--rs-font-mono); font-size: var(--rs-text-xs); }
.rs-t-num  { text-align: right; font-variant-numeric: tabular-nums; }

.rs-t-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: var(--rs-text-xs);
  font-weight: 600;
  letter-spacing: .02em;
  background: var(--rs-neutral); color: #fff;
}

/* Outcome and severity words, coloured from the same palette the rest of the console uses. */
.rs-t-pill--fail, .rs-t-pill--critical, .rs-t-pill--f { background: var(--rs-critical); }
.rs-t-pill--error, .rs-t-pill--high, .rs-t-pill--d    { background: var(--rs-high); }
.rs-t-pill--inconclusive, .rs-t-pill--medium,
.rs-t-pill--warning, .rs-t-pill--c                    { background: var(--rs-medium); color: #1a1a1a; }
.rs-t-pill--pass, .rs-t-pill--completed,
.rs-t-pill--active, .rs-t-pill--yes, .rs-t-pill--a    { background: var(--rs-ok); }
.rs-t-pill--low, .rs-t-pill--b                        { background: var(--rs-low); }
.rs-t-pill--skipped, .rs-t-pill--informational,
.rs-t-pill--info, .rs-t-pill--no, .rs-t-pill--refused,
.rs-t-pill--cancelled, .rs-t-pill--not-run            { background: var(--rs-neutral); }
.rs-t-pill--running, .rs-t-pill--queued               { background: var(--rs-info); }
"""

#: Streamlit's own chrome.
#:
#: WHY THIS BLOCK IS LARGE
#:     It used to be ten rules, and the result was the "half dark, half light" dashboard: the custom
#:     components read `var(--rs-*)` and themed correctly, while every native widget -- inputs,
#:     selects, tabs, code blocks, alerts, the header bar -- kept Streamlit's own light defaults.
#:     Switching theme repainted half the page.
#:
#:     Streamlit exposes its own theme through CSS custom properties, so the fix is to REDEFINE
#:     those from the palette rather than to chase individual widgets. The `--background-color`
#:     group below is what makes native widgets follow the toggle; the specific selectors after it
#:     handle the few components that do not read those variables.
_STREAMLIT_OVERRIDES = """
/* Streamlit's own theme variables, driven from the active palette. This is what makes the runtime
   toggle repaint NATIVE widgets, not just our components. */
:root, .stApp {
  --background-color: var(--rs-bg);
  --secondary-background-color: var(--rs-surface);
  --text-color: var(--rs-text);
  --primary-color: var(--rs-accent);
  --font: var(--rs-font-sans);
}

/* `!important` on the surfaces, and it is load-bearing rather than lazy.
 *
 * `.streamlit/config.toml` pins `base = "dark"`, because Streamlit paints its own chrome before
 * this stylesheet reaches the browser and an unpinned base flashes white on every load. The cost
 * is that the compiled base theme is DARK even when the operator has chosen LIGHT -- and its rules
 * are emitted after ours in the cascade. Without `!important` the content repainted light while
 * the native chrome stayed dark: the "half dark, half light" console.
 *
 * The pin cannot simply be dropped: it is a static file and cannot know which theme this session
 * chose. So the stylesheet has to be authoritative for both directions, which is what this does.
 *
 * Confined to background/colour on containers. Borders, hovers, and component internals are left
 * to normal specificity so they stay overridable. */
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
  background: var(--rs-bg) !important;
  color: var(--rs-text) !important;
  font-family: var(--rs-font-sans);
}
[data-testid="stMain"], [data-testid="stMainBlockContainer"], [data-testid="stBottom"] {
  background: var(--rs-bg) !important;
}
[data-testid="stHeader"] { border-bottom: 1px solid var(--rs-border); }
[data-testid="stToolbar"] { right: 8px; }

/* Wider and tighter. A console uses the whole screen -- capping at 1500px on a 1920 display wastes
   a fifth of the width the operator is trying to read grids in -- and the top padding was pushing
   the first panel down for no reason. */
section.main > div.block-container,
[data-testid="stMainBlockContainer"] {
  padding-top: 1.1rem;
  padding-bottom: 2rem;
  max-width: 1760px;
}

/* Vertical rhythm: Streamlit's default gaps between blocks are set for prose. At console density
   they leave the page looking half-empty while the third panel sits below the fold. */
[data-testid="stVerticalBlock"] { gap: var(--rs-space-sm); }
[data-testid="stHorizontalBlock"] { gap: var(--rs-space-md); }
hr { margin: var(--rs-space-md) 0; border-color: var(--rs-border); }

/* Bordered containers become panels, matching `.rs-card`. */
[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: var(--rs-radius-sm) !important;
  border-color: var(--rs-border) !important;
  background: var(--rs-surface);
}

/* Metrics: tabular figures and a compressed label, so a row of counters reads as instrumentation
   rather than as a set of headlines. */
[data-testid="stMetric"] {
  background: var(--rs-surface);
  border: 1px solid var(--rs-border);
  border-radius: var(--rs-radius-sm);
  padding: var(--rs-space-sm) var(--rs-space-md);
}
[data-testid="stMetricLabel"] {
  font-size: var(--rs-text-xs) !important;
  letter-spacing: var(--rs-tracking);
  text-transform: uppercase;
  color: var(--rs-text-faint) !important;
}

h1, h2, h3, h4, h5, h6 { color: var(--rs-text); font-family: var(--rs-font-sans); }
p, span, label, li, div { color: var(--rs-text); }
a, a:visited { color: var(--rs-accent); }
small, .stCaption, [data-testid="stCaptionContainer"] { color: var(--rs-text-muted) !important; }

/* -- sidebar: the module rail --------------------------------------------------------------- */
[data-testid="stSidebar"], [data-testid="stSidebarContent"], [data-testid="stSidebarNav"] {
  background: var(--rs-surface) !important;   /* see the note on the .stApp rule above */
}
[data-testid="stSidebar"] {
  border-right: 1px solid var(--rs-border-strong);
}
[data-testid="stSidebar"] * { color: var(--rs-text); }
[data-testid="stSidebar"] .rs-label { padding-left: 2px; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 2px; }

/* Navigation entries read as a list of modules, left-aligned and tightly stacked, with the active
   one marked by a left rule. Centred, evenly-spaced buttons read as a menu of actions -- these are
   places, not actions. */
[data-testid="stSidebar"] .stButton > button {
  text-align: left;
  justify-content: flex-start;
  font-weight: 500;
  padding: 0.3rem 0.55rem;
  border-color: transparent;
  /* Transparent so the rail reads as one surface -- but forced, because the pinned dark base theme
     paints its own button fill and would otherwise leave dark chips on a light sidebar. */
  background: transparent !important;
  color: var(--rs-text) !important;
  border-left: 2px solid transparent;
  border-radius: var(--rs-radius-sm);
}
/* These two carry `!important` only because the base rule above had to. Equal specificity means the
   later rule wins, but `!important` outranks plain declarations regardless of order -- so without
   it here, the forced transparent background would flatten both the hover and the active item, and
   the rail would lose every affordance it has. */
[data-testid="stSidebar"] .stButton > button:hover {
  background: var(--rs-surface-raised) !important;
  border-color: transparent;
  border-left-color: var(--rs-border-strong);
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
  background: var(--rs-accent-soft) !important;
  color: var(--rs-text) !important;
  border-color: transparent;
  border-left: 2px solid var(--rs-accent);
  font-weight: 650;
}

/* -- inputs -------------------------------------------------------------------------------- */
input, textarea, select,
.stTextInput input, .stNumberInput input, .stTextArea textarea, .stDateInput input {
  background: var(--rs-surface-raised) !important;
  color: var(--rs-text) !important;
  border: 1px solid var(--rs-border) !important;
  border-radius: var(--rs-radius-sm) !important;
}
input::placeholder, textarea::placeholder { color: var(--rs-text-faint) !important; }
input:focus, textarea:focus, select:focus {
  border-color: var(--rs-accent) !important;
  box-shadow: 0 0 0 2px var(--rs-accent-soft) !important;
}
[data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="textarea"] > div {
  background: var(--rs-surface-raised) !important;
  border-color: var(--rs-border) !important;
  color: var(--rs-text) !important;
  border-radius: var(--rs-radius-sm) !important;
}
[data-baseweb="popover"], [data-baseweb="menu"], [role="listbox"] {
  background: var(--rs-surface-raised) !important;
  border: 1px solid var(--rs-border) !important;
}
[role="option"] { color: var(--rs-text) !important; }
[role="option"]:hover { background: var(--rs-accent-soft) !important; }

/* -- buttons ------------------------------------------------------------------------------- */
/* Compact, square-ish, and uniform -- toolbar controls rather than call-to-action buttons. */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  border-radius: var(--rs-radius-sm);
  font-weight: 600;
  font-size: var(--rs-text-sm);
  padding: 0.32rem 0.7rem;
  min-height: 0;
  border: 1px solid var(--rs-border-strong);
  background: var(--rs-surface-raised);
  color: var(--rs-text);
  transition: background .12s ease, border-color .12s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
  border-color: var(--rs-accent);
  background: var(--rs-accent-soft);
}
.stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
  background: var(--rs-accent);
  border-color: var(--rs-accent);
  color: #fff;
}

/* -- containers ---------------------------------------------------------------------------- */
[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; color: var(--rs-text); }
[data-testid="stMetricLabel"] { color: var(--rs-text-faint); }
div[data-testid="stExpander"] details {
  border: 1px solid var(--rs-border);
  border-radius: var(--rs-radius-md);
  background: var(--rs-surface);
}
div[data-testid="stExpander"] summary { color: var(--rs-text); }
[data-testid="stVerticalBlockBorderWrapper"] {
  border-radius: var(--rs-radius-md);
}
.stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid var(--rs-border); gap: 2px; }
.stTabs [data-baseweb="tab"] { color: var(--rs-text-muted); }
.stTabs [aria-selected="true"] { color: var(--rs-accent); }

/* -- code and evidence --------------------------------------------------------------------- */
code, pre, .stCode, [data-testid="stCode"] {
  background: var(--rs-surface-raised) !important;
  color: var(--rs-text) !important;
  border-radius: var(--rs-radius-sm);
  font-family: var(--rs-font-mono) !important;
}
[data-testid="stCode"] { border: 1px solid var(--rs-border); }

/* -- alerts -------------------------------------------------------------------------------- */
[data-testid="stAlert"] {
  background: var(--rs-surface-raised);
  border: 1px solid var(--rs-border);
  border-radius: var(--rs-radius-md);
  color: var(--rs-text);
}

/* -- the interactive grid, for anywhere it is still used ------------------------------------ */
[data-testid="stDataFrame"] {
  border: 1px solid var(--rs-border);
  border-radius: var(--rs-radius-md);
}

/* -- scrollbars, so the dark theme is dark all the way to the edges ------------------------- */
* { scrollbar-color: var(--rs-border-strong) transparent; }
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: var(--rs-border-strong);
  border-radius: 999px;
  border: 2px solid var(--rs-bg);
}

#MainMenu, footer { visibility: hidden; }

/* Responsive: the four-across metric strip becomes two-across, then one, rather than shrinking
   numbers until they are unreadable. */
@media (max-width: 1100px) { section.main > div.block-container { padding-left: 1rem; padding-right: 1rem; } }
@media (max-width: 640px) { .rs-kv { grid-template-columns: 1fr; } .rs-grade { width: 58px; height: 58px; font-size: var(--rs-text-xl); } }
"""


def stylesheet(palette: Palette, tokens: Tokens = TOKENS) -> str:
    """The complete ``<style>`` payload for one theme.

    Returned as a string rather than written to the page here, so that the theme package stays free
    of Streamlit and can be tested without one.
    """
    return "\n".join(
        [
            "<style>",
            css_variables(palette, tokens),
            _COMPONENTS,
            _TABLES,
            _STREAMLIT_OVERRIDES,
            "</style>",
        ]
    )
