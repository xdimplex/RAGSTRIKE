"""Generate the sample PDF corpus.

WHY A GENERATOR AND NOT COMMITTED BINARIES
    A PDF in version control is an opaque blob: it cannot be reviewed in a diff, and nobody can
    tell whether its text changed. Keeping the source here means the corpus is readable, editable,
    and reproducible -- and the PDFs can be rebuilt at any time with:

        python sample-corpus/build_pdfs.py

    Every document is synthetic. "Northwind Analytics Ltd" is a fictional company and no figure,
    name, or identifier below refers to anything real.

WHY EACH DOCUMENT IS AT LEAST A FULL PAGE
    These exist to demonstrate ingestion end to end. At 512-character chunks with 64 characters of
    overlap, a one-page document produces roughly 8-12 chunks -- enough that chunking, embedding,
    and top-k retrieval all do something visible, which a four-line file would not show.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

OUTPUT_DIR = Path(__file__).parent / "pdf"

# --------------------------------------------------------------------------------------------------
# Styles
# --------------------------------------------------------------------------------------------------
_BASE = getSampleStyleSheet()

TITLE = ParagraphStyle(
    "NwTitle", parent=_BASE["Title"], fontSize=17, leading=21, spaceAfter=4
)
SUBTITLE = ParagraphStyle(
    "NwSubtitle", parent=_BASE["Normal"], fontSize=8.5, leading=12,
    textColor="#555555", spaceAfter=14,
)
HEADING = ParagraphStyle(
    "NwHeading", parent=_BASE["Heading2"], fontSize=11.5, leading=14,
    spaceBefore=12, spaceAfter=5,
)
BODY = ParagraphStyle(
    "NwBody", parent=_BASE["BodyText"], fontSize=9.5, leading=13.5,
    alignment=TA_JUSTIFY, spaceAfter=7,
)
BULLET = ParagraphStyle(
    "NwBullet", parent=BODY, leftIndent=12, bulletIndent=3, spaceAfter=3
)


def build(filename: str, title: str, subtitle: str, blocks: list[tuple[str, str]]) -> Path:
    """Render one document.

    *blocks* is a list of ``(kind, text)`` where kind is ``h`` (heading), ``p`` (paragraph),
    ``b`` (bullet), or ``pb`` (page break). Keeping the content as plain data means a document can
    be proof-read without reading any layout code.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename

    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=title, author="Northwind Analytics Ltd", subject=subtitle,
    )

    story: list[object] = [Paragraph(title, TITLE), Paragraph(subtitle, SUBTITLE)]
    for kind, text in blocks:
        if kind == "h":
            story.append(Paragraph(text, HEADING))
        elif kind == "p":
            story.append(Paragraph(text, BODY))
        elif kind == "b":
            story.append(Paragraph(text, BULLET, bulletText="•"))
        elif kind == "pb":
            story.append(PageBreak())
    story.append(Spacer(1, 10))
    story.append(
        Paragraph(
            "All names, figures, and identifiers in this document are synthetic and exist for "
            "demonstration purposes only. Northwind Analytics Ltd is a fictional entity.",
            SUBTITLE,
        )
    )

    doc.build(story)
    return path


# --------------------------------------------------------------------------------------------------
# The documents
# --------------------------------------------------------------------------------------------------

