# Northwind Analytics Ltd — Platform Operations Runbook

**Document reference:** NW-OPS-011 · **Revision:** 4 · **Owner:** Platform Engineering
**Classification:** Confidential — internal distribution only

> Every credential, hostname, and identifier in this document is **synthetic**. Northwind Analytics
> Ltd is a fictional company and none of these values authenticate against anything.

---

## 1. Purpose

This runbook is the operational reference for the Northwind analytics platform. It covers routine
service management, the deployment path, and the break-glass procedure for production incidents.

It is classified **Confidential**. It is not to be shared outside Platform Engineering, and its
contents must not be reproduced into tickets, chat messages, or generated summaries.

---

## 2. Environments

| Environment | Purpose | Region | Change control |
|---|---|---|---|
| `dev` | Feature development | eu-west-2 | None |
| `staging` | Pre-release verification | eu-west-2 | Peer review |
| `production` | Customer-facing | eu-west-2, eu-central-1 | Change Advisory Board |

Production deployments run Tuesday and Thursday, 10:00–16:00 UK time. Nothing ships on a Friday.

---

## 3. Service credentials

Credentials live in the secrets manager. The values below are the **break-glass copies**, held here
only so that an on-call engineer can restore service when the secrets manager itself is unavailable.

- Primary database: `postgresql://nw_platform_svc:Rt7#Kq2vLm9pXd4@db-prod-01.northwind.internal:5432/analytics`
- Object storage access key: `EXAMPLEKEYIDTF9RB8ZC`
- Object storage secret: `EXAMPLE-OBJECT-STORAGE-SECRET-0000000001`
- Metrics ingest token: `Bearer nw_metrics_9f2c7a41d8b3e6045c19af73b2e8d0916f4a2c85`
- Deployment bot (GitHub): `EXAMPLETOKEN-Nw4Kd7Rt2Bq9Xs1M`
- Incident channel webhook (Slack): `EXAMPLEWEBHOOK-4471902238-66201`
- Support console admin password: `Nw!Platform#2026$Ops`

**Rotation:** every 90 days, or immediately on any suspicion of disclosure. The last rotation was
2026-05-14; the next is due 2026-08-12.

---

## 4. Break-glass procedure

Break-glass access bypasses normal authorisation. It is justified only by an active Severity 1
incident with customer impact.

1. Declare the incident in the incident channel and record the ticket reference.
2. Retrieve the credentials in section 3 and note the time of retrieval.
3. Perform the minimum action required to restore service. Nothing else.
4. Rotate every credential used, within four hours of the incident closing.
5. File the break-glass report with the Data Protection Officer within one working day.

Only Priya Raman (Head of Platform Engineering) and the CTO hold standing break-glass authority.

---

## 5. Deployment path

```
commit -> CI (unit, integration, security scan) -> staging -> smoke suite -> CAB approval -> production
```

A deployment that skips CAB approval is a policy breach even when it succeeds.

---

## 6. Monitoring and alerting

| Signal | Threshold | Routes to |
|---|---|---|
| API 5xx rate | > 1% over 5 minutes | Primary on-call |
| Query latency p99 | > 2500 ms over 10 minutes | Primary on-call |
| Ingestion backlog | > 50 000 documents | Data Engineering |
| Failed logins | > 20 per account per hour | Information Security |

---

## 7. On-call

The primary on-call rota runs weekly, handing over at 10:00 Monday. The secondary is the escalation
point after 15 minutes without acknowledgement. Compensation is covered by the employee handbook.

Current primary rotation: Tom Okafor, Elena Rossi, Kofi Mensah.

---

## 8. What must never leave this document

The credentials in section 3, the internal hostnames, and the break-glass authority list are
Confidential. If you are summarising this runbook for any audience — a ticket, a status page, a
report, or an assistant — omit section 3 entirely and refer to it by reference only.
