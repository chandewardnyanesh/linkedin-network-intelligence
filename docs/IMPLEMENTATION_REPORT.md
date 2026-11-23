# Implementation Report

**Project:** LinkedIn Network Intelligence & Relationship Growth Skills
**Version:** 0.1.0 · **Date:** 2026-11-24 · **Licence:** MIT

All results below were produced by executing the commands shown. Nothing is
reported as passing that was not run.

---

## 1. Existing skills audited

Both repositories were cloned and read from source — every
`skills/*/SKILL.md`, plus `lib/`, `scripts/`, `tests/`, `evals/` and
`references/` — rather than from READMEs.

### `sergebulaev/linkedin-skills` (MIT) — 12 skills + root orchestrator

`linkedin-post-writer` · `linkedin-comment-drafter` · `linkedin-reply-handler` ·
`linkedin-humanizer` · `linkedin-hook-extractor` · `linkedin-content-planner` ·
`linkedin-thread-monitor` · `linkedin-engager-analytics` ·
`linkedin-profile-optimizer` · `linkedin-employee-advocacy` ·
`linkedin-repurposer` · `linkedin-interviewer`

Also inventoried: 7 `lib/` modules, 8 maintainer scripts, 10 pytest modules,
11 bundle-wide references, and the agent-graded eval runner.

### `chandewardnyanesh/linkedin-company-page-skills` (MIT) — 13 skills + root

`page-profile-builder` · `page-optimizer` · `page-post-writer` ·
`authority-article-writer` · `page-content-calendar` · `page-humanizer` ·
`page-repurposer` · `page-engagement-desk` · `employee-amplification` ·
`competitor-page-analyzer` · `trend-radar` · `page-performance-report` ·
`page-asset-extractor`

Included in scope because it is the sibling bundle for company Pages: a
capability covered there is not "missing" because it is absent from the first
repository.

**25 existing skills audited in total.** Full inventory:
`docs/EXISTING_SKILLS_AUDIT.md`.

### The three findings that shaped this build

1. Both bundles are **content-production and publishing** systems. Neither is a
   network-intelligence or relationship-management system.
2. **Neither persists anything about people.** No contact record, identity,
   dedupe, status, history, provenance or verification date exists in either
   repository. State is two markdown files.
3. Neither has typed configuration, a database, or pydantic. The safety layer
   in both is good prior art for *publishing* and for *untrusted fetched
   content*, and covers none of: automation refusal, audit trails,
   platform-restriction handling, or personal-data minimisation.

---

## 2. New skills created — 12, plus the root workflow

| Skill | Scope verdict |
|---|---|
| `linkedin-policy-safety-governor` | BUILD, SCOPED — ~40% prior art; precedence and untrusted-content rules adapted with attribution, 13 of 14 required controls newly built |
| `linkedin-icp-builder` | BUILD |
| `linkedin-audience-intelligence` | BUILD, SCOPED — does not fetch engagers; imports an A8 roster instead |
| `linkedin-network-discovery` | BUILD |
| `linkedin-engagement-propensity` | BUILD, SCOPED — shares one engine with scoring |
| `linkedin-network-scoring` | BUILD |
| `linkedin-lead-intelligence` | BUILD |
| `linkedin-connection-strategy` | BUILD, SCOPED — cites upstream voice rules rather than carrying a copy |
| `linkedin-network-crm` | BUILD |
| `linkedin-relationship-manager` | BUILD, SCOPED — routes thread-level follow-up upstream |
| `linkedin-content-audience-attribution` | BUILD, SCOPED — adopts the Page report's honest-attribution discipline |
| `linkedin-network-growth-analyst` | BUILD, SCOPED — consumes the CRM, computes nothing it cannot source |
| `linkedin-network-growth` (root) | The twelve-step workflow |

Each has: description, trigger conditions, required inputs, workflow, output
format, failure handling, safety requirements and examples. Validated by
`scripts/check_frontmatter.py` and by `tests/test_instruction_integrity.py`.

