# Capability Gap Analysis

Each Phase-2 proposal against what the audit found. Verdicts are one of:

- **BUILD** — nothing comparable exists on this surface.
- **BUILD, SCOPED** — something partially overlaps; only the incremental
  capability is built, and the skill delegates the overlapping part upstream.
- **EXCLUDE** — substantially implemented already; do not rebuild.

"Surface" is the distinction that decides most of these: a **personal network**
(people the user connects to) is not a **company Page audience**, and a
**per-post engager list** is not a **persistent contact record**.

Legend for prior art: `A#` = `sergebulaev/linkedin-skills`,
`B#` = `chandewardnyanesh/linkedin-company-page-skills` (see audit §1.2, §2).

---

## Summary table

| # | Proposed skill | Closest prior art | Overlap | Verdict |
|---|---|---|---|---|
| 1 | `linkedin-audience-intelligence` | A8 engager-analytics, B12 page-performance-report | ~25% | **BUILD, SCOPED** |
| 2 | `linkedin-icp-builder` | B1 icp-firmographics template | ~15% | **BUILD** |
| 3 | `linkedin-network-discovery` | none | 0% | **BUILD** |
| 4 | `linkedin-engagement-propensity` | A8 tiering, A7 thread-monitor signals | ~20% | **BUILD, SCOPED** |
| 5 | `linkedin-network-scoring` | A8 four-tier heuristic, B8 commenter scoring | ~10% | **BUILD** |
| 6 | `linkedin-connection-strategy` | A8 one-line openers, A2 comment-drafter voice | ~15% | **BUILD, SCOPED** |
| 7 | `linkedin-network-crm` | none | 0% | **BUILD** |
| 8 | `linkedin-lead-intelligence` | A8 "prospect" tier, B8 sales-question routing | ~10% | **BUILD** |
| 9 | `linkedin-content-audience-attribution` | B12 follower composition, A8 per-post engagers | ~30% | **BUILD, SCOPED** |
| 10 | `linkedin-relationship-manager` | A7 thread-monitor | ~25% | **BUILD, SCOPED** |
| 11 | `linkedin-network-growth-analyst` | A10 advocacy ROI, B12 Page report | ~20% | **BUILD, SCOPED** |
| 12 | `linkedin-policy-safety-governor` | precedence.md, untrusted-content.md, approval.py, SECURITY.md (both bundles) | ~40% | **BUILD, SCOPED** |

**Nothing is excluded outright.** Twelve skills are built, five of them at
reduced scope with an explicit upstream delegation. That reduction is real: it
removes roughly a third of what a naive reading of Phase 2 would have produced.

Capabilities deliberately **not** built, because they already exist, are listed
in §13.

---

## 1. `linkedin-audience-intelligence` — BUILD, SCOPED

**Prior art.** A8 pulls likers and commenters for **one post URL** and sorts
them into peer / aspirational / prospect / other, then prints outbound action
lists. B12 reports **Page** follower composition against a Page ICP.

**What is missing.**

