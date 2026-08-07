"""Return the lab to a known clean state.

    python scripts/reset_lab.py                 # everything
    python scripts/reset_lab.py --keep-uploads  # keep the files, drop the index and the database

**Reset between exercises.** Poisoning attacks write persistent state by design, and a corpus
carried over from a previous session produces results that look like findings but are really
leftovers.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from rag.config import load_settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="vulnerable")
    parser.add_argument("--keep-uploads", action="store_true", help="Leave uploaded files on disk.")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    log = logging.getLogger("reset")

    settings = load_settings(args.profile)
    targets: list[Path] = [settings.storage.chroma_dir, settings.storage.database_path]
    if not args.keep_uploads:
        targets.append(settings.storage.upload_dir)

    print(f"About to remove, for profile {args.profile!r}:")
    for target in targets:
        print(f"  - {target}")

    # This deletes ingested state. Requiring a confirmation is the difference between a reset and
    # an accident.
    if not args.yes and input("Proceed? [y/N] ").strip().lower() not in {"y", "yes"}:
        print("Cancelled.")
        return 1

    for target in targets:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            target.mkdir(parents=True, exist_ok=True)
            (target / ".gitkeep").touch()
            log.info("cleared %s", target)
        elif target.exists():
            target.unlink()
            log.info("removed %s", target)
        else:
            log.info("nothing to remove at %s", target)

    log.info("lab reset. Re-seed with: python scripts/seed_corpus.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
