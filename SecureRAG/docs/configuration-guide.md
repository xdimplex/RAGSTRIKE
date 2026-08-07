# Configuration guide

---

## Precedence

```
configs/config.yaml  →  profiles/secure/config.yaml  →  configs/security.yaml  →  SRAG_* env
```

`VRAG_*` is still honoured so a lab script written for either application works against both;
`SRAG_*` wins where both are set. Validation happens once, at startup, and fails fast with the exact
field path.

---

## The rule that shapes this file

**Configuration can tune a control. It cannot remove one.**

Every control in `rag/policy/controls/` is composed unconditionally by `build_controls()`, in code.
The settings in `configs/security.yaml` adjust thresholds and toggle individual *checks within* a
control — they never take one out of the chain.

Setting `sanitizer.neutralize_instructions: false` leaves the sanitizer composed, still normalizing
Unicode, and still reported by `GET /health`. **There is no value you can put in any configuration
file that makes SecureRAG report zero active policies.**

This is the same reasoning ADR-009 applies to the profile split: a security posture that a YAML edit
can silently erase is a posture nobody can rely on. `test_no_setting_can_empty_the_chain` turns every
boolean in the schema off at once and asserts the chain is still seven controls long.

A missing `security.yaml` yields the **defaults, which are the secure values** — so an absent file
produces a fully hardened application, not a disabled one. Failing closed is the only safe direction.

---

## `configs/security.yaml`

### `sanitizer` — runs at ingestion

| Key | Default | Turning it off means |
|---|---|---|
| `normalize_unicode` | `true` | A document can use fullwidth or mathematical-alphanumeric characters to render an instruction in a form no pattern matches |
| `strip_invisible_characters` | `true` | Zero-width and bidi-control characters survive — the reader and the model see different text |
| `neutralize_instructions` | `true` | Instruction framing reaches the prompt with its imperative intact |

### `validation` — runs on every question

| Key | Default | Notes |
|---|---|---|
| `max_question_chars` | `2000` | Raising it widens the window for pushing the system prompt out of effective attention |
| `min_question_chars` | `1` | Must not exceed the maximum — validated |
| `normalize_unicode` | `true` | |
| `reject_control_characters` | `true` | |

### `retrieval` — runs on retrieved chunks

| Key | Default | Notes |
|---|---|---|
| `min_score` | `0.15` | **The single most consequential value here.** `0.0` disables the relevance floor, and a poisoned document that matches nothing in particular is then pulled into every unrelated question |
| `max_chunks` | `5` | Applied after the floor |
| `max_chunk_chars` | `4000` | A larger chunk is a chunking failure or a stuffing attempt |
| `max_instruction_density` | `8.0` | Matches per hundred words. Lower catches more injection and drops more legitimate security documentation |

### `session`

| Key | Default | Notes |
|---|---|---|
| `max_history_turns` | `6` | Unbounded history replays a landed injection on every subsequent question, forever |
| `max_prompt_chars` | `24000` | Trimming takes from the context, never from the instructions |

### `output`

| Key | Default | Notes |
|---|---|---|
| `max_answer_chars` | `8000` | |
| `detect_prompt_echo` | `true` | Turning it off removes the only control that reliably stops prompt disclosure |
| `echo_window` | `48` | Shortest run of prompt text counting as an echo. Lower catches paraphrase, risks coincidence |
| `normalize_whitespace` | `true` | |

### `masking`

| Key | Default | Notes |
|---|---|---|
| `mask_emails` | `true` | PII, separable from credential masking |
| `fingerprint_chars` | `6` | Enough to correlate occurrences; far too little to recover the value |

### `citations`

| Key | Default | Notes |
|---|---|---|
| `annotate_ungrounded` | `true` | Annotating rather than deleting: a fabricated citation is evidence the reader needs |

### `uploads`

| Key | Default | Notes |
|---|---|---|
| `max_upload_mb` | `25` | Capped at 1024 by the schema — a 10 GB limit is a mistake, not a policy |
| `allowed_extensions` | `["pdf"]` | Normalized: `pdf`, `.pdf`, `PDF` are one value. An empty list is refused |
| `allowed_mime_types` | pdf, x-pdf, octet-stream | `octet-stream` is accepted because many clients send it for everything |
| `verify_magic_bytes` | `true` | The only check the client cannot forge. This is what makes accepting `octet-stream` safe |
| `reject_duplicates` | `true` | Returns the existing record instead of ingesting a second copy |

### `http`

| Key | Default |
|---|---|
| `security_headers` | `true` |
| `suppress_server_header` | `true` |

### `planned` — enables nothing

```yaml
planned:
  rate_limiting: false
  authentication: false
  authorization: false
```

Setting one to `true` **enables nothing**, because there is nothing to enable. The controls are
declared and not built (`rag/policy/controls/future_controls.py`). The flag records intent; `GET
/health` reports the gap either way.

---

## Environment overrides

Double underscore separates nesting:

```bash
SRAG_SECURITY__VALIDATION__MAX_QUESTION_CHARS=4000
SRAG_SECURITY__RETRIEVAL__MIN_SCORE=0.25
SRAG_MODEL__NAME=qwen3:8b
SRAG_SERVER__API_PORT=9101
```

Values are parsed as YAML, so `8` is an int and `true` is a boolean.

An environment override **also cannot empty the chain** — tested, because a stale shell export
outlives a config edit and is the easiest surface to change by accident.

---

## Do not expose sensitive configuration

There are no credentials in any file here, and there is nowhere to put one. Ollama runs locally
without authentication; if a future provider needs a key it belongs in the environment, never in a
committed YAML file.