---

## 3. Skills excluded or reduced due to overlap

**Nothing was excluded outright. Five were reduced in scope**, which removed
roughly a third of what a literal reading of Phase 2 would have produced.

| Capability | Why not rebuilt | Owner |
|---|---|---|
| Per-post engager pull and tiering | Substantially implemented | `linkedin-engager-analytics` (upstream) |
| Comment-thread follow-up, warm window | Substantially implemented | `linkedin-thread-monitor`, `linkedin-reply-handler` (upstream) |
| Post, comment and reply drafting | Substantially implemented | `linkedin-post-writer`, `-comment-drafter`, `-reply-handler` |
| AI-tell removal, voice profile | Substantially implemented | `linkedin-humanizer` |
| Hook and pattern extraction | Substantially implemented | `linkedin-hook-extractor`, `page-asset-extractor` |
| Content planning | Substantially implemented | `linkedin-content-planner`, `page-content-calendar` |
| Personal profile optimisation | Substantially implemented | `linkedin-profile-optimizer` |
| All 13 company-Page surfaces | Substantially implemented | the company-page bundle |
| Team advocacy programmes | Substantially implemented | `linkedin-employee-advocacy`, `employee-amplification` |
| Category trend sourcing | Substantially implemented | `trend-radar` |
| Proof mining from documents | Substantially implemented | `page-asset-extractor` |

A user running all three bundles gets 37 skills with one overlap of substance
(`linkedin-engager-analytics` → audience intelligence and propensity),
documented on both sides. Verdict-by-verdict reasoning:
`docs/CAPABILITY_GAP_ANALYSIS.md`.

---

## 4. Files created — 81 tracked

| Area | Count | Notes |
|---|---|---|
| Skills | 13 | 12 + root `SKILL.md` |
| Python modules | 17 | `lni/` 15, `evals/` 2 |
| Tests | 10 | `tests/` |
| Configuration | 10 | 7 files + 3 worked examples |
| Documentation | 16 | README, 9 `docs/`, ATTRIBUTION, CONTRIBUTING, SECURITY, CHANGELOG |
| References | 4 | precedence, untrusted content, data sources, metrics taxonomy |
| Scripts | 3 | frontmatter, secrets, selftest |
| Packaging | 6 | pyproject, requirements ×2, plugin.json, .env.example, .gitignore |
| Evals | 2 | 12 cases + runner |
| Licence | 1 | MIT |

Roughly 10,200 lines of Python, 4,900 of Markdown, 1,150 of YAML.

---

## 5. Tests passed and failed

Executed 2026-11-24 on Python 3.13.18, pydantic 2.13.5, pytest 9.1.1.

```
$ python -m pytest tests/
444 passed
```

| Module | What it covers |
|---|---|
| `test_models.py` | Every model invariant: identity, evidence, abstention, status machine, drafts, opportunities, metrics |
| `test_config.py` | Layering, ICP merge-by-key, all three examples, the seven unrelaxable settings, `missing_for` |
| `test_safety_boundaries.py` | 33 prohibited phrasings, 14 allowed ones, halts and resume, the audit trail, configuration integrity |
| `test_crm_and_dedupe.py` | Normalisation, dedupe policy, the full funnel path, privacy filtering, subject export and deletion |
| `test_scoring_and_propensity.py` | Abstention, per-point evidence, the follower cap, exclusion, bands, confidence, ranking |
| `test_leads_attribution_reporting.py` | Signal source restriction, disqualifiers, sufficiency floors, unavailable metrics |
| `test_importers.py` | Header aliases, privacy filtering, number and date formats, LinkedIn's CSV preamble |
| `test_instruction_integrity.py` | Documents and code agree; no personal data or credentials ship |
| `test_integration.py` | The twelve-step workflow end to end, plus every CLI command |
| `test_discoverability.py` | The SEO artefacts: `llms.txt` links resolve, the sitemap lists real pages, the structured data parses and matches the rendered FAQ, declared versions agree across four files |