VENDOR_RISK = [
    ("h", "1. Purpose"),
    ("p", "This procedure describes how Northwind Analytics Ltd assesses and monitors the security "
          "risk presented by third-party suppliers. It applies to any supplier that stores, "
          "processes, or transmits Company or client information, or that is granted access to a "
          "Company network or system. It applies equally to paid and free services, and to trials."),
    ("p", "The procedure exists because supplier compromise is now a more common route into an "
          "organisation than direct attack. A supplier with weak controls extends its weakness to "
          "every customer it serves, and a contract does not mitigate a technical failure."),
    ("h", "2. Risk tiering"),
    ("p", "Every supplier is placed in one of three tiers at onboarding. The tier determines the "
          "depth of assessment and the frequency of review. Tier is assigned by the Information "
          "Security team, not by the business sponsor, because a sponsor has an obvious interest in "
          "the answer being 'low'."),
    ("b", "<b>Tier 1 — Critical.</b> Processes Confidential or Restricted information, or has "
          "privileged access to production. Full assessment, annual reassessment, right to audit, "
          "and a named security contact required."),
    ("b", "<b>Tier 2 — Significant.</b> Processes Internal information, or has non-privileged "
          "system access. Questionnaire-based assessment and biennial reassessment."),
    ("b", "<b>Tier 3 — Limited.</b> No access to Company data or systems. Registration only, with "
          "annual confirmation that the scope has not changed."),
    ("h", "3. Assessment content"),
    ("p", "A Tier 1 assessment covers governance, access control, encryption, secure development, "
          "vulnerability management, logging and monitoring, incident response, business continuity, "
          "sub-processor management, and personnel screening."),
    ("p", "Independent assurance is preferred over self-attestation. A current ISO 27001 certificate "
          "with a scope statement covering the relevant service, or a SOC 2 Type II report with no "
          "material exceptions, satisfies most control areas. A completed questionnaire with no "
          "supporting evidence satisfies none of them."),
    ("p", "Where a supplier declines to provide evidence on confidentiality grounds, a review under "
          "NDA at the supplier's premises is offered. A supplier that declines both is not "
          "onboarded at Tier 1, regardless of commercial pressure."),
    ("h", "4. Contractual requirements"),
    ("p", "No Tier 1 or Tier 2 supplier is engaged without the following terms in the executed "
          "contract. Legal will not release a contract for signature without them, and a purchase "
          "order raised against an unsigned contract is a policy breach."),
    ("b", "A data processing agreement naming the categories of data and the purposes of processing."),
    ("b", "Breach notification to Northwind within 24 hours of the supplier becoming aware."),
    ("b", "A right to audit, exercisable annually with 14 days' notice."),
    ("b", "Prior written approval for any sub-processor, with flow-down of these same terms."),
    ("b", "Defined return and secure destruction of data within 30 days of termination, evidenced "
          "by a certificate of destruction."),
    ("b", "Liability provisions that are not capped below the reasonably foreseeable cost of a "
          "breach of the data in scope."),
    ("h", "5. Ongoing monitoring"),
    ("p", "Assessment at onboarding establishes a position at a point in time. Suppliers change: "
          "they are acquired, they move infrastructure, they add sub-processors, and their staff "
          "turn over. Monitoring is therefore continuous rather than periodic."),
    ("p", "Tier 1 suppliers are subject to continuous external attack-surface monitoring, immediate "
          "review on any publicly disclosed breach affecting them, and a service review at least "
          "twice yearly with the business sponsor and Information Security present."),
    ("p", "Any supplier that suffers a security incident affecting Northwind data moves to enhanced "
          "monitoring for 12 months irrespective of tier, and the business sponsor must produce a "
          "written continuation case for the Security Committee."),
    ("h", "6. Exit"),
    ("p", "Every Tier 1 engagement has a documented exit plan before it begins, covering data "
          "extraction format, transition period, and the alternative supplier or in-house "
          "capability. An exit plan written during an incident is written too late."),
    ("p", "On termination, Information Security confirms data destruction, revokes all federated "
          "access, and removes the supplier from the network allow-list. The engagement is closed in "
          "the supplier register only after all three are evidenced."),
]

