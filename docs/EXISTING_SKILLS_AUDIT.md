# Existing Skills Audit

What already exists, read from source rather than from a README.

Audited **2026-11-23** against:

| Repository | Commit basis | Skills | License |
|---|---|---|---|
| [`sergebulaev/linkedin-skills`](https://github.com/sergebulaev/linkedin-skills) | `--depth 1` clone, 2026-11-23 | 12 + 1 root orchestrator | MIT |
| [`chandewardnyanesh/linkedin-company-page-skills`](https://github.com/chandewardnyanesh/linkedin-company-page-skills) | `--depth 1` clone, 2026-11-23 | 13 + 1 root orchestrator | MIT |

The second repository is in scope because it is the sibling bundle for LinkedIn
**company Pages** and shares the first bundle's structure. A capability that
exists there is not "missing" just because it is absent from the first repo —
it is covered for Pages and would be duplicated work if rebuilt here for the
same surface.

Method: every `skills/*/SKILL.md` was parsed for frontmatter, headings, inputs,
outputs, hard rules and declared handoffs; `lib/`, `scripts/`, `tests/`,
`evals/` and `references/` were read in full for the first repo and inventoried
for the second. Nothing in this document is inferred from a skill name.

---

## 1. Bundle A — `sergebulaev/linkedin-skills`

### 1.1 Architecture as built

```
SKILL.md                  root router, voice rules, URN mapping, tier model
skills/<name>/SKILL.md    12 single-purpose skills
skills/<name>/references/ per-skill reference prose
references/               11 bundle-wide reference documents
lib/                      7 Python modules (thin API clients + conventions)
scripts/                  8 maintainer scripts (validators, posters, selftest)
tests/                    10 pytest modules + 6 JSON fixtures
evals/run_evals.py        agent-level graded cases
```

Storage model: **none**. State lives in two markdown files that skills read and
append to — `references/voice-profile.md` and `references/story-bank.md`. There
is no database, no record identity, no schema and no persisted history of any
person the user interacts with.

Configuration model: **none in the Phase-3 sense**. Behaviour is configured by
(a) environment variables for API credentials, and (b) markdown templates with
a `filled: no` status line. There is no YAML, no typed config and no profile
object.

Validation model: `pydantic` is not used anywhere. Validation is string and
shape assertions inside `tests/` plus four `scripts/check_*.py` linters.

### 1.2 Skill-by-skill inventory

| # | Skill | Purpose as implemented | Inputs | Outputs | Writes to LinkedIn? |
|---|---|---|---|---|---|
| A1 | `linkedin-post-writer` | Draft a post from 20 hook formulas (F1–F20) + 10 founder angles (A1–A10), goal-first selection | topic, goal, voice profile, Story Bank | post draft, formula used, approval card | Yes, via Publora after approval |
| A2 | `linkedin-comment-drafter` | Comment on a third-party post from its URL; also reshare-with-commentary | post URL or pasted text | 1–3 comment variants + reaction choice | Yes, after approval |
| A3 | `linkedin-reply-handler` | Reply to one comment, or sweep a whole thread and reply to everything worth answering | comment URL or post URL | per-comment replies, resolved `parentComment` | Yes, after approval |
| A4 | `linkedin-humanizer` | 4-pass AI-tell removal; `--mode audit` pre-publish review; `--mode profile` voice builder | any draft | rewritten draft, AI-tell score, voice profile | No |
| A5 | `linkedin-hook-extractor` | Classify a viral post against the 20 formulas, return a blank template | post URL or text | formula ID, why it worked, template | No |
| A6 | `linkedin-content-planner` | 7-day plan: pillar, format, hook type, CTA, time, daily comment targets | theme, audience, pillars | 7-day calendar + inbound-readiness check | No |
| A7 | `linkedin-thread-monitor` | Which of **the user's own comments** earned author replies; 6–24h warm window; hot/warm/cool/dormant | user's profile, Apify or paste | thread roster + follow-up routing | No |
| A8 | `linkedin-engager-analytics` | Who liked/commented on **one post**, tiered peer / aspirational / prospect / other, with outbound action lists | one post URL | engager roster, tier breakdown, one-line openers | No |
| A9 | `linkedin-profile-optimizer` | 9-component profile audit and rewrite | profile text or URL | scorecard + rewritten sections | No |
| A10 | `linkedin-employee-advocacy` | Stand up a team advocacy program: 14-day launch, governance, per-person/team/business metrics | team size, brand guidelines | playbook + ROI metric set | No |
| A11 | `linkedin-repurposer` | Rebuild external content (tweet, video, blog, newsletter) as a native post | source content | native post draft | Yes, after approval |
| A12 | `linkedin-interviewer` | Interview the user to fill the Story Bank, or turn one topic into a post spine | conversation | Story Bank entries, 5-line spine | No |

### 1.3 Shared library (`lib/`)

| Module | What it does | Reusable here? |
|---|---|---|
| `url_parser.py` | LinkedIn URL → `post_urn` + `comment_id`; handles `activity` / `share` / `ugcPost` | **Yes, conceptually** — a profile-URL normaliser is needed, but for `/in/` slugs, which this does not handle |
| `publora_client.py` | Publishing REST client | No — this bundle publishes nothing |
| `apify_client.py` | Read-side fetches: `fetch_post`, `fetch_post_comments`, `fetch_user_recent_comments`, `fetch_post_engagers` | Interface only; see §4 on the data-source boundary |
| `pixfaro_client.py` | Image generation | No |
| `approval.py` | `render_approval_card(...)` — formats a draft and stops | **Yes, pattern reused** (independently reimplemented, see ATTRIBUTION) |
| `backend_selector.py` | Picks connector / REST / custom poster / manual | Pattern only |
| `_env.py` | `.env` discovery and "token set but not loaded" diagnosis | Pattern only |

### 1.4 Safety and approval mechanisms already present

This matters most, because Phase 2 proposes a safety governor. What exists:

| Control | Where | Strength |
|---|---|---|
| Approval before publish | `lib/approval.py` + a `## Hard rules` block in every writing skill | Convention, not runtime enforcement — the module's own docstring says so |
| Fetched content is data, never instructions | `references/untrusted-content.md` + a `## Untrusted content` section in the 5 reading skills | Strong and well written |
| Conflict resolution order | `references/precedence.md` — owner's standing instruction > truth of specifics > approval gate > fetched-content-is-data > local rules > reach heuristics | Strong; genuinely good prior art |
| No invented specifics | post-writer step 0, interviewer hard rules, `evals/run_evals.py` | Enforced at eval level |
| Secrets never committed | `scripts/check_no_secrets.py` | Enforced |
| Security boundaries | `tests/test_security_boundaries.py` | Enforced at test level |
| Vulnerability policy | `SECURITY.md` | Present |
| No detector-beating claims | humanizer SKILL.md, precedence.md | Explicit refusal |

**What is absent from Bundle A's safety layer:**

1. No rule anywhere that refuses to **automate connection requests**. The
   bundle never sends invitations, so the question never arose.
2. No **audit trail**. Nothing records what was recommended, what was approved,
   by whom, or when. `precedence.md` §"Who enforces what" lists enforcement
   points; none of them persists a record.
3. No **platform-restriction detection** — no instruction on what to do when
   LinkedIn shows a security challenge, a rate warning or an account
   restriction.
4. No **CAPTCHA refusal** rule. Not needed for a bundle that never drives a
   browser; needed the moment network research is in scope.
5. No **data-protection surface**: no data minimisation statement, no subject
   export, no deletion path. There is no stored personal data to export, so
   this is consistent rather than negligent.
6. The untrusted-content rule is scoped to **content fetched about posts**, not
   to **profile records about people**.

### 1.5 Tests and evals

```
tests/test_client_behaviour.py       tests/test_publora_shapes.py
tests/test_detector_tool.py          tests/test_response_shapes.py
tests/test_eval_runner.py            tests/test_security_boundaries.py
tests/test_instruction_integrity.py  tests/test_skill_contracts.py
tests/test_mcp_read_layer.py         tests/test_text_encoding.py
tests/test_pixfaro_client.py
evals/run_evals.py                   graded agent cases, 1 model call each
```

`tests/test_instruction_integrity.py` is the notable one: it asserts that
**handoff contracts hold on both sides** — if the planner names a Story Bank
section, the writer must read it. That convention is adopted here.

---

## 2. Bundle B — `chandewardnyanesh/linkedin-company-page-skills`

Thirteen skills, all scoped to a **company Page**, not a personal network.

| # | Skill | Purpose | Overlaps a Phase-2 proposal? |
|---|---|---|---|
| B1 | `page-profile-builder` | Research website + Page, build canonical company profile, proof library, ICP, competitor set | Partially — ICP *for the company's buyers*, Page surface |
| B2 | `page-optimizer` | Audit and rewrite all Page fields | No |
| B3 | `page-post-writer` | 16 brand post formats | No |
| B4 | `authority-article-writer` | Long-form articles / newsletters | No |
| B5 | `page-content-calendar` | 30-day multi-surface plan | No |
| B6 | `page-humanizer` | De-AI + pre-publish audit for brand copy | No |
| B7 | `page-repurposer` | Atomise existing material into Page assets | No |
| B8 | `page-engagement-desk` | Inbound comments; **scores commenters against the ICP**; escalation | Partially — scoring a commenter, but on Page threads only |
| B9 | `employee-amplification` | Reshare kits, comment drafts, Notify-employees budget, Thought Leader Ad candidates | No |
| B10 | `competitor-page-analyzer` | Competitor Page cadence, pillars, white space | No |
| B11 | `trend-radar` | Category trend → ranked content opportunities | No |
| B12 | `page-performance-report` | Monthly report; **follower composition scored against the ICP**; employee vs Page reach | Partially — audience composition, Page surface |
| B13 | `page-asset-extractor` | Pattern extraction from posts; proof mining from documents | No |

### 2.1 What Bundle B contributes to the gap analysis

Three reference documents in Bundle B are prior art for the proposals:

- **`references/icp-firmographics.md`** — a filled-in-markdown ICP: account
  dimensions (industry, headcount, revenue, geography, ownership, tech,
  maturity) and a per-role table (economic buyer, champion, technical
  evaluator, blocker) with what each cares about and fears.
  This is a **single ICP, in prose, for one company's buyers.** Phase 2 asks
  for *multiple concurrent, machine-readable ICPs across eight purposes* with
  exclusion criteria and observable engagement signals. Different artefact.
- **`references/proof-library.md`** — "a draft may only state a figure that has
  an entry here." The strongest no-fabrication control in either bundle. Its
  logic is adopted directly for evidence handling.
- **`references/precedence.md`** and **`untrusted-content.md`** — same role as
  Bundle A's.

Storage model: **none**, same as Bundle A. Markdown templates with `filled: no`.
Configuration model: markdown templates. No YAML, no pydantic, no database.
`scripts/check_no_secrets.py` fails the build when a confidential template is
marked `filled: yes` — a deliberate guard against committing a filled ICP.

---

## 3. Consolidated capability inventory

What the two bundles, together, already do:

**Content production** — post drafting (A1), comments (A2), replies (A3),
repurposing (A11), articles and newsletters (B4), Page posts (B3), 30-day
planning (B5), 7-day planning (A6), hook/pattern extraction (A5, B13),
de-AI and pre-publish audit (A4, B6), trend sourcing (B11).

**Profile and Page assets** — personal profile audit (A9), Page audit (B2),
Page field rewriting (B2).

**Inbound engagement** — reply sweeps (A3), Page comment triage with ICP
scoring (B8), thread follow-up on the user's own comments (A7).

**Per-post audience reading** — engagers on one post, tiered into four
categories, with outbound action lists (A8).

**Team programs** — personal advocacy program (A10), Page amplification kits
(B9).

**Reporting** — Page monthly report with follower composition vs ICP (B12),
advocacy ROI metrics (A10).

**Raw material capture** — Story Bank interview (A12), proof mining (B13).

**Safety** — precedence order, untrusted-content rule, approval card,
no-fabrication rule, secrets linting, security boundary tests (both bundles).

## 4. The data-source boundary, as the existing bundles draw it

Bundle A's read layer calls four Apify actors against public LinkedIn content.
The bundle describes them as "no-cookies, public, no LinkedIn login required."

Phase 2 of this project states plainly: **"Do not scrape LinkedIn profiles or
automate browser interactions."** That is a narrower boundary than Bundle A's,
and this bundle holds the narrower one. Consequences, stated once here and
enforced throughout:

- This bundle ships **no LinkedIn scraper and no Apify dependency.** It reads
  what the user supplies: profile URLs they paste, CSVs they build, their own
  LinkedIn data export, their own analytics export, public company websites and
  professional directories, and official APIs where the user holds authorised
  access.
- Where a user already runs Bundle A and has engager rosters from A8 or thread
  rosters from A7, those are **user-supplied inputs** to this bundle, imported
  as CSV with source provenance recorded. This bundle does not call the actors
  itself, and it does not tell a user to go and scrape.
- Nothing here automates a LinkedIn action. Every invitation, message, follow
  and like is performed by the human, in LinkedIn's own interface.

## 5. Audit conclusions

1. Both bundles are **content-production and publishing** systems. Neither is a
   **network-intelligence and relationship-management** system.
2. Neither has persistent state about people. There is no contact record, no
   identity, no dedupe, no status, no history, no provenance and no
   verification date anywhere in either repository.
3. Neither has a typed configuration layer, a database, or pydantic validation.
   Phase 6's engineering standards describe a system neither bundle attempts.
4. The one real overlap is **A8 `linkedin-engager-analytics`**: it reads one
   post's engagers and tiers them against an implicit four-way ICP. It is a
   per-post, in-conversation report with no persistence, no configurable ICP and
   no scoring model. It is a legitimate *input* to this bundle, not a substitute
   for it.
5. The safety layer in both bundles is good prior art for *publishing* and for
   *untrusted fetched content*. It does not cover automation refusal, audit
   trails, platform-restriction handling, or personal-data minimisation — the
   four controls that matter once a system holds records about other people.

Gap-by-gap mapping: `CAPABILITY_GAP_ANALYSIS.md`.
