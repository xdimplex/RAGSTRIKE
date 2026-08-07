"""CLI exit codes.

Distinct codes so a pipeline can tell *"the target is insecure"* from *"the scanner is
misconfigured"*. Those demand opposite responses -- one is a finding to triage, the other is a build
to fix -- and collapsing both into ``1`` makes the difference invisible to automation.
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    #: Findings exceeded the ``--fail-on`` threshold. The scanner worked; the target did not.
    FINDINGS = 1
    #: Bad configuration, unknown target, unknown adapter. Fix the setup, not the target.
    CONFIGURATION = 2
    #: The target could not be reached at all.
    UNREACHABLE = 3
    #: The scan itself errored.
    SCAN_ERROR = 4
    #: No authorization record. Deliberately its own code (ADR-017).
    UNAUTHORIZED = 5
