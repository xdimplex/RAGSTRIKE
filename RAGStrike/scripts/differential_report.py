"""Print the differential between two scans of the same profile, with honest interpretation.

WHY THIS IS A SCRIPT AND NOT A README TABLE
    The comparison is the project's central claim, and it is easy to read badly. Two failure modes
    have already happened while running it by hand:

    * **Reading FAIL as a defect.** On VulnerableRAG a FAIL means the scanner *worked* -- it broke
      into an application built to be broken into. A clean sheet there would mean the tool is
      useless.
    * **Reading a one-payload delta as a result.** Most evaluation packs carry three to six
      payloads. At that size, 3/4 versus 2/4 is noise, not evidence, and calling it an improvement
      (or a regression) claims a precision the sample does not support.

    So the interpretation is computed rather than eyeballed, and the thresholds are stated in code
    where they can be argued with.

USAGE
    python scripts/differential_report.py <vulnerable.log> <secure.log>
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys

#: Below this many payloads, a single differing payload is not evidence of anything. Chosen because
#: the evaluation packs ship 3-6 payloads: one flip is 17-33% of the sample, which is well inside
#: the run-to-run variance of a non-deterministic model.
SMALL_SAMPLE = 8

#: Fraction of payloads that must change verdict before a partial difference is called meaningful.
#: A total flip (FAIL -> PASS) is always reported regardless.
MEANINGFUL_DELTA = 0.30

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_LINE = re.compile(r"\s+(PASS|FAIL|INCONC|ERROR)\s+(\S+)\s+\S+\s+(.*)")
_RATIO = re.compile(r"(\d+)\s*/\s*(\d+)")


@dataclass(frozen=True, slots=True)
class Result:
    outcome: str
    failed: int = 0
    total: int = 0

    @property
    def ratio(self) -> str:
        return f"{self.failed}/{self.total}" if self.total else "--"


def parse(path: Path) -> dict[str, Result]:
    out: dict[str, Result] = {}
    for raw in path.read_text(errors="ignore").splitlines():
        match = _LINE.match(_ANSI.sub("", raw))
        if not match:
            continue
        outcome, slug, detail = match.groups()
        ratio = _RATIO.search(detail)
        failed, total = (int(ratio.group(1)), int(ratio.group(2))) if ratio else (0, 0)
        # A PASS line reports "N/N payloads returned PASS", so the first number is passes.
        out[slug] = Result(outcome, 0 if outcome == "PASS" else failed, total)
    return out


#: argv for `script <vuln.log> <secure.log>`.
_EXPECTED_ARGS = 3


def interpret(before: Result | None, after: Result | None) -> str:
    """What the pair of results supports saying -- and nothing more.

    A chain of guards rather than a lookup: each branch is a distinct claim about the evidence, and
    naming them separately is what stops "FAIL vs FAIL" and "n too small to read" collapsing into
    one vague verdict.
    """
    if before is None or after is None:
        return "incomplete"
    if before.outcome == "FAIL" and after.outcome == "PASS":
        return "CONTROL WORKED -- every payload flipped"
    if before.outcome == "PASS" and after.outcome == "FAIL":
        return "REGRESSION -- hardened target failed where the weak one held"
    # FAIL -> INCONCLUSIVE is emphatically not "no difference": the confirmed findings stopped, and
    # what replaced them is UNMEASURED rather than SAFE. Collapsing the two would let a detector
    # that quietly lost its calibration read as a security improvement.
    if before.outcome == "FAIL" and after.outcome == "INCONC":
        return "no confirmed finding, but INCONCLUSIVE -- not the same as PASS"
    if "INCONC" in (before.outcome, after.outcome):
        return "inconclusive -- the detector could not tell"
    if before.outcome != "FAIL" or after.outcome != "FAIL":
        return "no difference"

    sample = max(before.total, after.total)
    delta = before.failed - after.failed
    if sample < SMALL_SAMPLE:
        return f"n={sample}: too small to read ({before.ratio} vs {after.ratio})"
    if abs(delta) / sample < MEANINGFUL_DELTA:
        return f"within noise ({before.ratio} vs {after.ratio})"
    direction = "fewer" if delta > 0 else "more"
    return f"{abs(delta)} {direction} failures ({before.ratio} vs {after.ratio})"


def main(argv: list[str]) -> int:
    if len(argv) != _EXPECTED_ARGS:
        print(__doc__)
        return 2

    vuln, sec = parse(Path(argv[1])), parse(Path(argv[2]))

    print()
    print("  DIFFERENTIAL -- same payloads, same model, same corpus")
    print("  FAIL on VulnerableRAG means the scanner WORKED. It is not a defect.")
    print()
    print(f"  {'PACK':24} {'VULNERABLE':<14} {'SECURE':<14} INTERPRETATION")
    print("  " + "-" * 92)

    real = 0
    for pack in sorted(set(vuln) | set(sec)):
        before, after = vuln.get(pack), sec.get(pack)
        verdict = interpret(before, after)
        if verdict.startswith(("CONTROL WORKED", "REGRESSION")):
            real += 1
        left = f"{before.outcome} {before.ratio}" if before else "--"
        right = f"{after.outcome} {after.ratio}" if after else "pending"
        print(f"  {pack:24} {left:<14} {right:<14} {verdict}")

    print()
    print(f"  {real} pack(s) produced an interpretable difference.")
    print(
        "  Packs marked 'too small to read' carry 3-6 payloads; one differing payload there is\n"
        "  run-to-run variance, not a security result. More payloads is the fix."
    )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