| Proposed capability | Exists? | Where it lands |
|---|---|---|
| Analyse user-provided LinkedIn **analytics exports** | No. Neither bundle ingests an export file. | Build |
| Post-level performance analysis across a corpus | No. A8 is single-post; A6 plans forward, never looks back. | Build |
| Audience demographics where the export provides them | No | Build |
| Recurring engagement patterns across posts and weeks | No | Build |
| **Topic affinity matrix** (topic × audience segment × engagement) | No. Nothing in either bundle joins topic to audience quality. | Build |
| Segment by professional relevance | Partially — A8 has four fixed tiers | Build on configurable ICPs (#2), not fixed tiers |
| **Gap between existing and desired audience** | No | Build — this is the skill's core output |
| Recommend content themes to close that gap | Partially — B11 trend-radar recommends themes, from category trends, for a Page | Build for personal audience gap; cite B11 for trend sourcing |

**Scope reduction applied.** The skill does **not** fetch engagers. Where the
user has an A8 roster it is imported as CSV. The skill's own inputs are export
files and pasted post metrics.

**Delegation.** Per-post engager pulls → A8. Category trend sourcing → B11.

---

## 2. `linkedin-icp-builder` — BUILD

**Prior art.** B1 produces `references/icp-firmographics.md`: one ICP, in
markdown, for a company's buyers — account dimensions plus a four-role table.

**Why that is not this.** Four substantive differences, each load-bearing:

1. **Cardinality.** B1 is one ICP. Phase 2 requires eight concurrent purposes
   (networking, personal brand, AI/tech, startup ecosystem, business
   development, agency clients, partnerships, industry-specific) coexisting,
   with a candidate able to match several and carry a primary classification.
2. **Machine-readability.** B1 is prose a human fills in. Every downstream skill
   here (#3, #4, #5, #8) consumes ICPs programmatically; they need typed fields
   with validation.
3. **Exclusion criteria.** Absent from B1. Required here, and it is the field
   that does the most work in practice — it is what stops a discovery run
   returning recruiters and MLM accounts.
4. **Observable engagement signals.** Absent from B1. Required here, and it is
   what makes an ICP falsifiable rather than aspirational: the signals are what
   #4 and #5 actually look for.

**Verdict.** Build. Interoperates with B1 — a filled `icp-firmographics.md` is
accepted as a seed input and converted into one `business_development` ICP.

---

## 3. `linkedin-network-discovery` — BUILD

**Prior art.** None in either bundle. Neither has any notion of finding a person
who is not already in a thread the user is reading.

**Verdict.** Build in full, within the §4 data-source boundary from the audit:
user-supplied profile URLs and CSVs, the user's own LinkedIn data export,
authorised official APIs, public company websites, professional directories.
No scraping, no browser automation, source provenance on every record.

---

## 4. `linkedin-engagement-propensity` — BUILD, SCOPED

**Prior art.** A8 assigns a tier from profile attributes and prints an opener.
A7 classifies the user's own comment threads hot / warm / cool / dormant and
notes "inbound-quality signals."

**What is missing.** A8's tier is a *category assignment from who someone is*.
Propensity is a *prediction about what they will do*, with the evidence and a
confidence level attached, and it must distinguish what was observed from what
was predicted. Neither bundle carries a confidence level on anything, and
neither separates observation from inference anywhere in its output format.

**Scope reduction applied.** This skill does not re-derive ICP tiers (#2 owns
the definition, #5 owns the aggregate score). It produces exactly four things:
a propensity band, the evidence behind it, a confidence level, and a
relationship-building approach. It shares one implementation with #5 —
`lni/propensity.py` is called by `lni/scoring.py`, so there is one engine, not
two that drift.

**Hard rule carried from Bundle A's precedence order.** Never fabricate
engagement history; never claim access to private analytics. Unverified claims
are reported as `unverified`, not as evidence.

---

## 5. `linkedin-network-scoring` — BUILD

**Prior art.** A8's four tiers; B8's commenter ICP check. Both are categorical
and non-configurable; no weights, no components, no evidence trail.

**Verdict.** Build. The 100-point framework (ICP 25 / activity 15 / engagement
signals 20 / topic alignment 15 / influence 10 / business opportunity 15) with
configurable weights, per-component evidence and confidence, and a priority
class. Explicitly: **follower count is not a quality indicator** and is capped
at a small share of the influence component.

---

## 6. `linkedin-connection-strategy` — BUILD, SCOPED

**Prior art.** A8 produces "DM-able with one-line openers." A2 owns voice rules
for third-party comments, including the rule against name-dropping your own
product.

**What is missing.** A connection *rationale* grounded in a specific shared
context; multiple invitation variations; a recommended first conversation topic;
a follow-up approach; and the relationship-first sequencing that keeps a pitch
out of the first touch. A one-line opener is not an invitation strategy.

**Scope reduction applied.** Voice rules are not reimplemented. The skill cites
Bundle A's `references/voice-rules.md` and, where the user runs A4, hands drafts
to the humanizer rather than carrying its own de-AI pass.

**Hard rule.** Draft-only. The skill never sends an invitation or a message,
and it refuses to produce output intended for an automated sender.

---

## 7. `linkedin-network-crm` — BUILD

**Prior art.** None. Both bundles are stateless beyond two markdown files.

**Verdict.** Build in full: SQLite default, optional PostgreSQL, 13-status
state machine with legal transitions, dedupe on normalised profile URL plus
name+company fallback, interaction history, source provenance, last-verified
date, CSV import/export, filtering and segmentation, and per-subject deletion.

This is the skill the other eleven are organised around.

---

## 8. `linkedin-lead-intelligence` — BUILD

**Prior art.** A8's "prospect" tier is a label with no opportunity model. B8
routes a sales question out of a public Page thread.

**Verdict.** Build. Configurable service categories, opportunity
classification, discovery questions.

**Hard rules.** Do not infer confidential company information. Do not fabricate
purchasing intent. An opportunity is a *hypothesis with named observable
evidence*, or it is not recorded.

---

## 9. `linkedin-content-audience-attribution` — BUILD, SCOPED

**Prior art — the largest genuine overlap.** B12 reports Page follower
composition against an ICP, compares employee amplification reach to Page
reach, and says plainly what the data cannot attribute. A8 gives per-post
engagers.

**Why it still gets built.** B12 is a **Page** report. This is the **personal
profile** surface, where the metrics available to the user are different
(impressions, members-reached, profile views, followers gained, per-post
engagement from an export) and the question is different: *which topics brought
in people worth having?*

**What is missing.** Joining topic → audience quality over time; comparing
engagement by segment; tracking follower and connection growth against content;
distinguishing impressions / reactions / comments / shares / followers from
**business outcomes**.

**Scope reduction applied.** The honest-attribution discipline is **adopted
from B12 rather than reinvented** — the "what this cannot attribute" section is
a required part of the output, credited in `ATTRIBUTION.md`.

---

## 10. `linkedin-relationship-manager` — BUILD, SCOPED

**Prior art.** A7 tracks the user's own comments for author replies, flags the
6–24h warm window, and routes warm threads to A3.

**What is missing.** A7 is **thread-scoped**: it knows about comments, not
people. It cannot tell you that you have not spoken to someone in five months,
that two contacts should meet each other, or that a contact's stated project is
now due. Relationship state across many touchpoints over time requires the CRM
in #7, which does not exist upstream.

**Scope reduction applied.** Comment-thread follow-up is **not** reimplemented.
Where a thread needs a reply, this skill routes to A7/A3 exactly as A7 does.
This skill owns the person-level cadence, not the thread-level one.

**Hard rules.** Anti-repetition is a first-class constraint, not advice: a
contact with a recent touch is suppressed by the engine, not by a suggestion.
All external communication requires explicit human approval.

---

## 11. `linkedin-network-growth-analyst` — BUILD, SCOPED

**Prior art.** A10 defines advocacy ROI metrics for a team. B12 is a monthly
Page report.

**What is missing.** The personal networking funnel end to end: researched →
qualified → shortlisted → manually invited → accepted → conversation → engaged →
lead → meeting → opportunity, with per-ICP performance and acceptance rates.
Neither bundle has a funnel, because neither persists the stages.

**Scope reduction applied.** The report consumes the CRM in #7 and computes
nothing it cannot source. Metrics LinkedIn does not expose to the user, or that
the user has not supplied, are printed as `unavailable` with the reason —
never estimated, never interpolated. This rule is inherited from B12.

---

## 12. `linkedin-policy-safety-governor` — BUILD, SCOPED

**Prior art — substantial, and the reason this is the most carefully scoped
skill in the bundle.** Both repositories ship a precedence order, an
untrusted-content rule, an approval card, a no-fabrication rule, secrets
linting and security-boundary tests. That is roughly 40% of what Phase 2 asks
for, and it is well built.

| Phase-2 rule | Already covered upstream? | Action |
|---|---|---|
| Follow the LinkedIn User Agreement | Implied, never stated | Build — state it |
| Do not automate connection requests | No | **Build** |
| Do not automate messaging / liking / commenting / following | No — Bundle A *does* publish posts and comments after approval, by design | **Build**, for this bundle's surface |
| Do not scrape profiles or private data | Partially — Bundle A permits public post reads via Apify | **Build**, at the narrower boundary (audit §4) |
| Do not bypass CAPTCHA or security challenges | No | **Build** |
| Do not suppress warnings or evade detection | No | **Build** |
| Do not manipulate engagement / manufacture interactions | Partially — A4 refuses to claim it beats detectors | **Build** |
| No unauthorised extensions, scripts or APIs | Partially — Bundle A's Tier 2 custom poster is gated to a trusted shell env var | **Build** |
| Respect privacy and data protection | No stored data upstream, so nothing to respect | **Build** — data minimisation, export, deletion |
| Human approval before external actions | **Yes** — `approval.py` + hard rules | **Adopt**, reimplemented for this bundle's action classes |
| Audit trail of recommendations and approvals | No | **Build** |
| Stop and alert on platform restriction or security warning | No | **Build** |
| Safety controls are not obstacles to circumvent | Partially — `precedence.md` carries the spirit | **Build** — state it as a rule |

**Scope reduction applied.** The precedence order is **adapted from Bundle A's
`references/precedence.md`** rather than invented, with attribution, because a
second incompatible resolution order in the same user's toolchain would be
actively harmful. The untrusted-content rule is likewise adapted and then
**extended** to cover records about people, which Bundle A's version does not
address.

---

## 13. Capabilities deliberately not built

Requested nowhere in Phase 2, but adjacent enough that a reader should know
they were considered and rejected:

| Capability | Why not |
|---|---|
| Any LinkedIn scraper or Apify integration | Phase 2 forbids it; audit §4 |
| Any automated sender, scheduler or browser driver | Phase 2 forbids it; §12 refuses it |
| Post / comment / reply drafting | A1, A2, A3 own it |
| AI-tell removal | A4 owns it |
| Hook extraction | A5 owns it |
| Content planning | A6 (personal), B5 (Page) own it |
| Personal profile optimisation | A9 owns it |
| Company Page anything | Bundle B owns all 13 Page surfaces |
| Team advocacy programs | A10, B9 own it |
| Trend sourcing | B11 owns it |
| Proof mining from documents | B13 owns it |

A user running all three bundles gets 37 skills with one overlap of substance
(A8 → #1/#4), documented on both sides.

Build order and dependencies: `NEW_SKILLS_ROADMAP.md`.
