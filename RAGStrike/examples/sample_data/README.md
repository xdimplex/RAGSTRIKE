# Sample data

## The corpus lives in the lab, not here

Six synthetic PDFs ship with **VulnerableRAG** at `corpus/`, and SecureRAG ingests an identical set.
They are not duplicated into this repository, because **two copies of a test corpus is two corpora**,
and a differential scan whose two targets read different documents proves nothing.

```
corpus/
├── manifest.yaml                     provenance for every document
├── benign/
│   ├── company_handbook.pdf          synthetic HR policies
│   ├── policy_document.pdf           synthetic security policy
│   └── product_faq.pdf               synthetic product answers
└── poisoned/
    ├── hidden_instruction.pdf        white-on-white injected instruction
    ├── fake_authority_memo.pdf       forged internal authority
    └── metadata_injection.pdf        payload in document metadata
```

**Everything is synthetic.** No real person, company, credential, or document is represented. Names
are invented, and the secrets are high-entropy canaries that mean nothing outside the lab.

**The poisoned documents are not ingested by default.** Auto-loading them would poison every session
before it started, and a learner would never see the clean baseline the attack is supposed to be
measured against. Ingest them deliberately, for a specific exercise.

## The manifest is test infrastructure

`corpus/manifest.yaml` declares every document with its hash. It is not documentation.

The retrieval-integrity pack asserts that every retrieved chunk traces back to a declared document —
**a chunk with no manifest entry is an injected chunk**, and that is a finding. The
citation-verification pack uses the same list: a citation naming a source absent from the manifest is
fabricated, decidable as a set operation rather than a judgement call.

## Expected outputs

[`expected_outputs.md`](expected_outputs.md) records what each pack should conclude on each target. It is
the answer key for a demonstration, and the thing to check first when a run surprises you.

## Example reports

[`../example_reports/`](../example_reports/) holds real generated output in all three formats.

## Adding your own documents

Anything you add must be safe to commit, safe to print in a report, and safe to publish. In practice
that means synthetic. If a document would embarrass someone were it quoted verbatim in a finding, it
does not belong in a corpus that exists to be quoted verbatim in findings.

Declare it in the manifest with its hash, or the integrity packs will correctly report it as
injected.
