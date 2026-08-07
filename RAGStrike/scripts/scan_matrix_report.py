"""Summarise a smoke/quick/standard x vulnerable/secure scan matrix into one table.

WHY A SCRIPT
    Six scans produce six logs, and reading them by hand is where misreadings happen. Two in
    particular, both of which occurred while producing these very results:

    * **FAIL read as a defect.** On VulnerableRAG a FAIL means the scanner WORKED -- it broke into
      an application built to be broken into. A clean sheet there would mean the tool is useless.
    * **A one-payload delta read as a result.** Most evaluation packs carry three to six payloads;
      at that size a single flip is run-to-run variance, not evidence.

    Printing the interpretation alongside the numbers keeps both corrections attached to the data.

USAGE
    python scripts/scan_matrix_report.py <dir-with-m_*.log>
"""

from __future__ import annotations

from pathlib import Path
import re
import sys

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_VERDICT = re.compile(r"\s+(PASS|FAIL|INCONC|ERROR)\s+(\S+)\s+\S+\s+(.*)")
_FINISHED = re.compile(
    r"state=(\w+).*?executed=(\d+) passed=(\d+) failed=(\d+) errored=(\d+) "
    r"skipped=(\d+) coverage=([\d.]+) elapsed_ms=(\d+)"
)
_RATIO = re.compile(r"(\d+)\s*/\s*(\d+)")

PROFILES = ("smoke", "quick", "standard")
TARGETS = ("vulnerable-rag", "secure-rag")

#: Below this many payloads, one differing payload is not evidence. The packs ship 1-18 payloads;
#: at n=4 a single flip is 25% of the sample, well inside run-to-run variance of a sampled model.
#: Same value as ``differential_report.py`` -- if one moves, move both.
SMALL_SAMPLE = 8

#: Fraction of the sample that must change verdict before a *partial* difference is worth claiming.
MEANINGFUL_DELTA = 0.30


def read_pair(a: str, ar: str, b: str, br: str) -> str:
    """What this pair of outcomes supports saying, and nothing beyond it.

    Written as a chain of named cases rather than a table because each branch is a different claim
    about the evidence. Two of them exist specifically to stop misreadings that already happened
    while producing these results by hand:

    * A partial reduction (14/17 -> 8/17) was printed as "control did not hold", which throws away
      a real 35% effect just because both sides still ended in FAIL.
    * FAIL -> INCONCLUSIVE was printed as "no difference", which is the opposite of the truth: the
      confirmed leaks stopped, and what replaced them is *unmeasured*, not *safe*.
    """
    if a == "FAIL" and b == "PASS":
        return "*** CONTROL WORKED ***"
    if a == "PASS" and b == "FAIL":
        return "REGRESSION -- hardened failed where weak held"
    if a == "FAIL" and b == "INCONC":
        return "no confirmed finding, but INCONCLUSIVE -- not the same as PASS"
    if a == "INCONC" or b == "INCONC":
        return "inconclusive -- detector could not tell"
    if a != "FAIL" or b != "FAIL":
        return "no difference"

    # Both FAIL. Whether that is "no change" or a real reduction depends on the sample size.
    fa, ta = _ratio_parts(ar)
    fb, _ = _ratio_parts(br)
    if not ta:
        return "control did not hold"
    delta = fa - fb
    if ta < SMALL_SAMPLE:
        return f"control did not hold (n={ta}: too small to read a partial change)"
    if abs(delta) / ta < MEANINGFUL_DELTA:
        return f"control did not hold ({ar} vs {br}: within noise)"
    direction = "fewer" if delta > 0 else "MORE"
    return f"partial: {abs(delta)} {direction} payloads succeeded ({ar} vs {br})"


def _ratio_parts(ratio: str) -> tuple[int, int]:
    match = _RATIO.search(ratio or "")
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


def parse(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    text = _ANSI.sub("", path.read_text(errors="ignore"))

    verdicts: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        match = _VERDICT.match(line)
        if match:
            outcome, slug, detail = match.groups()
            ratio = _RATIO.search(detail)
            verdicts[slug] = (outcome, ratio.group(0) if ratio else "")

    summary = _FINISHED.search(text)
    if not summary:
        return {"verdicts": verdicts, "state": "INCOMPLETE"}

    state, executed, passed, failed, errored, skipped, coverage, elapsed = summary.groups()
    return {
        "verdicts": verdicts,
        "state": state,
        "executed": int(executed),
        "passed": int(passed),
        "failed": int(failed),
        "errored": int(errored),
        "skipped": int(skipped),
        "coverage": float(coverage),
        "minutes": int(elapsed) / 60000,
    }


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(".")

    print()
    print("  SCAN MATRIX -- identical payloads, identical model, identical corpus")
    print("  On VulnerableRAG a FAIL means the SCANNER WORKED. It is not a defect.")
    print()
    print(f"  {'PROFILE':10} {'TARGET':16} {'STATE':10} {'COV':>5} {'PASS':>5} {'FAIL':>5} "
          f"{'ERR':>4} {'SKIP':>5} {'MINS':>6}")
    print("  " + "-" * 78)

    runs: dict[tuple[str, str], dict[str, object]] = {}
    for profile in PROFILES:
        for target in TARGETS:
            data = parse(root / f"m_{profile}_{target}.log")
            if data is None:
                print(f"  {profile:10} {target:16} {'pending':10}")
                continue
            runs[(profile, target)] = data
            if data["state"] == "INCOMPLETE":
                print(f"  {profile:10} {target:16} {'running':10}")
                continue
            print(
                f"  {profile:10} {target:16} {data['state']:10} "
                f"{data['coverage']:>4.0%} {data['passed']:>5} {data['failed']:>5} "
                f"{data['errored']:>4} {data['skipped']:>5} {data['minutes']:>6.1f}"
            )

    # Per-pack differential, standard profile only -- it is the only one with full coverage.
    vuln = runs.get(("standard", "vulnerable-rag"))
    sec = runs.get(("standard", "secure-rag"))
    if vuln and sec and vuln["state"] != "INCOMPLETE" and sec["state"] != "INCOMPLETE":
        print()
        print("  PER-PACK DIFFERENTIAL (standard, full coverage)")
        print(f"  {'PACK':24} {'VULNERABLE':<16} {'SECURE':<16} READING")
        print("  " + "-" * 84)
        left = vuln["verdicts"]  # type: ignore[index]
        right = sec["verdicts"]  # type: ignore[index]
        wins = 0
        for pack in sorted(set(left) | set(right)):
            a, ar = left.get(pack, ("--", ""))
            b, br = right.get(pack, ("--", ""))
            reading = read_pair(a, ar, b, br)
            if reading.startswith("***"):
                wins += 1
            print(f"  {pack:24} {a + ' ' + ar:<16} {b + ' ' + br:<16} {reading}")
        print()
        print(f"  {wins} pack(s) where the hardened target held and the weak one did not.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
