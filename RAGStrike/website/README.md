# Website assets

Source content for a project site. **Nothing here is deployed**, and this directory contains no build
tooling — the phase brief is explicit that a site is prepared, not published.

| File | Becomes |
|---|---|
| [`index.md`](index.md) | Landing page |
| [`architecture.md`](architecture.md) | Architecture overview |
| [`features.md`](features.md) | Feature overview |
| [`quickstart.md`](quickstart.md) | Quick start |
| [`faq.md`](faq.md) | FAQ |
| [`roadmap.md`](roadmap.md) | Roadmap |
| [`screenshots/`](screenshots/) | Image slots, with a manifest of what each must show |

## If you publish this

MkDocs Material is the intended target (planned in Annex A). Point `docs_dir` here, or symlink.

**One rule.** Every capability claim on the site must be true of the tagged release, and anything not
yet working must be marked. [`../docs/limitations.md`](../docs/limitations.md) is the reference —
a project page that overstates is a project page that gets found out.
