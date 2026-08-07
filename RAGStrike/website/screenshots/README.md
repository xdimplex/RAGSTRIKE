# Screenshots and demo assets

**Placeholders.** No images are committed — a screenshot of an interface that reports
`BACKEND OFFLINE` would be accurate and useless, and a mocked one would be neither.

Capture these when `/api/v1` lands ([D-03](../../docs/technical-debt.md)).

## Required

| File | Must show |
|---|---|
| `01-scan-running.png` | A scan in progress: pack, payload counter, elapsed time |
| `02-findings-list.png` | Findings with severity, **including at least one `INCONCLUSIVE`** |
| `03-finding-detail.png` | One finding expanded: request, response, **the detector that fired** |
| `04-risk-breakdown.png` | The risk arithmetic, printed |
| `05-coverage.png` | Coverage beside the grade, with a skip and its reason |
| `06-differential.png` | The same pack: FAIL on VulnerableRAG, PASS on SecureRAG |
| `07-report-html.png` | A rendered HTML report |
| `08-cli-scan.png` | A terminal run start to finish |

## Demo GIF

| File | Shows |
|---|---|
| `demo-scan.gif` | Register → authorize → scan → report. **Real timing, or a visible cut marker** |
| `demo-differential.gif` | Same pack, both targets, opposite results |
| `demo-plugin.gif` | Three files → `ragstrike plugins` finds it → it runs |

The third is the most persuasive asset this project has: **zero framework edits**, visible in about
forty seconds.

## Rules

**Real output only.** Never a mock-up dressed as a run.

**Never speed up a scan without saying so.** Scans take 5–40 seconds per payload, and a GIF implying
otherwise is a false claim about performance. Cut, with a marker.

**Screenshot 06 is the important one.** FAIL and PASS side by side is the argument; everything else is
interface.

**Redact nothing, because there is nothing to redact.** The corpus is synthetic and the secrets are
canaries. If a capture needs redacting, something is in the lab that should not be.
