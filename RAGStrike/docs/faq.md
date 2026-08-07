# FAQ

### Is a clean scan proof my RAG application is secure?

No, and the framework is built to make that clear rather than to let you infer otherwise. A clean
scan means the shipped packs did not find the weaknesses they test for. Coverage is reported beside
every grade so the two claims stay distinguishable.

### Why does a plugin return INCONCLUSIVE instead of PASS?

Because it could not tell. A target that ignored the payload entirely, an empty response, or a
leakage detector with no reference prompt to calibrate against all produce INCONCLUSIVE. Reporting
PASS there would mean claiming a defence exists on evidence that only shows nothing happened.

### Why not use an LLM to judge whether an attack succeeded?

Scores drive remediation budgets and sometimes go-live decisions, so they have to be reproducible. A
model judge changes its mind between runs and between versions, which would make the same unchanged
target score differently after an upgrade. Detection here is canary-based and deterministic, and
every score is arithmetic a reader can redo by hand from the report.

### Can I scan a production system?

Only if you are authorized to, and the framework makes that a deliberate act. Targets are loopback-
only by default; a remote host needs both `allow_remote_targets: true` and an `allowed_hosts` entry.
Every target carries an authorization record, no scan starts without one, and the record appears in
the report.

### Why are VulnerableRAG and SecureRAG separate repositories?

They were built that way on an explicit decision. ADR-009 argued for one repository with two profiles
because separate trees drift — and once they drift the comparison stops measuring security while
continuing to look correct. The mitigation is `SecureRAG/tests/parity`, which asserts both expose the
same endpoints and schemas, plus a compatibility guide listing every file that is supposed to differ.

### Why does the dashboard say the backend is offline?

Because it is. The `/api/v1` server is not implemented. The dashboard is a complete client written
against the published contract, and it shows an honest offline state rather than inventing data. Use
`RAGSTRIKE_DASHBOARD__TRANSPORT=demo` to explore the interface.

### Why does the dashboard shout about demo mode?

Sample findings in a security tool are indistinguishable from real ones in a screenshot. The banner
is derived from the transport rather than from a setting, so no configuration removes the label while
the data stays sample data.

### How do I add an attack pack?

Write a `pack.yaml` and a class implementing the nine-method lifecycle, drop the directory into
`plugins/`, and run `ragstrike plugins validate <slug>`. There is no registration step anywhere in
the engine — that property is enforced by a test asserting no plugin name appears in engine code.

See [`plugin-development.md`](plugin-development.md) and [`sdk-guide.md`](sdk-guide.md).

### Why is PDF export listed but unavailable?

It is a declared placeholder that refuses rather than emitting an empty file or HTML with a `.pdf`
extension — either would look like success and fail when someone opened the report. `render_all` and
`export_all` skip it, and `formats()` reports `pdf: false`.

### Why is my scan so slow?

Target model inference, not the framework. `python -m validation.runner` separates framework time
from target time so you can see the split.

### Can I run this in CI?

The test suite and `python -m validation.runner --checks-only`, yes. A full scan needs a running
target and a model, so it is a separate job with its own infrastructure. Exit codes distinguish
"insecure" from "misconfigured" specifically so a pipeline can act on the difference.

### Is scoring comparable across versions?

Not automatically, on purpose. Weights are published under a `scoring_model_version`, and trend views
refuse cross-version comparison without an explicit recompute. A target that has not changed must not
change grade because the scanner was upgraded.
