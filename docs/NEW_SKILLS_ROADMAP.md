# New Skills Roadmap

The finalised build list, in dependency order, with what each skill owns and
what it is forbidden from doing.

## Finalised list

Twelve skills plus one root orchestrator. Five are reduced in scope against the
Phase-2 brief; the reductions and their reasons are in
`CAPABILITY_GAP_ANALYSIS.md`.

| Order | Skill | Owns | Depends on |
|---|---|---|---|
| 0 | `linkedin-network-growth` (root) | The 12-step workflow, one-time and weekly modes | all |
| 1 | `linkedin-policy-safety-governor` | Prohibited-action classification, approval gate, audit trail, platform-restriction handling | — |
| 2 | `linkedin-icp-builder` | ICP definitions, exclusions, observable signals | governor |
| 3 | `linkedin-audience-intelligence` | Analytics-export analysis, topic affinity, audience gap | icp-builder |
| 4 | `linkedin-network-discovery` | Candidate sourcing within the authorised-source boundary, provenance, dedupe | icp-builder, crm |
| 5 | `linkedin-engagement-propensity` | Propensity band, evidence, confidence, approach | icp-builder, crm |
| 6 | `linkedin-network-scoring` | 100-point aggregate, components, priority class | propensity, icp-builder |
| 7 | `linkedin-lead-intelligence` | Service-category opportunity hypotheses, discovery questions | scoring, crm |
| 8 | `linkedin-connection-strategy` | Connection rationale, invitation drafts (draft-only) | scoring, crm, governor |
| 9 | `linkedin-network-crm` | Records, identity, status machine, history, provenance, import/export, deletion | governor |
| 10 | `linkedin-relationship-manager` | Person-level follow-up cadence, anti-repetition, collaboration spotting | crm, governor |
| 11 | `linkedin-content-audience-attribution` | Topic → audience quality over time, honest attribution limits | audience-intelligence, crm |
| 12 | `linkedin-network-growth-analyst` | Funnel metrics, weekly and monthly reports, per-ICP performance | crm, all |

Implementation order differs from the user-facing order: the governor, the data
models and the CRM are built first because everything else writes through them.

## Shared code, so rules exist once

| Module | Single source of truth for |
|---|---|
| `lni/models.py` | All 14 Phase-5 data models, pydantic-validated |
| `lni/config.py` | YAML load, layer merge, validation, missing-value detection |
| `lni/db.py` | Schema, migrations, SQLite and PostgreSQL backends |
| `lni/crm.py` | Record identity, status transitions, history |
| `lni/dedupe.py` | URL normalisation and candidate matching |
| `lni/propensity.py` | Evidence grading and confidence — called by scoring, never duplicated |
| `lni/scoring.py` | Weighted aggregate over propensity output |
| `lni/leads.py` | Opportunity classification |
| `lni/attribution.py` | Content ↔ audience joins |
| `lni/reporting.py` | Funnel computation; `unavailable` rather than estimates |
| `lni/safety.py` | Prohibited-action classifier, approval requirement, audit writes |
| `lni/provenance.py` | Source records and verification dates |

A rule that two skills need lives in one module and is cited by both. This is
the handoff convention adopted from Bundle A's
`tests/test_instruction_integrity.py`, and it is tested the same way.

## Non-negotiables, applied to every skill

1. No LinkedIn scraping, no browser automation, no automated sending.
2. Every external action is drafted, presented, and performed by the human.
3. Every stored claim carries a source and a verification date, or it is marked
   `unverified` and is not used as evidence.
4. Observations and predictions are labelled separately in every output.
5. A metric that is not available is printed as `unavailable` with the reason.
6. No hardcoded personal data anywhere in the package; missing configuration
   produces a question, never an invented value.
7. Personal data is minimised, exportable and deletable per subject.

## Deferred, with reasons

| Item | Reason |
|---|---|
| PostgreSQL as default | SQLite covers single-user research; Postgres ships as an optional backend behind the same repository interface |
| Official LinkedIn API client | Requires a Partner Program approval the typical user does not hold; the integration point is defined and left unimplemented rather than faked |
| A UI | Out of scope for an Agent Skills bundle |
| Automated directory crawling | Would reintroduce the scraping question; directories are read by the user or by `WebFetch` on a page the user names |