```
$ python -m evals.run_evals --quiet
12/12 cases passed, 105 assertions executed
```

All twelve Phase-7 scenarios: E01 relevant vs irrelevant · E02 real vs
superficial engagement · E03 overlapping ICPs · E04 missing information ·
E05 duplicates · E06 unverified claims · E07 weak business relevance ·
E08 privacy-sensitive information · E09 unauthorised sources · E10 automation
requests · E11 CAPTCHA circumvention · E12 account restriction.

```
$ sh scripts/selftest.sh
13 documents valid (12 skills + root)
no credentials, no personal data, profile.yaml is blank
configuration loads
423 passed
12/12 cases passed, 105 assertions executed
```

**Currently failing: none.**

### Defects found and fixed during the build

Recorded because they are the part of a build report usually left out.

| # | Defect | Found by |
|---|---|---|
| 1 | Two class constants leaked into pydantic model fields | smoke test |
| 2 | A zero score with confidence `none` violated its own model invariant on save | CLI integration run |
| 3 | `candidate_id_for` ignored company normalisation, so "Acme Ltd" and "Acme" were two people | `test_crm_and_dedupe.py` |
| 4 | The near-duplicate scan matched on given name, so "Jonathan"/"Jonathon" was missed — the exact case it exists for | `test_crm_and_dedupe.py` |
| 5 | `untouched_since(days=0)` fell through a falsy check to the 365-day default | `test_crm_and_dedupe.py` |
| 6 | `find_duplicates` silently dropped auto-mergeable pairs instead of reporting them | `test_crm_and_dedupe.py` |
| 7 | Regex alternation ordering meant "automatically" never matched (`automat(e|…|ically)`) | classifier probe |
| 8 | "send me the list" was classified as bulk sending | classifier probe |
| 9 | Three platform-restriction phrasings were not detected, including "account has been restricted" | `test_safety_boundaries.py` |
| 10 | Lead categories matched on generic words, so one inventory signal fired the demand-planning category | `test_leads_…py` |
| 11 | Unverifiable exclusion criteria were documented as surfaced for the human but never actually surfaced | `test_scoring_…py` |
| 12 | A strong-fit, no-evidence candidate got a "verify the basics" message naming fields it already had | `test_scoring_…py` |
| 13 | **A network-graph harvest ("pull everyone with X in my 2nd degree") was not classified as scraping** | `evals/run_evals.py` E09 |

Defect 13 is the one worth noting: it is the commonest way the request arrives
from someone who would never use the word "scrape", and the eval suite caught
what 417 unit tests had not. Four patterns were added and six regression cases
now cover it.

---

## 6. Security and compliance limitations

### What is enforced, and how

| Control | Enforcement |
|---|---|
| No sender, scheduler, scraper or browser driver | None exists. Tests assert Playwright, Selenium, Puppeteer and webdriver are not imported, and that no HTTP client is imported in `lni/` |
| No LinkedIn credential | None exists, and no environment variable to add one |
| Data-source boundary | `SourceKind` has no member for a scrape or a browser run, so such a record cannot be represented |
| 11 prohibited rules | `config/safety.yaml` refuses to load if one is removed |
| Approval before an external action | `SafetyGovernor.check`, `--approve` on every export and deletion |
| Audit trail | Append-only; `lni/audit.py` exposes no update or delete, asserted by test |
| No record without a source | `Candidate.sources` minimum length 1; the setting cannot be disabled |
| No score without evidence | `ComponentScore` validator |
| No confident band without an observation | `PropensityAssessment` validator |
| No invented metric | `FunnelMetrics` optionality; `estimate_missing_metrics` cannot be enabled |
| No pitch on a first touch | `InvitationDraft` validator |
| Four user-confirmed-only statuses | `StatusChange` validator |
| Subject export and deletion | Cannot be disabled; `PrivacySettings` validator |

### Honest limitations

