"""JSON renderer -- the machine-readable format, and the one every other consumer falls back to.

Deliberately the thinnest renderer in the engine: the report model already knows how to serialize
itself, so this adds indentation and nothing else. Any transformation here would be a difference
between what the model says and what a consumer receives.
"""

from __future__ import annotations

import json

from ragstrike.reporters.base.renderer import BaseRenderer
from ragstrike.reporters.models.report import ReportModel


class JsonRenderer(BaseRenderer):
    """Renders the complete report model as JSON."""

    name = "json"
    extension = "json"
    media_type = "application/json"

    def __init__(self, *, indent: int = 2, sort_keys: bool = False) -> None:
        self.indent = indent
        #: Off by default. Report sections are ordered as a human reads them -- cover, summary,
        #: risk -- and sorting keys alphabetically would scramble that for no benefit to a machine
        #: consumer, which does not care about order at all.
        self.sort_keys = sort_keys

    def render(self, report: ReportModel) -> str:
        return json.dumps(
            report.to_dict(),
            indent=self.indent,
            sort_keys=self.sort_keys,
            default=str,
            ensure_ascii=False,
        )


__all__ = ["JsonRenderer"]