INCIDENT_RUNBOOK = [
    ("h", "1. Scope and principles"),
    ("p", "This runbook describes how Northwind Analytics Ltd responds to a suspected information "
          "security incident. It is written to be followed under pressure by someone who has not "
          "read it recently, so it favours explicit instruction over discussion."),
    ("p", "Three principles govern every decision during a response. Preserve evidence before "
          "attempting remediation. Communicate early and imprecisely rather than late and "
          "precisely. Assume the reporter is right until the investigation shows otherwise."),
    ("h", "2. What counts as an incident"),
    ("p", "An incident is any event that may compromise the confidentiality, integrity, or "
          "availability of Company or client information. Certainty is not required to report; "
          "suspicion is sufficient and is the intended threshold."),
    ("b", "Suspected phishing, whether or not anyone interacted with it."),
    ("b", "Malware detected or suspected on any device."),
    ("b", "Loss or theft of any device holding Company data or credentials."),
    ("b", "Credentials, API keys, or private keys exposed in any way, including in a private "
          "repository, a ticket, or a chat message."),
    ("b", "Information sent to the wrong recipient."),
    ("b", "Unexpected system behaviour that cannot be readily explained."),
    ("b", "Any external request for information or access that seems unusual in its urgency, its "
          "channel, or its claimed authority."),
    ("h", "3. Immediate actions on discovery"),
    ("p", "Report first. Contact Security Operations through the incident line or the "
          "#security-incidents channel. Do not wait to confirm your suspicion, gather more detail, "
          "or check with a colleague."),
    ("p", "Do not investigate, contain, or remediate unless explicitly instructed. Well-intentioned "
          "action routinely destroys the evidence needed to establish scope. Do not power off an "
          "affected machine; disconnect it from the network if instructed and leave it running, "
          "because memory contents are frequently the only record of what executed."),
    ("p", "Do not discuss the incident outside the response channel, including with colleagues who "
          "are not involved. Where a compromise of communications is possible, the response team "
          "will move to an out-of-band channel and will tell you which one."),
    ("pb", ""),
    ("h", "4. Severity classification"),
    ("p", "Severity is assigned by the Incident Commander within 30 minutes of triage and is "
          "reviewed at every checkpoint. It may be raised or lowered as understanding improves; "
          "both directions are normal and neither is a criticism of the initial call."),
    ("b", "<b>SEV1 — Critical.</b> Confirmed compromise of production, confirmed exfiltration of "
          "Confidential or Restricted data, ransomware, or any incident affecting client data. "
          "Executive Committee notified immediately. Response is continuous."),
    ("b", "<b>SEV2 — High.</b> Confirmed compromise of a non-production system, credential "
          "compromise with no evidence of use, or malware contained on a single endpoint. Response "
          "during extended hours."),
    ("b", "<b>SEV3 — Moderate.</b> Suspected but unconfirmed compromise, policy violation with "
          "security implications, or a near miss worth investigating."),
    ("h", "5. Roles"),
    ("p", "The Incident Commander owns the response and is the single decision-maker. They do not "
          "perform technical work; their job is to hold the whole picture, and someone deep in a log "
          "file cannot do that."),
    ("p", "The Communications Lead owns all internal and external messaging, including to clients "
          "and regulators. No one else communicates about the incident outside the response team."),
    ("p", "The Scribe maintains the timeline: what was observed, when, by whom, and what was done in "
          "response. The timeline is written contemporaneously, never reconstructed afterwards."),
    ("p", "Technical Responders investigate and remediate as directed. Where a responder disagrees "
          "with a decision, they say so once, clearly, and then execute — and the disagreement is "
          "recorded in the timeline for the post-incident review."),
    ("h", "6. Containment, eradication, recovery"),
    ("p", "Containment limits further damage: isolating hosts, revoking sessions and credentials, "
          "blocking indicators, and disabling affected accounts. Containment decisions are made "
          "quickly and are reversible where possible."),
    ("p", "Eradication removes the cause: patching the exploited weakness, removing persistence, and "
          "rotating every credential that could have been observed. Rotation covers everything the "
          "compromised context could reach, not only what is known to have been used."),
    ("p", "Recovery restores service from a known-good state, with heightened monitoring for at "
          "least 14 days. A system is returned to service only when the Incident Commander is "
          "satisfied the cause is understood, not when the symptom stops."),
    ("h", "7. Regulatory notification"),
    ("p", "Any incident involving personal data is assessed by the Data Protection Officer within 24 "
          "hours for notification obligations. Client contracts may impose shorter deadlines than "
          "regulation; the Communications Lead checks both."),
    ("h", "8. Post-incident review"),
    ("p", "Every SEV1 and SEV2 receives a written review within five business days, covering "
          "timeline, root cause, contributing factors, what worked, and what did not."),
    ("p", "The review is blameless. It examines systems and processes, never individuals. An "
          "organisation that punishes the person who reported an incident learns about its next "
          "incident from a customer, or from a newspaper."),
]