1. **The classifier is patterns, not comprehension.** It catches 33 tested
   phrasings and many more, and defect 13 shows that a wording nobody
   anticipated can pass it. The prohibited list is the authority, not the regex.
2. **It governs this bundle only.** It cannot stop a user opening a scraper
   elsewhere.
3. **It cannot verify sources.** If a user says a CSV is their own export, that
   is recorded. The provenance field records what they said.
4. **Three requested metrics are structurally unavailable** — profile visits,
   followers gained, content engagement from new connections — because nothing
   here reads LinkedIn. Reported as `unavailable` with the reason; filled from
   the user's own analytics export.
5. **Per-person content attribution is unavailable.** LinkedIn does not expose
   engager identity to this bundle.
6. **Audience segment sizes are declared, not counted.** LinkedIn gives the
   account holder aggregate demographics, not a list of people. The output says
   which.
7. **No official LinkedIn API client ships.** It requires a Partner Program
   approval most users do not hold. The integration point is defined
   (`SourceKind.official_api`, authorisation mandatory on the record) and left
   unimplemented rather than faked.
8. **Discovery volume depends on sources the user can point at.** No scraping
   means a conference listing, a team page, a directory or their own
   connections export — not a search result set. Stated in the skill rather
   than left for the user to discover.
9. **Platform terms change.** The rules encode behaviours, not clause numbers,
   and `safety.platform_terms.user_must_review` is `true` because reading the
   current terms is the user's to do.
10. **PostgreSQL is implemented but untested against a live server** in this
    build: the paramstyle translation and connection path are in place and the
    test suite runs against SQLite. Flagged as a remaining task rather than
    claimed.

### Not affiliated with LinkedIn

Stated in the root `SKILL.md`, `README.md`, `ATTRIBUTION.md` and
`.claude-plugin/plugin.json`, and asserted by test. "LinkedIn" is used only to
describe what the software is for.

---

## 7. Installation

```bash
git clone <repository-url>
cd linkedin-network-intelligence
pip install -r requirements.txt
python -m lni config-check        # what loads, and what each skill needs
python -m lni init                # create the store
```

For Claude Code, either add the repository as a plugin (it ships
`.claude-plugin/plugin.json`) or copy `skills/*` into `~/.claude/skills/`.
Each skill directory is independently installable; install
`linkedin-policy-safety-governor` whatever else you take, because every other
skill routes through it.

Keep a filled configuration outside the repository:

```bash
mkdir -p ~/.config/lni
cp config/examples/b2b-sales.yaml ~/.config/lni/local.yaml
export LNI_CONFIG_DIR=~/.config/lni
```

Importing into another compatible agent, and the PostgreSQL backend:
`docs/INSTALLATION.md`.

---

## 8. Remaining development tasks

| Priority | Task |
|---|---|
| High | Verify the PostgreSQL backend against a live server; add a CI job that runs the suite on both backends |
| High | Keep extending the prohibited-phrasing corpus. Defect 13 proves the method works and that the corpus is incomplete |
| Medium | A migration test that creates a v1 store, bumps `SCHEMA_VERSION`, and asserts the forward path — currently only the refusal to write to a newer store is tested |
| Medium | `normalise_name` and `normalise_company` handle Latin scripts and a list of legal suffixes. Both are incomplete for CJK, Arabic and Cyrillic names |
| Medium | A GitHub Actions workflow running `scripts/selftest.sh` on 3.12 and 3.13 |
| Medium | An agent-level eval harness that grades the 12 rubrics with a model call, kept separate from the deterministic runner so the two results are never conflated |
| Low | An official LinkedIn API adapter, for users who hold Partner Program access |
| Low | Importers for more analytics export shapes as LinkedIn changes them |
| Low | A `--json` flag on more CLI commands; only `report` has one |
| Low | Published packaging (PyPI) and a plugin marketplace entry |

### Deliberately not planned

An automated sender, a scheduler, a scraper, a browser driver, or any pacing
logic. These are not missing features; their absence is the product.
