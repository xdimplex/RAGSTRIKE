<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0d1b2a,50:1f3a5f,100:415a77&height=190&section=header&text=RAGStrike&fontSize=76&fontColor=ffffff&fontAlign=50&fontAlignY=36&desc=AI%20Security%20Evaluation%20Framework%20for%20RAG%20Applications&descSize=17&descAlign=50&descAlignY=60&animation=fadeIn&fontFamily=Verdana" alt="RAGStrike" width="100%" />

<br>

<img src="https://readme-typing-svg.demolab.com?font=IBM+Plex+Mono&weight=500&size=19&duration=3000&pause=1000&color=1F3A5F&center=true&vCenter=true&width=820&height=42&lines=A+security+scanner+for+RAG+applications;plant+a+canary+%E2%80%94+send+a+payload+%E2%80%94+watch+the+marker;deterministic+detection%2C+not+guesswork;nine+attack+packs%2C+mapped+to+OWASP+LLM+Top+10;runs+entirely+offline+on+one+machine" alt="" />

<br><br>

<img src="https://img.shields.io/badge/Python-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
<img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit" />
<img src="https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white" alt="Ollama" />
<img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />

<img src="https://img.shields.io/badge/tests-1,893_passing-2EA043?style=flat-square&logo=pytest&logoColor=white" alt="tests" />
<img src="https://img.shields.io/badge/attack_packs-9-1F3A5F?style=flat-square" alt="packs" />
<img src="https://img.shields.io/badge/payloads-65-1F3A5F?style=flat-square" alt="payloads" />
<img src="https://img.shields.io/badge/OWASP-LLM01_·_LLM06_·_LLM07-E63946?style=flat-square&logo=owasp&logoColor=white" alt="OWASP" />
<img src="https://img.shields.io/badge/runs-100%25_offline-6A4C93?style=flat-square" alt="offline" />
<img src="https://img.shields.io/badge/license-Apache_2.0-0d1b2a?style=flat-square" alt="licence" />

</div>

---

## What RAGStrike is

A security scanner built specifically for **Retrieval Augmented Generation** applications.

Conventional application scanners look for SQL injection and cross-site scripting. They do not upload
a poisoned document, ask a question, and check whether the answer contains a credential that should
never have left the system. RAGStrike does exactly that — it drives a RAG application through its own
interfaces, sends attack payloads through the paths a real user would use, and reports what came back
with evidence attached.

It answers one question: **what does this application disclose when someone attacks it?**

---

## What makes it different

| | |
|:---|:---|
| **Tests the whole application, not the model** | The upload path, the vector store, retrieval, and the controls sitting between retrieval and the prompt. Model-level scanners never reach those. |
| **Deterministic detection** | Findings are proved by canary tokens arriving where they should not, never by reading an answer and judging it. The same scan gives the same verdict every time. |
| **Coverage beside every grade** | If four of nine packs did not run, the report says so. A grade of A on half a test is not a grade of A on a full one. |
| **Plugins, not a monolith** | The engine knows nothing about any specific attack. Adding one means adding a folder. |
| **Provider independent** | Attack code talks to an adapter, never to a model. Supporting a new framework is one adapter, not a rewrite. |
| **Fully offline** | No GPU, no cloud, no API key. Test corpora containing credentials never leave the machine. |

---

## How detection works

Most tools read the model's answer and estimate whether something leaked. RAGStrike does not
estimate.

```text
   ┌──────────────────────┐
   │  1  PLANT            │   Unique canary tokens are placed inside the corpus
   │     canary tokens    │   and inside the application's system prompt.
   └──────────┬───────────┘
              │
   ┌──────────▼───────────┐
   │  2  ATTACK           │   Payloads are sent through the real application —
   │     via real paths   │   its chat endpoint, its document upload.
   └──────────┬───────────┘
              │
   ┌──────────▼───────────┐
   │  3  OBSERVE          │   Every request and response is stored as evidence.
   │     and record       │
   └──────────┬───────────┘
              │
   ┌──────────▼───────────┐
   │  4  DECIDE           │   Does the exact marker appear in the answer?
   │     by marker        │
   └──────────┬───────────┘
              │
       ┌──────┴──────┐
       │             │
    [ FAIL ]      [ PASS ]
   marker found   marker absent
   proven leak    target resisted
```