DATA_RETENTION = [
    ("h", "1. Purpose"),
    ("p", "This schedule states how long Northwind Analytics Ltd keeps each category of information "
          "and what happens at the end of that period. It supports the Information Security Policy "
          "and the Company's obligations under the Digital Personal Data Protection Act."),
    ("p", "Retention is a control in both directions. Keeping information longer than necessary "
          "increases the harm of any future breach and creates disclosure obligations the Company "
          "would otherwise not have. Deleting it too early destroys evidence the Company may need."),
    ("h", "2. Governing rules"),
    ("b", "The retention clock starts at the trigger event named in the schedule, not at the date "
          "the record was created."),
    ("b", "Deletion at the end of a period is automatic and evidenced in the retention log. It is "
          "not a task somebody remembers to do."),
    ("b", "Where a legal hold is in force, retention is suspended for the records in scope until the "
          "hold is lifted in writing by the Company Secretary."),
    ("b", "Backups follow the retention of the data they contain. A backup is not a permitted route "
          "to indefinite retention."),
    ("b", "Where two periods could apply, the longer applies, unless the shorter is a statutory "
          "maximum rather than a minimum."),
    ("h", "3. Schedule"),
    ("p", "<b>Client engagement records.</b> Deliverables, correspondence, working papers, and "
          "contracts: 7 years from engagement close. Client data processed under an engagement is "
          "returned or destroyed within 30 days of close unless the contract says otherwise."),
    ("p", "<b>Financial records.</b> Ledgers, invoices, expense claims, tax filings, and supporting "
          "evidence: 8 years from the end of the financial year to which they relate."),
    ("p", "<b>Employee records.</b> Contracts, payroll, performance, and disciplinary records: 7 "
          "years from the end of employment. Medical information: 3 years from the end of "
          "employment, held separately with restricted access."),
    ("p", "<b>Recruitment records.</b> Unsuccessful applicants: 6 months from the decision. "
          "Successful applicants: merged into the employee record."),
    ("p", "<b>Security logs.</b> Authentication, authorisation, administrative action, and network "
          "flow: 13 months. The period is deliberately just over a year so that an annual pattern "
          "remains visible for comparison."),
    ("p", "<b>Incident records.</b> Timelines, evidence, and post-incident reviews: 7 years from "
          "closure. Evidence that could support a criminal prosecution is retained indefinitely on "
          "instruction from the Company Secretary."),
    ("p", "<b>Email.</b> 3 years from send or receipt, after which items are deleted from mailboxes "
          "and from backup on the backup cycle. Business records that must be kept longer are filed "
          "into the appropriate system rather than left in a mailbox."),
    ("p", "<b>Instant messaging.</b> 90 days. Messaging is not a system of record and must not be "
          "used to hold decisions, approvals, or client commitments."),
    ("p", "<b>CCTV.</b> 30 days, extended only where footage is subject to an active investigation."),
    ("p", "<b>Marketing contact data.</b> 2 years from the last meaningful interaction, or "
          "immediately on withdrawal of consent, whichever is earlier."),
    ("p", "<b>Vendor assessments.</b> Duration of the engagement plus 3 years."),
    ("h", "4. Deletion standard"),
    ("p", "Electronic deletion is by cryptographic erasure where the storage supports it, and by "
          "overwrite otherwise. Physical media leaving Company control is destroyed by a certified "
          "provider and a destruction certificate is retained for 3 years."),
    ("p", "Deletion means the record is irrecoverable through ordinary means. Moving a file to an "
          "archive folder, removing a database index, or deleting a pointer while retaining the "
          "object is not deletion for the purposes of this schedule."),
    ("h", "5. Responsibilities"),
    ("p", "System owners implement retention in the systems they own and confirm annually that "
          "automated deletion is running and producing log evidence."),
    ("p", "The Data Protection Officer maintains this schedule, reviews it annually, and reports "
          "exceptions to the Security Committee. Any system that cannot enforce its stated retention "
          "is recorded in the risk register with a remediation date."),
]

