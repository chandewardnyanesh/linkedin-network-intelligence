# Architecture

## Layout

```
SKILL.md                      the root workflow, linkedin-network-growth
skills/<name>/SKILL.md        12 single-purpose skills
references/                   4 bundle-wide reference documents
config/                       7 YAML files + 3 worked examples
lni/                          13 Python modules
tests/                        10 pytest modules, 444 tests
evals/                        12 graded evaluation cases
docs/                         9 documents
```

## Modules

| Module | Owns | Depends on |
|---|---|---|
| `models.py` | All 14 data models, identity, normalisation, the status graph | — |
| `config.py` | Layering, validation, `missing_for` | models |
| `db.py` | Schema, migrations, SQLite and PostgreSQL, subject rights | config |
| `audit.py` | The append-only trail | db, config, models |
| `safety.py` | Classification, decisions, the approval gate, halts | config, models |
| `provenance.py` | Source constructors, staleness, verification reports | config, models |
| `dedupe.py` | Comparison and duplicate policy | models |
| `crm.py` | Records, merging, status transitions, history, filtering | db, audit, safety, dedupe, models |
| `propensity.py` | Evidence grading, bands, confidence, approach | config, models |
| `scoring.py` | ICP fit, six components, priority classes | propensity, config, models |
| `leads.py` | Opportunity classification | config, models |
| `attribution.py` | Topic affinity, audience gap, attribution limits | config, models |
| `reporting.py` | Funnel computation, period reports | crm, config, models |
| `importers.py` / `exporters.py` | The whole input and output surface | config, models, provenance |
| `cli.py` | One entry point for every skill to call | all |

A rule that two skills need lives in one module and is cited by both.
`lni/scoring.py` imports `lni/propensity.py` for its engagement component
rather than scoring engagement a second time — one engine, two skills, no
drift. `tests/test_instruction_integrity.py` asserts the handoff holds on both
sides, a convention adopted from the upstream bundle.

## The fourteen data models

All in `models.py`, all pydantic, `extra="forbid"` throughout.

| # | Model | Note |
|---|---|---|
| 1 | `UserProfile` | Every field optional; a missing one makes a skill ask |
| 2 | `ICPDefinition` | Several coexist; an active one with no positive criteria does not validate |
| 3 | `AudienceSegment` | A size requires a stated basis |
| 4 | `Candidate` | Id derived from the normalised profile URL; `sources` cannot be empty |
| 5 | `CandidateScore` + `ComponentScore` | Total must equal its components; a scored component needs evidence |
| 6 | `SourceProvenance` | No member for a scrape; `official_api` requires an authorisation note |
| 7 | `ConnectionRecommendation` | Needs shared or profile context, or it does not validate |
| 8 | `InvitationDraft` | Over the character limit is rejected, not truncated; a pitch is rejected |
| 9 | `StatusChange` | Illegal transitions rejected; four statuses require user confirmation |
| 10 | `RelationshipEvent` | Cannot be dated in the future |
| 11 | `BusinessOpportunity` | Stages past `signal_observed` require user confirmation |
| 12 | `ContentAnalytics` | Every metric optional; `None` means the export did not carry it |
| 13 | `PeriodReport` + `FunnelMetrics` | `unavailable` carries the reason per metric |
| 14 | `AuditEntry` | A refusal cannot be written without citing a rule |

Plus `Evidence` and `PropensityAssessment`, which carry the two disciplines
that matter most: `Evidence.observed` rejects predictive language, and
`PropensityAssessment` rejects a confident band with no usable observation.

## Storage

Each table carries **indexed scalar columns for what we filter and sort on,
plus a `payload` column holding the full validated model as JSON.**

The reasoning: pydantic stays the single definition of every record's shape, so
a schema change is a model change and cannot drift from what the code
validates. The scalar columns exist because `WHERE crm_status = ? AND relevance
> ?` has to be a query rather than a full-table rehydrate.

Trade-off accepted: querying *inside* evidence or components means rehydrating.
At the sizes this bundle works in — a weekly run is 100 records — that is the
right side of the trade.

`audit_log` has no `UPDATE` or `DELETE` path in the repository layer.

PostgreSQL support is a paramstyle translation and a different connection in
`open_database`; every repository method is identical.

## The scoring engine

Six components, weights from configuration, evidence on every point.

