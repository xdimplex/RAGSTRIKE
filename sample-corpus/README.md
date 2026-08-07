# Sample Corpus — Northwind Analytics Ltd

Demonstration documents for showing RAG ingestion end to end: **upload → extract → chunk → embed →
store in ChromaDB → retrieve → answer**.

**Northwind Analytics Ltd is a fictional company.** Every name, figure, credential, and identifier
in these documents is synthetic. Nothing here refers to a real organisation, person, or system.

---

## These are NOT pre-loaded

Neither VulnerableRAG nor SecureRAG ingests this folder. That is deliberate — the point of the
folder is to let you demonstrate the upload path live, through the UI, in front of an audience.

Upload them yourself from **Upload Documents** in either lab UI:

- VulnerableRAG → http://127.0.0.1:8601
- SecureRAG → http://127.0.0.1:8602

If you want the same documents in both labs, upload to both. The differential comparison is only
meaningful while the two corpora match.

---

## What is here

### `pdf/` — five documents, two pages each

| File | Subject | Pages | Est. chunks |
|---|---|---:|---:|
| `vendor_risk_assessment_procedure.pdf` | Supplier tiering, assessment, contractual terms | 2 | ~10 |
| `incident_response_runbook.pdf` | Severity, roles, containment, notification | 2 | ~12 |
| `data_retention_schedule.pdf` | Retention periods by record category | 2 | ~10 |
| `engineering_onboarding_guide.pdf` | Access, environment, shipping, on-call | 2 | ~12 |
| `quarterly_business_review_q4_fy2025.pdf` | Revenue, margin, product, operations | 2 | ~10 |

### `text/` — five documents

| File | Subject | Est. chunks |
|---|---|---:|
| `employee_handbook.txt` | Leave, hours, conduct, disciplinary | ~27 |
| `information_security_policy.txt` | Classification, access, encryption, AI controls | ~26 |
| `customer_support_playbook.txt` | Tiers, severity, escalation, sensitive requests | ~21 |
| `expense_and_procurement_policy.txt` | Authority limits, travel, what is not claimable | ~21 |
| `product_faq.txt` | Platform capability, security posture, known limits | ~17 |

### `csv/`

Reserved. The lab ingestion pipeline currently accepts **PDF only** (`ingestion.supported_types`
in `configs/config.yaml`), so a CSV would be rejected at upload. The folder exists so the structure
is obvious if CSV support is added later.

**Roughly 166 chunks across the corpus at the configured 512/64 chunking.** That is enough for
retrieval to make real choices — a four-line file would return the same chunk every time and
demonstrate nothing.

---

## Suggested demo questions

These are answerable from the corpus and each pulls from a different document, so retrieval is
visibly doing work:

- *"How many days of annual leave do employees get, and how many can be carried over?"*
- *"What has to be in a contract with a Tier 1 supplier?"*
- *"If I find a credential committed to a repository, what should I do?"*
- *"How long are security logs kept, and why that period?"*
- *"What are the platform's known limitations?"*
- *"When can an engineer get production access?"*

Watch the **retrieved chunks** panel alongside each answer — that is what makes the retrieval step
visible rather than something the audience has to take on trust.

### For the security demo

The security-relevant content is deliberately concentrated in
`information_security_policy.txt` (section 9 covers RAG-specific controls) and
`customer_support_playbook.txt` (section 6 covers requests that must always be refused). Ask both
labs the same question about them and compare the answers.

---

## Rebuilding the PDFs

The PDFs are generated, not committed as opaque binaries, so their content is reviewable in a diff:

```bash
cd /home/iacsd/project && RAGStrike/.venv/bin/python sample-corpus/build_pdfs.py
```

Edit the content blocks in `build_pdfs.py` and re-run to change them.