ENGINEERING_ONBOARDING = [
    ("h", "1. Your first week"),
    ("p", "This guide covers what a new engineer at Northwind Analytics needs in order to be "
          "productive. It is written on the assumption that you are competent and new, which is a "
          "different thing from being inexperienced."),
    ("p", "Nobody expects a commit on day one. The expectation for week one is that you can build "
          "and run the platform locally, that you know who to ask about what, and that you have "
          "asked at least one question that felt obvious. The last of those is the important one."),
    ("h", "2. Access and accounts"),
    ("p", "Your manager raises access requests before your start date. On day one you should have: "
          "an identity provider account with MFA enrolled, a laptop enrolled in device management, "
          "repository access to your team's projects, and read access to the staging environment."),
    ("p", "Production access is not granted at onboarding. It is granted after you have completed "
          "the security induction, shipped changes through the normal pipeline, and been on-call "
          "shadow for one rotation. This is not a statement about you; it is how least privilege "
          "works and it applies to everyone including the CTO."),
    ("p", "Set up the password manager before anything else. Storing a credential in a note file, a "
          "browser profile, or a repository is the single most common policy breach and it is "
          "avoidable in the first hour."),
    ("h", "3. Development environment"),
    ("p", "Everything runs locally. Clone the platform repository, run the bootstrap script, and you "
          "will have PostgreSQL, the object store emulator, and the API running under Docker "
          "Compose. The bootstrap script is idempotent; running it twice is safe."),
    ("p", "If the bootstrap script fails, that is a defect in the script, not in your machine. Raise "
          "it. Onboarding friction is invisible to everyone who onboarded before the thing broke, so "
          "the only person who can report it is you, and only during your first week."),
    ("h", "4. How we ship"),
    ("p", "Trunk-based development with short-lived branches. A branch that lives longer than three "
          "days is a signal that the change is too large, not that the reviewer is slow."),
    ("p", "Every change requires one approving review. Reviews are expected within one working day. "
          "A review comment is a question until proven otherwise, and the author is free to disagree "
          "with any of them and say why."),
    ("p", "CI runs unit tests, integration tests, type checking, linting, dependency audit, and "
          "container scanning. A red build is never merged, and 'the test is flaky' is a defect to "
          "be fixed rather than a reason to re-run."),
    ("p", "Deployment to production is automatic on merge to main, behind feature flags. A change "
          "that cannot be flagged is a change that needs a deployment plan, agreed before it starts."),
    ("pb", ""),
    ("h", "5. Testing expectations"),
    ("p", "Write the test that would have caught the bug. Coverage percentage is reported but is not "
          "a target; a suite at 95% that tests only the happy path is worse than one at 70% that "
          "tests the failure modes, because it produces false confidence."),
    ("p", "Integration tests run against real dependencies in containers, not mocks. Mocks are for "
          "unit tests and for third-party services we do not control."),
    ("p", "A passing test suite proves the pieces behave. It does not prove the system works. Before "
          "calling a change done, run it and use it as a user would."),
    ("h", "6. On-call"),
    ("p", "Engineers join the on-call rotation after approximately three months, starting as a "
          "shadow for one full rotation. The rotation is one week in six and is compensated."),
    ("p", "You are never expected to resolve an incident alone. Escalating is the correct action and "
          "carries no stigma whatsoever. The person who escalates at 03:00 after fifteen minutes is "
          "doing the job properly; the person who struggles alone until 06:00 is not."),
    ("p", "After any incident you were involved in, you will be asked to contribute to a blameless "
          "review. Say what you actually saw and what you actually did, including anything that "
          "turned out to be wrong. That is where the value is."),
    ("h", "7. Security expectations for engineers"),
    ("p", "Treat every input as untrusted, including from internal systems and including from a "
          "document a user uploaded. Validate at the boundary and encode at the point of use."),
    ("p", "Never commit a secret. If you do, rotate it immediately and tell Security Operations. "
          "Rewriting history does not make an exposed credential safe, because you cannot know who "
          "cloned the repository before you rewrote it."),
    ("p", "Where you work on retrieval-augmented or agentic features, remember that anyone who can "
          "add a document to a corpus can influence what the model does. Retrieved content is data, "
          "never instruction, and it must be delimited as such in every prompt you construct."),
    ("h", "8. Asking for help"),
    ("p", "The team channel is the default. A question asked in the open helps the next person and "
          "is searchable; the same question in a direct message helps one person once."),
    ("p", "There is no waiting period before asking. The convention is roughly thirty minutes of "
          "genuine effort, then ask, describing what you tried. Nobody is measuring."),
]