There is no judgement anywhere in that chain, which is what makes a scan reproducible — fixed seed,
temperature zero, same verdict on every run.

Full detail: **[`CONCEPTS.md`](CONCEPTS.md)**

---

## Architecture

```text
                          ┌───────────────────────────────┐
                          │   Operator  (browser or CLI)  │
                          └───────────────┬───────────────┘
                                          │
              ┌───────────────────────────▼───────────────────────────┐
              │                    R A G S T R I K E                  │
              │                                                       │
              │   CLI  ·  FastAPI  (8000)  ·  Streamlit console (8501) │
              ├───────────────────────────────────────────────────────┤
              │   Registry     loads and validates attack packs        │
              │   Scheduler    runs payloads, records evidence         │
              │   Analyzer     decides PASS / FAIL by fixed rules      │
              │   Scoring      risk score, letter grade, coverage      │
              │   Reporters    HTML · JSON · Markdown · PDF            │
              └───────┬───────────────────────────────────┬───────────┘
                      │                                   │
        ┌─────────────▼─────────────┐         ┌───────────▼───────────┐
        │      TARGET ADAPTERS      │         │        STORAGE        │
        │  FastAPI · Ollama · …     │         │  SQLite  ·  reports/  │
        └─────────────┬─────────────┘         └───────────────────────┘
                      │
        ┌─────────────▼──────────────────────────────────────────────┐
        │  Any RAG application under test                            │
        │  (two reference laboratories ship with this project)       │
        └────────────────────────────────────────────────────────────┘
```

The attack code never learns what it is attacking. It hands a payload to an adapter and receives a
response — so the same pack tests a local FastAPI service, a hosted endpoint, or another framework
without a single change.

---

## The attack packs

Nine packs ship with the scanner. Payload counts are for the `standard` profile.

| Pack | What it tests | Payloads | OWASP |
|:---|:---|:---:|:---:|
| `prompt-injection` | User input overriding application instructions | 17 | `LLM01` |
| `prompt-leakage` | Whether the system prompt can be extracted | 18 | `LLM07` |
| `context-poisoning` | Instructions hidden inside uploaded documents | 8 | `LLM01` |
| `indirect-prompt-injection` | Injection arriving through retrieved text | — | `LLM01` |
| `instruction-priority` | Which instruction wins when two conflict | 4 | `LLM01` |
| `prompt-boundary` | Whether the prompt fence can be broken | 4 | `LLM01` |
| `context-separation` | Data kept apart from instructions | 4 | `LLM01` |
| `retrieval-consistency` | Whether retrieval is stable across runs | 6 | — |
| `source-attribution` | Whether cited sources were really retrieved | 3 | `LLM06` |

Each pack is a folder containing an attack class, its payloads as YAML, and a manifest declaring the
permissions it needs. A pack requesting more than it needs is refused at load time — and the refusal
appears in the report as a coverage gap rather than being hidden.

---

## Scan profiles

| Profile | Packs | Time | Use it for |
|:---|:---|:---|:---|
| `smoke` | 2 | ~2 min | Confirming the harness reaches the target |
| `quick` | all | ~6 min | A fast look |
| `standard` | all 9 · 65 payloads | ~20 min | **The real run** |
| `deep` | all · every payload tier | hours | Overnight |

---

## Reporting

Every scan produces a report in four formats from one finding set, so they cannot disagree:

- **HTML** — for reading, with evidence per finding
- **JSON** — for other tools and CI gates
- **Markdown** — for pasting into a ticket
- **PDF** — for handing over

