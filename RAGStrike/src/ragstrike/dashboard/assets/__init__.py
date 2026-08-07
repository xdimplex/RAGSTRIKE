"""Static assets.

WHY THE LOGO IS A PYTHON CONSTANT AND NOT A FILE
    A ``.svg`` on disk has to be found at runtime, which means either a filesystem read from a UI
    layer that is documented as never touching the filesystem, or ``package-data`` wiring that
    breaks silently in a wheel. Inline SVG is a string, renders identically, needs no packaging
    metadata, and cannot go missing in an installed environment.

WHY IT IS DRAWN RATHER THAN LINKED
    A remote image would make the dashboard phone out on load. The same reasoning as the reporting
    engine's refusal to fetch a remote logo: whatever it was intended to be, it is a tracking pixel.
"""

from ragstrike.dashboard.assets.branding import LOGO_SVG, PRODUCT_NAME, TAGLINE, wordmark

__all__ = ["LOGO_SVG", "PRODUCT_NAME", "TAGLINE", "wordmark"]
