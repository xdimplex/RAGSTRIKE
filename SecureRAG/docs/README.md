> ⚠️ **SecureRAG is a lab application — hardened, not audited.** Loopback only.
> See [`LAB_SAFETY.md`](LAB_SAFETY.md).

# `docs` — Documentation

The hardened half of the pair is a teaching artifact as much as a test target, so the documentation
is a first-class deliverable.

| Document | What it covers |
|---|---|
| [`LAB_SAFETY.md`](LAB_SAFETY.md) | Containment rules. **Read this first** |
| [`architecture-comparison.md`](architecture-comparison.md) | The two applications side by side, and the one line that differs |
| [`security-features.md`](security-features.md) | Every control, why it is shaped that way, and **what it does not do** |
| [`configuration-guide.md`](configuration-guide.md) | `security.yaml`, and why no setting can empty the chain |
| [`deployment-guide.md`](deployment-guide.md) | Running it, and running the pair |
| [`compatibility-guide.md`](compatibility-guide.md) | Every divergence from VulnerableRAG, and the drift gate |
| [`migration-guide.md`](migration-guide.md) | Porting these controls into a real application |
| [`developer-guide.md`](developer-guide.md) | Layout, tests, adding a control, conventions |
| [`folder-responsibilities.md`](folder-responsibilities.md) | Per-directory ownership and the rules that hold everywhere |
| [`vulnerabilities.md`](vulnerabilities.md) | The V1–V9 catalogue, inherited — describing what is **countered** here |

## Reading order

**Understanding the pair:** `architecture-comparison.md` → `security-features.md` → the diff of the
two `prompt_builder.py` files.

**Running it:** `LAB_SAFETY.md` → `deployment-guide.md`.

**Extending it:** `developer-guide.md` → `folder-responsibilities.md` → `compatibility-guide.md`.

**Taking it somewhere real:** `migration-guide.md`, then the "what it does not do" section of
`security-features.md`.