QUARTERLY_REVIEW = [
    ("h", "1. Executive summary"),
    ("p", "Q4 FY2025 closed ahead of plan on revenue and behind plan on gross margin. Annual "
          "recurring revenue reached INR 412 crore, up 31% year on year, against a plan of INR 398 "
          "crore. Gross margin of 68.2% was 2.4 points below plan, driven almost entirely by cloud "
          "infrastructure cost growth outpacing customer growth."),
    ("p", "Net revenue retention was 114%, the fourth consecutive quarter above 110%. Gross logo "
          "retention was 91%, down from 94% in Q3, with the decline concentrated in the Essential "
          "tier. Two Enterprise accounts churned, both following acquisition by a parent with an "
          "incumbent platform."),
    ("h", "2. Revenue detail"),
    ("p", "New business contributed INR 34.2 crore of new ARR against a plan of INR 30.0 crore. "
          "Twenty-nine new logos closed, of which nine were Enterprise tier. Average new-logo "
          "contract value rose to INR 118 lakh from INR 94 lakh a year earlier, reflecting a "
          "deliberate shift up-market rather than a price increase."),
    ("p", "Expansion within the existing base contributed INR 21.7 crore, ahead of the INR 18.0 "
          "crore plan. Seat expansion accounted for two thirds of this and tier upgrades the "
          "remainder. The strongest expansion cohort remains customers onboarded 18 to 30 months "
          "ago, which is consistent with the observed adoption curve."),
    ("p", "Churn and contraction totalled INR 9.1 crore against a plan of INR 7.5 crore. The "
          "overrun is attributable to the two Enterprise departures noted above; excluding those, "
          "churn was marginally better than plan."),
    ("h", "3. Margin and cost"),
    ("p", "Cloud infrastructure cost grew 44% year on year against revenue growth of 31%. Analysis "
          "attributes roughly 60% of the excess to query workloads on three large tenants whose "
          "model design has not been reviewed since onboarding, and 40% to non-production "
          "environments left running outside working hours."),
    ("p", "Two remediations are underway. A model review programme for the twelve largest tenants "
          "begins in Q1 and is expected to recover 5 to 7 points of infrastructure efficiency. "
          "Automatic shutdown of non-production environments outside 07:00-22:00 is already live and "
          "reduced non-production spend by 38% in its first full month."),
    ("p", "Support cost per customer fell 9% despite ticket volume rising 14%, following the "
          "publication of the self-service knowledge base in October. Deflection is currently 22% "
          "of would-be tickets against a target of 30%."),
    ("h", "4. Product"),
    ("p", "Three planned releases shipped in the quarter. Customer-managed encryption keys shipped "
          "to Enterprise in October and has been adopted by eleven accounts. Incremental refresh for "
          "watermarked sources shipped in November and is now used by 64% of eligible tenants. The "
          "semantic layer versioning capability shipped in December, two weeks late."),
    ("p", "Mumbai data residency, planned for Q4, slipped to Q1 FY2026. The cause was an "
          "underestimate of the work needed to separate backup and disaster recovery paths by "
          "region. Seven prospects are gated on this capability, representing approximately INR 14 "
          "crore of pipeline."),
    ("h", "5. Operations"),
    ("p", "Platform availability was 99.94% against a 99.9% commitment. There was one SEV1 lasting "
          "47 minutes in November, caused by a schema migration that acquired a lock on a large "
          "table during business hours. The post-incident review produced two actions, both closed."),
    ("p", "There were no security incidents affecting client data. One SEV2 was raised in October "
          "when an API key was committed to a private repository; it was rotated within 20 minutes "
          "of detection and log review confirmed no use of the key outside expected sources."),
    ("h", "6. People"),
    ("p", "Headcount closed at 287, up from 241 a year earlier. Voluntary attrition was 11.2% "
          "annualised, below the 14% plan assumption. Engineering attrition was 8.4%."),
    ("p", "Nineteen roles were open at quarter end, of which eight are in engineering and five in "
          "client services. Median time to hire was 41 days, improved from 58 days a year earlier."),
    ("h", "7. Outlook"),
    ("p", "The FY2026 plan assumes 28% ARR growth, margin recovery to 71% by Q3, and gross logo "
          "retention returning above 93% as the Essential tier onboarding changes take effect."),
    ("p", "The principal risks to that plan are the Mumbai residency slip constraining regulated "
          "prospects, continued infrastructure cost growth if the model review programme "
          "underdelivers, and concentration risk from the largest customer at 6.1% of ARR."),
]


DOCUMENTS = [
    ("vendor_risk_assessment_procedure.pdf",
     "Vendor Risk Assessment Procedure",
     "Northwind Analytics Ltd · NW-SEC-009 · Revision 2 · Classification: Internal",
     VENDOR_RISK),
    ("incident_response_runbook.pdf",
     "Incident Response Runbook",
     "Northwind Analytics Ltd · NW-SEC-012 · Revision 6 · Classification: Internal",
     INCIDENT_RUNBOOK),
    ("data_retention_schedule.pdf",
     "Data Retention Schedule",
     "Northwind Analytics Ltd · NW-LEG-007 · Revision 3 · Classification: Internal",
     DATA_RETENTION),
    ("engineering_onboarding_guide.pdf",
     "Engineering Onboarding Guide",
     "Northwind Analytics Ltd · NW-ENG-001 · Revision 8 · Classification: Internal",
     ENGINEERING_ONBOARDING),
    ("quarterly_business_review_q4_fy2025.pdf",
     "Quarterly Business Review — Q4 FY2025",
     "Northwind Analytics Ltd · NW-FIN-Q425 · Final · Classification: Confidential",
     QUARTERLY_REVIEW),
]


def main() -> int:
    for filename, title, subtitle, blocks in DOCUMENTS:
        path = build(filename, title, subtitle, blocks)
        print(f"wrote {path.relative_to(Path(__file__).parent)}  ({path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
