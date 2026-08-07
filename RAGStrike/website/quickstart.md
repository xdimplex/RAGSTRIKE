# Quick start

Ten minutes to a report, assuming Python 3.11+ and about 8 GB of RAM for the local model.

---

## 1. Install

```bash
git clone <repository-url> RAGStrike
cd RAGStrike
python -m venv .venv && .venv\Scripts\activate    # Windows
pip install -e ".[dev]"
ragstrike version
```

## 2. Start a target

```bash
cd ../VulnerableRAG
pip install -e .
RAGSTRIKE_LAB_ACK=1 python -m profiles.vulnerable.main_api      # 9000
```

Ollama must be running with the model pulled. `http://127.0.0.1:9000/health` should answer.

## 3. Check RAGStrike can reach it

```bash
ragstrike targets --verify
```

Expect `OK vulnerable-rag`. Targets are declared in `configs/targets.yaml`, each with an
`authorization:` block — `authorized_by`, `authorization_ref`, `scope`.

**That block is not a formality.** It is a persisted record, and no scan runs without one (ADR-017).
Non-local URLs are rejected outright.

## 4. Scan

```bash
ragstrike plugins disable prompt-leakage
ragstrike plugins disable context-poisoning
ragstrike scan --target vulnerable-rag
```

**Expect 10–20 minutes for one attack pack.** Every payload is a full RAG round trip through a local
model — 5–40 seconds each on CPU. With everything enabled it runs for hours, so scope it by disabling
packs; `ragstrike plugins enable <slug>` puts them back.

## 5. Read the result

Findings are persisted and printed. Reports are generated from Python — there is no `ragstrike report`
command yet ([`limitations.md`](../docs/limitations.md)); the snippet is in
[`../examples/example_reports/README.md`](../examples/example_reports/README.md).

Three things to look at first:

- **The risk arithmetic**, printed rather than asserted — you can check it by hand
- **The detector name on every finding** — request, response, and the rule that fired
- **Coverage, beside the grade.** A grade from partial coverage is a different claim

## 6. The part that makes it mean something

```bash
cd ../SecureRAG && RAGSTRIKE_LAB_ACK=1 python -m profiles.secure.main_api      # 9001
```

```bash
ragstrike scan --target secure-rag
```

**Same pack, hardened target, expect PASS.** If it fails on both, the pack is measuring something
other than the control — and that is worth knowing before you trust any finding it produces.

---

## Without a model

To see the interfaces without waiting on inference:

```bash
RAGSTRIKE_DASHBOARD__TRANSPORT=demo streamlit run src/ragstrike/dashboard/app.py
```

Fixtures, labelled as fixtures. The live dashboard reports `BACKEND OFFLINE` because `/api/v1` is not
implemented — see [`limitations.md`](../docs/limitations.md).

Real generated reports are in [`../examples/example_reports/`](../examples/example_reports/).

## Next

[Write a pack](../examples/custom_plugin/) · [Add a target](../examples/custom_target/) ·
[User guide](../docs/user-guide.md) · [Troubleshooting](../docs/troubleshooting.md)