```
ScoringInput ─┬─ icp_relevance          (ICP fit, or the exclusion that fired)
              ├─ observable_activity    (dated public activity in a window)
              ├─ engagement_signals  ──→ lni/propensity.py
              ├─ topic_alignment        (needs profile.content_topics)
              ├─ professional_influence (demonstrated signals; followers capped)
              └─ business_opportunity   (needs usable signals, not a number)
                         ↓
              CandidateScore: total, components, priority, confidence, action
```

Three invariants:

1. **Abstention.** No inputs means zero points and `abstained=True`. Never a
   midpoint. A midpoint is a guess that reads like a measurement, and it is the
   easiest route from a scoring system to fiction.
2. **Evidence.** `ComponentScore` rejects points above zero with no evidence.
3. **Follower cap.** Audience size contributes at most
   `follower_subscore_cap` of the influence component, log-scaled, and cannot
   move a candidate between priority classes.

Exclusion beats score. A literal, specific criterion present in the record
excludes automatically; a judgement criterion is **surfaced for the human**
rather than guessed from keyword overlap — because a silent wrong exclusion is
the failure nobody notices.

## Decisions worth recording

**Why no scraper.** The specification forbids it. The consequence is real:
discovery volume comes from sources the user can point at rather than from a
search result set, and `linkedin-network-discovery` says so rather than letting
a user wonder why they are not getting a thousand records a week.

**Why abstention rather than imputation.** A midpoint for a missing component
makes a thin record indistinguishable from an evidenced one at the same total.
The abstention count *is* the information.

**Why `None` rather than `0`.** A reader should never have to guess whether a
blank means zero. An acceptance rate from zero invitations is not 0%, it is
unavailable.

**Why user-confirmed-only statuses.** Four statuses assert something that
happened on LinkedIn, which this bundle cannot see. Recording them from
inference would make the funnel fiction.

**Why conservative merging.** A wrong automatic merge destroys a record and is
invisible afterwards. A duplicate the user can see is the cheaper mistake. So
exact identity merges; anything less is reported.

**Why the audit trail survives deletion.** It holds no profile fields and it is
the only proof the deletion happened.

**Why the configuration refuses to relax controls.** A setting that can be
turned off is a control that will be, in the session where it is inconvenient.
Seven settings refuse rather than silently weakening the output.

**Why pydantic rather than dataclasses.** Most of the disciplines in this
bundle are expressible as validators, which means they are enforced at
construction rather than at review. "A score with no evidence cannot be built"
is a stronger guarantee than "do not build a score with no evidence".

## Integration points left unimplemented

**Official LinkedIn API.** `SourceKind.official_api` exists, requires an
authorisation note on the record, and is accepted throughout. No client ships,
because the Partner Program approval is something most users do not hold, and a
faked client would be worse than an honest gap. To add one: construct
`Candidate` records with `provenance.official_api(name, authorisation)` and the
rest of the bundle works unchanged.

**Engager rosters.** `SourceKind.upstream_skill_export` accepts a roster the
user exported from another tool, with provenance recorded. This is the
documented route for interoperating with the upstream bundle's per-post engager
analytics without this bundle calling any scraper itself.

## Testing

| File | Covers |
|---|---|
| `test_models.py` | Every model invariant |
| `test_config.py` | Layering, validation, the seven unrelaxable settings, `missing_for` |
| `test_safety_boundaries.py` | 29 prohibited phrasings, 12 allowed ones, halts, the audit, config integrity |
| `test_crm_and_dedupe.py` | Normalisation, dedupe policy, the status machine, privacy, subject rights |
| `test_scoring_and_propensity.py` | Abstention, evidence, the follower cap, exclusion, bands, confidence |
| `test_leads_attribution_reporting.py` | Signal sources, disqualifiers, sufficiency floors, unavailable metrics |
| `test_importers.py` | Header aliases, privacy filtering, number and date formats, LinkedIn's preamble |
| `test_instruction_integrity.py` | Do the documents and the code agree; no personal data or credentials ship |
| `test_integration.py` | The twelve-step workflow end to end, and the CLI |
| `test_discoverability.py` | `llms.txt` links resolve, the sitemap lists real pages, the JSON-LD parses and its FAQ matches the rendered page, declared versions agree |

`test_instruction_integrity.py` is the one worth copying into another project:
it asserts that every rule id quoted in prose is a rule the configuration
loads, every CLI command cited exists in the parser, every cited file is
present, and every handoff contract holds on both sides.
