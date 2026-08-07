"""Design tokens -- the non-colour half of the theme.

Spacing, radius, and type scale live here so that "make the cards tighter" is one edit rather than
forty. They are palette-independent: dark and light differ in colour, not in rhythm.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class Tokens:
    """Layout and typography constants, in CSS units."""

    # DENSITY IS A DESIGN DECISION, NOT A DEFAULT.
    #
    # These were roughly 40% larger, which gave a comfortable reading layout -- appropriate for a
    # document, wrong for an assessment console. A security tool is read the way Burp Suite or a
    # SIEM is read: many rows at once, scanned rather than perused, with the eye moving between
    # panels. Generous spacing pushes the third panel below the fold, and a tool where you have to
    # scroll to see whether anything failed is a tool that gets checked less often.
    #
    # Everything below is one step tighter, and the radii are smaller because large rounded corners
    # read as consumer software.
    space_xs: str = "3px"
    space_sm: str = "6px"
    space_md: str = "10px"
    space_lg: str = "16px"
    space_xl: str = "24px"

    radius_sm: str = "4px"
    radius_md: str = "6px"
    radius_lg: str = "8px"

    #: A monospace stack is not a stylistic choice here: payloads, canaries, and response excerpts
    #: are the primary evidence, and proportional fonts make whitespace differences invisible.
    #:
    #: Both stacks lead with fonts that may not be installed and then fall back through faces that
    #: ARE present on Windows, macOS, and mainstream Linux. The project runs fully offline, so a
    #: webfont is not an option and an unresolvable first choice silently drops to the browser
    #: default -- Times New Roman for serif-less stacks, which is what made the console look
    #: unfinished. `ui-monospace`/`system-ui` resolve to the platform's own UI face, so there is
    #: always a good answer before the generic keyword is reached.
    font_mono: str = (
        "'JetBrains Mono', 'Cascadia Mono', 'SF Mono', ui-monospace, "
        "'DejaVu Sans Mono', 'Liberation Mono', Consolas, 'Courier New', monospace"
    )
    font_sans: str = (
        "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, "
        "'Helvetica Neue', 'Noto Sans', 'Liberation Sans', Arial, sans-serif"
    )

    # A compressed type scale, for the same reason as the spacing above. The old `text_hero` at
    # 2.6rem is a marketing headline; a console's page title should not be four times the size of
    # the data it introduces. Body text stays legible -- density must not become squinting -- but
    # the *range* is narrower, so nothing shouts.
    text_xs: str = "0.70rem"
    text_sm: str = "0.79rem"
    text_md: str = "0.88rem"
    text_lg: str = "1.02rem"
    text_xl: str = "1.30rem"
    text_hero: str = "1.75rem"

    #: Letter-spacing for the small uppercase labels that carry most of the product's character.
    label_tracking: str = "0.08em"


TOKENS: Final = Tokens()
