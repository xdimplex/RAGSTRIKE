#!/usr/bin/env bash
#
# The indirect-channel differential: the exercise the context-poisoning pack was written for.
#
# WHY THIS SCRIPT EXISTS
#     `context-poisoning` is READ-ONLY by design -- it refuses to be the thing that poisons the
#     corpus it then reports on. Its `poisoned-corpus` dataset therefore declares a precondition:
#     the operator must have ingested `corpus/poisoned/` first. Run against a clean lab the dataset
#     measures nothing, and the pack now says so (INCONCLUSIVE / coverage gap) rather than
#     reporting a misleading PASS.
#
#     Performing that ingest by hand, on both labs, in the right order, is fiddly and easy to get
#     half-right -- and a half-right corpus produces a comparison that means nothing. So it is a
#     script.
#
# WHY BOTH LABS, ALWAYS
#     The differential is only meaningful while the two corpora are IDENTICAL. Poisoning one and
#     not the other would produce a difference that looks like a security control and is really a
#     difference in what was ingested. That is the single most dangerous mistake available here, so
#     the script never poisons one lab alone.
#
# WHAT IT DOES NOT DO
#     It does not reset afterwards. Leaving the poisoned corpus in place is deliberate: it is what
#     lets you re-run, inspect retrieval in the chat UI, and show the effect live. Clean up when you
#     are done with:
#
#         ./scripts/poisoned_corpus_exercise.sh --reset
#
set -euo pipefail

# Derived from this script's own location, not hardcoded.
#
# These were absolute paths under `/home/iacsd/project/`, and the whole tree was later moved one
# level down into `project/RAGSTRIKE/`. The script then pointed at three directories that no longer
# existed -- and its first act is to ingest poisoned documents, so a stale path here does not fail
# loudly, it half-completes: one lab poisoned, the other not, and a differential that looks like a
# security control and is really a difference in what got loaded.
#
# `STRIKE` is two levels up from `scripts/`; the labs are siblings of the repository.
STRIKE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABS="$(dirname "$STRIKE")"
VULN="$LABS/VulnerableRAG"
SEC="$LABS/SecureRAG"

for _dir in "$VULN" "$SEC"; do
    [[ -d "$_dir" ]] || { echo "not a directory: $_dir" >&2; exit 1; }
done

banner() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }

if [[ "${1:-}" == "--reset" ]]; then
    banner "Resetting both labs to the clean benign corpus"
    for lab in "$VULN:vulnerable" "$SEC:secure"; do
        dir="${lab%%:*}"
        ( cd "$dir" && .venv/bin/python scripts/reset_lab.py --yes \
                    && .venv/bin/python scripts/seed_corpus.py )
    done
    banner "Both labs back to the benign baseline"
    exit 0
fi

# --------------------------------------------------------------------------------------------------
# 1. Ingest the poisoned documents into BOTH labs
# --------------------------------------------------------------------------------------------------
banner "Ingesting corpus/poisoned/ into BOTH labs"
for dir in "$VULN" "$SEC"; do
    echo "  -> $(basename "$dir")"
    ( cd "$dir" && .venv/bin/python scripts/seed_corpus.py --include-poisoned )
done

# --------------------------------------------------------------------------------------------------
# 2. Confirm the corpora actually match
#
# Checked rather than assumed: an ingest that silently failed on one lab would produce a comparison
# that reads as a security result and is really a difference in what got loaded.
# --------------------------------------------------------------------------------------------------
banner "Verifying both corpora are identical"
python3 - <<'PY'
import json, sys, urllib.request

def docs(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/documents", timeout=20) as r:
        return sorted(d["filename"] for d in json.load(r)["documents"])

vuln, sec = docs(9000), docs(9001)
print(f"  VulnerableRAG ({len(vuln)}): {vuln}")
print(f"  SecureRAG     ({len(sec)}): {sec}")
if vuln != sec:
    sys.exit("  CORPORA DIFFER -- the comparison would be meaningless. Fix before scanning.")
if not any("hidden_instruction" in d for d in vuln):
    sys.exit("  poisoned documents are NOT present -- the exercise would measure nothing.")
print("  identical, and poisoned documents are present")
PY

# --------------------------------------------------------------------------------------------------
# 3. Run the pack against each lab, sequentially
#
# Sequential, not parallel: both labs share one Ollama, so concurrent scans contend for it and
# produce latencies that cannot be compared.
# --------------------------------------------------------------------------------------------------
cd "$STRIKE"
for target in vulnerable-rag secure-rag; do
    banner "context-poisoning vs $target"
    .venv/bin/ragstrike scan --target "$target" --profile standard 2>&1 \
        | sed 's/\x1b\[[0-9;]*m//g' \
        | grep -E "context-poisoning|scan finished" || true
done

banner "Done"
cat <<'EOF'
  Read the two context-poisoning lines above.

    VulnerableRAG FAIL, SecureRAG PASS  -> the control worked. This is the demo.
    both FAIL                           -> the control did not hold. Report it; it is a real result.
    both PASS                           -> the poison was not retrieved by either. Check the
                                           coverage-gap note in the detail before claiming anything.

  Reset when finished:  ./scripts/poisoned_corpus_exercise.sh --reset
EOF