Each report carries the risk score, the letter grade, the **coverage that grade is based on**, and
the analyzer and scoring-model versions it was produced under. Findings map to OWASP LLM categories,
so the output fits a review process that already exists.

---

## Quick start

```bash
# 1 - prerequisites
ollama serve &
ollama pull qwen2.5:3b && ollama pull nomic-embed-text

# 2 - install (virtualenvs are not shipped)
cd RAGStrike && python3 -m venv .venv && .venv/bin/pip install -e ".[dashboard,pdf]"

# 3 - confirm the scanner sees its targets and packs
.venv/bin/ragstrike targets --verify
.venv/bin/ragstrike plugins list

# 4 - run a scan
.venv/bin/ragstrike scan --target vulnerable-rag --profile standard
```

Console at <http://127.0.0.1:8501> · API at <http://127.0.0.1:8000/api/v1/docs>

Full installation: **[`GUIDE/01-INSTALLATION.md`](GUIDE/01-INSTALLATION.md)** ·
Daily startup: **[`GUIDE/02-START-EVERY-TIME.md`](GUIDE/02-START-EVERY-TIME.md)**

---

## Reference laboratories

Two small RAG applications ship alongside the scanner so it can be verified against known behaviour,
and so the value of a security control can be measured rather than asserted. They are test fixtures
for the scanner — not the subject of this project.

- **VulnerableRAG** — a working RAG application with every defensive control deliberately removed
- **SecureRAG** — the same application with seven policy controls active

Because they differ only in their controls, running the same scan against both isolates exactly what
the controls are worth. See [`GUIDE/03-PROJECT-OVERVIEW.md`](GUIDE/03-PROJECT-OVERVIEW.md).

---

## Safety

> **VulnerableRAG is deliberately insecure. It exists to be attacked.**

- Both laboratories refuse to start without `RAGSTRIKE_LAB_ACK=1`
- Everything binds to `127.0.0.1` — never `0.0.0.0`
- Every credential in the test corpus is **synthetic** and authenticates against nothing
- Targets carry an authorisation record; a target cannot be created and attacked in one action

**Never deploy VulnerableRAG anywhere reachable.**

---

## Documentation

| Document | Contents |
|:---|:---|
| [`CONCEPTS.md`](CONCEPTS.md) | How the tool works — detection, canaries, scoring, coverage, plugins |
| [`GUIDE/00-WALKTHROUGH.md`](GUIDE/00-WALKTHROUGH.md) | Setup to demonstration, one page |
| [`GUIDE/01-INSTALLATION.md`](GUIDE/01-INSTALLATION.md) | First-time installation |
| [`GUIDE/02-START-EVERY-TIME.md`](GUIDE/02-START-EVERY-TIME.md) | Daily startup |
| [`GUIDE/05-TROUBLESHOOTING.md`](GUIDE/05-TROUBLESHOOTING.md) | When something breaks |
| [`RAGStrike/ARCHITECTURE.md`](RAGStrike/ARCHITECTURE.md) | Design decisions and their rationale |
| [`RAGStrike/docs/plugin-development.md`](RAGStrike/docs/plugin-development.md) | Writing an attack pack |

---

## Built on published research

| Source | Contribution |
|:---|:---|
| [Greshake et al. (2023)](https://arxiv.org/abs/2302.12173) | Indirect prompt injection through retrieved content |
| [PromptInject](https://arxiv.org/abs/2211.09527) | Goal hijacking and prompt-leaking techniques |
| [garak](https://github.com/NVIDIA/garak) | Probe families: promptinject, leakreplay |
| [Lakera Gandalf](https://gandalf.lakera.ai) | Encoding and spell-it-out evasions |
| [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/) | Finding classification |

*Pack code is original to this project. Every payload names its source in a `provenance` field.*

---

<div align="center">

*You cannot fix what you have not measured.*

<sub>Apache 2.0 · All test data is synthetic · For authorised security testing and education only</sub>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:415a77,50:1f3a5f,100:0d1b2a&height=110&section=footer" alt="" width="100%" />

</div>
