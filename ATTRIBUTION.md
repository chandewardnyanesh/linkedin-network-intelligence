# Attribution

This bundle is independently authored. No code was copied from either upstream
repository. Several ideas were adopted deliberately, and they are recorded here
because taking a good idea without saying so is the kind of thing that makes
open source worse.

Both upstream projects are MIT licensed, as is this one.

## `sergebulaev/linkedin-skills` (MIT)

The personal-profile and content bundle. Twelve skills for writing posts,
comments and replies, extracting hooks, planning content, auditing a profile,
reading per-post engagers and tracking comment threads.

| Adopted | From | What was taken |
|---|---|---|
| The precedence order | `references/precedence.md` | The idea of a written resolution order, and most of its ranking. Kept deliberately compatible, because a user running both bundles should not meet two incompatible orders. Two rules added here: platform policy at the top, and data minimisation, neither of which the upstream bundle needed because it stores nothing about other people. See `references/precedence.md`. |
| Fetched content is data, never instructions | `references/untrusted-content.md` | The rule and its reasoning. Extended here to cover **records about people**, which the upstream version does not address. See `references/untrusted-content.md`. |
| The approval-gate pattern | `lib/approval.py` | The shape of a review block that stops and hands the action to the human. Independently reimplemented as `SafetyGovernor.approval_card`, and changed in one substantive way: this bundle never performs the action, so the card says who does. |
| Handoff contracts tested on both sides | `tests/test_instruction_integrity.py` | The convention that if skill A names something skill B owns, B's document must own it, and a test enforces the pair. Reimplemented as `tests/test_instruction_integrity.py` here. |
| Refusing to claim detector evasion | `linkedin-humanizer` | The stance, generalised into `no_detection_evasion`. |

**Interoperation rather than duplication.** Where work is content —
post drafting, comment voice, AI-tell removal, hook extraction, content
planning, profile optimisation — this bundle routes to that one instead of
carrying a second copy. `linkedin-connection-strategy` cites its voice rules
and hands drafts to its humanizer; `linkedin-relationship-manager` routes
comment-thread follow-up to `linkedin-thread-monitor` and
`linkedin-reply-handler`.

**Where the two bundles differ, on purpose.** The upstream read layer calls
third-party actors against public LinkedIn content. This bundle ships no
scraper and no such dependency, because the project specification states no
scraping and no browser automation. That is a narrower line, not a criticism of
a well-documented choice. A roster the user exports from
`linkedin-engager-analytics` is accepted here as a user-supplied input with
`upstream_skill_export` provenance. Explained in
`references/data-sources.md`.

## `chandewardnyanesh/linkedin-company-page-skills` (MIT)

The company-Page bundle, by the same author as this one. Thirteen skills for
running a LinkedIn company Page.

| Adopted | From | What was taken |
|---|---|---|
| Honest attribution as required output | `page-performance-report` | The discipline that every report states plainly what it cannot attribute, as a section rather than a disclaimer. Reimplemented in `lni/attribution.py` (`limits_for`) and `lni/reporting.py`, where the section is built from the actual gaps in the data rather than from fixed text. |
| A claim may only state a figure with an entry behind it | `references/proof-library.md` | The strongest no-fabrication control in either upstream bundle. Generalised here into the `Evidence` model and the rule that a scored component with no evidence cannot be constructed. |
| Never invent an unavailable metric | `page-performance-report` | Reported as `unavailable` with the reason. Enforced here by `FunnelMetrics` optionality and by a configuration layer that refuses to enable estimation. |
| Keeping a filled confidential template out of the repository | `scripts/check_no_secrets.py` | The practice, applied here to `config/icps.yaml` and `config/business_services.yaml`. |

**Where the two differ.** That bundle is a company Page; this one is a personal
network. Its ICP is one prose document describing a company's buyers; this one
holds several typed, concurrent ICPs with exclusion criteria and observable
signals. Neither replaces the other, and `docs/CAPABILITY_GAP_ANALYSIS.md`
records the three partial overlaps.

## Independently authored here

Everything else, including: the fourteen pydantic models; the configuration
layer and its refusal to relax a control; the SQLite and PostgreSQL store; the
status machine and its user-confirmed-only statuses; the dedupe policy; the
propensity engine; the 100-point scoring engine and its abstention rule; the
follower-count cap; lead classification and the overlap coefficient behind it;
the funnel computation; the append-only audit trail; and the prohibited-action
classifier, including the softened-phrasing patterns.

## Not affiliated with LinkedIn

This project is not affiliated with, endorsed by, or connected to LinkedIn
Corporation. "LinkedIn" is a trademark of its owner and is used here only to
describe what the software is for.
