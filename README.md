# LinkedIn Network Intelligence Skills

**Twelve open-source Claude Agent Skills that research, score and manage a LinkedIn professional network — without scraping, automating or touching your account.**

An ICP builder, candidate discovery from authorised sources, a configurable
100-point scoring engine, engagement propensity with confidence levels, a
networking CRM, lead intelligence, connection-note drafting, relationship
cadence, content attribution and weekly funnel reporting.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-444%20passing-brightgreen.svg)](#how-do-i-verify-it-works)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-open%20standard-5A4FCF.svg)](https://code.claude.com/docs/en/skills)

📖 **[Documentation site](https://chandewardnyanesh.github.io/linkedin-network-intelligence/)** ·
❓ **[FAQ](docs/FAQ.md)** ·
🛡 **[Safety](docs/SAFETY.md)** ·
🤖 **[llms.txt](llms.txt)**

> **Not affiliated with, endorsed by, or connected to LinkedIn Corporation.**

---

## The one thing to know first

**This bundle drafts and records. It never sends.**

There is no sender, no scheduler, no scraper, no browser driver and no LinkedIn
credential anywhere in it. Every invitation, message, comment and follow is
performed by you, by hand, in LinkedIn. It does not read LinkedIn either: it
works from data you supply and from public pages.

That is the design, not a limitation to be worked around later.

## Why does it refuse to automate, when other LinkedIn tools do not?

Most LinkedIn tooling works by holding a `li_at` session cookie or driving your
logged-in browser. This bundle does neither, and the restriction is enforced in
code rather than promised in a document:

- The `SourceKind` enum that every record's provenance uses **has no member for
  a scrape or a browser run**, so a scraped record cannot be represented in the
  data model at all.
- No HTTP client — `requests`, `httpx`, `aiohttp`, `urllib3` — is imported
  anywhere in the package, and a test asserts it.
- Playwright, Selenium, Puppeteer and webdriver are not imported either, also
  asserted by test.
- Eleven prohibited rules load from configuration that **refuses to load** if
  one is removed.
- 33 prohibited request phrasings are refused by a classifier with regression
  tests — including the softened forms that arrive *after* a refusal:
  *"spread these over three days so it looks organic"*, *"how many can I send
  before I get flagged"*, *"warm up the account first"*.

## What does each skill do?

| Skill | For |
|---|---|
| [`linkedin-icp-builder`](skills/linkedin-icp-builder/SKILL.md) | Define who you are looking for, across eight purposes |
| [`linkedin-audience-intelligence`](skills/linkedin-audience-intelligence/SKILL.md) | Who your audience actually is, and the gap to who you want |
| [`linkedin-network-discovery`](skills/linkedin-network-discovery/SKILL.md) | Find candidates and build a weekly shortlist |
| [`linkedin-engagement-propensity`](skills/linkedin-engagement-propensity/SKILL.md) | Who is likely to care, with the evidence and a confidence level |
| [`linkedin-network-scoring`](skills/linkedin-network-scoring/SKILL.md) | Rank a pool on a configurable 100-point framework |
| [`linkedin-lead-intelligence`](skills/linkedin-lead-intelligence/SKILL.md) | Which contacts might become customers, as hypotheses |
| [`linkedin-connection-strategy`](skills/linkedin-connection-strategy/SKILL.md) | Invitation notes worth sending, draft-only |
| [`linkedin-network-crm`](skills/linkedin-network-crm/SKILL.md) | Records, a 13-status pipeline, history, provenance |
| [`linkedin-relationship-manager`](skills/linkedin-relationship-manager/SKILL.md) | Follow-ups worth making, repetition suppressed |
| [`linkedin-content-audience-attribution`](skills/linkedin-content-audience-attribution/SKILL.md) | Whether your posting is working, judged by who it brought in |
| [`linkedin-network-growth-analyst`](skills/linkedin-network-growth-analyst/SKILL.md) | Weekly and monthly funnel reports |
| [`linkedin-policy-safety-governor`](skills/linkedin-policy-safety-governor/SKILL.md) | The mandatory safety and compliance layer |

Plus [`linkedin-network-growth`](SKILL.md), the root workflow that orchestrates
all twelve in a twelve-step cycle, one-time or recurring weekly.

## How do I install it?

### Claude Code — as a plugin

```bash
/plugin marketplace add chandewardnyanesh/linkedin-network-intelligence
/plugin install linkedin-network-intelligence
```

### Claude Code — manually

```bash
git clone https://github.com/chandewardnyanesh/linkedin-network-intelligence.git
cp -R linkedin-network-intelligence/skills/* ~/.claude/skills/
```

### With the `skills` CLI

```bash
npx -y skills add chandewardnyanesh/linkedin-network-intelligence
```

### The Python engine (needed for scoring, storage and reporting)

```bash
cd linkedin-network-intelligence
pip install -r requirements.txt
python -m lni config-check   # what loads, and what each skill needs from you
python -m lni init           # create the store
```

Each `skills/<name>/` directory is self-contained and independently
installable — take only the ones you want. Install
`linkedin-policy-safety-governor` whatever else you take, because every other
skill routes through it.

**Other agents:** the skills are plain Markdown with YAML frontmatter following
the Agent Skills open standard, so they work in any compatible host —
claude.ai, Claude Desktop, Codex CLI, Cursor, OpenClaw and others. Full
instructions in [`docs/INSTALLATION.md`](docs/INSTALLATION.md).

## How do I get something useful in five minutes?

```bash
python -m lni config-check      # lists what each skill needs from you
python -m lni init

# Tell it who you are looking for (or let the ICP builder skill do it with you)
mkdir -p ~/.config/lni
cp config/examples/b2b-sales.yaml ~/.config/lni/local.yaml
export LNI_CONFIG_DIR=~/.config/lni

# Bring in a list you already have — an event page, a team page, a CSV
python -m lni import-candidates attendees.csv --icp business_development
python -m lni score --all
python -m lni shortlist
```

Nothing is invented on your behalf: where a value is missing, a skill asks.
More, with real output, in [`docs/USAGE_EXAMPLES.md`](docs/USAGE_EXAMPLES.md).

## What makes the output trustworthy?

Four disciplines, enforced as validators rather than documented as intentions.
They are the reason to use this instead of asking a model to guess:

1. **A component with no inputs abstains.** It scores zero and says so. It
   never scores a midpoint, because a midpoint is a guess that reads like a
   measurement.
2. **Every point carries evidence.** A scored component with no observation
   behind it cannot be constructed — the model layer rejects it.
3. **Observations and predictions are separate fields.** A confident propensity
   band with no usable observation cannot exist.
4. **A metric that cannot be sourced is `unavailable`, with the reason.** Never
   estimated, never interpolated. The setting that would allow estimation
   refuses to load.

A worked consequence: a candidate who is a perfect ICP match but has no
observable activity scores around 30 and is told *"strong ICP fit, but nothing
observed yet — the gap is in what we know, not in who they are."* A system that
scored them 70 would be more flattering and less useful.

## How do I score LinkedIn connections?

A configurable 100-point framework with six components:

| Component | Default | What it measures |
|---|---|---|
| ICP relevance | 25 | Fit against your Ideal Connection Profiles |
| Observable activity | 15 | Dated public activity inside a window |
| Meaningful engagement signals | 20 | Substantive comments and replies, not reactions |
| Content-topic alignment | 15 | Overlap with the topics you publish about |
| Professional influence | 10 | What they demonstrably do; follower count capped |
| Business opportunity | 15 | Opportunity hypotheses with public evidence |

Three weighting profiles ship — `default`, `networking_only`,
`business_development` — and weights must sum to 100 so two scores from
different profiles are never silently compared.

**Follower count is deliberately almost irrelevant.** Audience size contributes
at most 30% of the influence component — three points of a hundred on the
default profile — on a logarithmic scale, and the configuration refuses a cap
above 50%.

## Where does its data come from?

| Authorised | Refused |
|---|---|
| Profile URLs you paste | Scraped profiles or search results |
| CSVs you build | Bought lists of scraped profiles |
| Your own LinkedIn data export | Anyone else's data |
| Your own analytics export | Anyone else's analytics |
| Official APIs you are authorised for | Unofficial endpoints, session cookies |
| Public company sites, directories, publications, event listings | Private messages or analytics |
| Referrals, and what you were told | Unpublished personal contact details |

Every record carries its source and a verification date, or it cannot be
created. Full table in [`references/data-sources.md`](references/data-sources.md).

## How does it compare to other LinkedIn skills and tools?

| | Content bundles | Automation tools | **This bundle** |
|---|---|---|---|
| Writes posts and comments | Yes | Sometimes | No — routes to them |
| Sends invitations or messages | No | Yes | **No, by design** |
| Needs a session cookie or browser | No | Usually | **No** |
| Persistent CRM about people | No | Sometimes | **Yes** |
| Configurable ICPs | No | Rarely | **Yes, eight purposes** |
| Scoring with evidence and confidence | No | No | **Yes** |
| Audit trail of every decision | No | Rarely | **Yes, append-only** |
| Per-person export and deletion | n/a | Rarely | **Yes, cannot be disabled** |

It works *alongside* the others. Running this with
[`sergebulaev/linkedin-skills`](https://github.com/sergebulaev/linkedin-skills)
(content) and
[`chandewardnyanesh/linkedin-company-page-skills`](https://github.com/chandewardnyanesh/linkedin-company-page-skills)
(company Pages) gives thirty-seven skills with one overlap of substance,
documented on both sides in
[`docs/CAPABILITY_GAP_ANALYSIS.md`](docs/CAPABILITY_GAP_ANALYSIS.md).

## What are the safety rules?

Eleven prohibited rules, loaded from `config/safety.yaml`, which refuses to
load if one is removed:

`no_automated_invitations` · `no_automated_messaging` · `no_scraping` ·
`no_browser_automation` · `no_captcha_bypass` · `no_detection_evasion` ·
`no_engagement_manipulation` · `no_unauthorised_api` · `no_private_data` ·
`no_fabrication` · `no_targeting_private_individuals`

Every decision goes to an append-only audit trail. If LinkedIn flags anything
on your account, the run stops and **no workaround is offered** — not a
different tool, not a slower pace, not a second account.

Full detail, including the honest limitations of a pattern-based classifier, in
[`docs/SAFETY.md`](docs/SAFETY.md).

## What can it not do?

Stated plainly, because a tool that overclaims wastes your time:

- **It cannot find people you have no source for.** No scraping means discovery
  volume comes from a conference listing, a team page, a directory or your own
  connections export — not a LinkedIn search result set.
- **Three metrics are structurally unavailable** — profile visits, followers
  gained, content engagement from new connections — because nothing here reads
  LinkedIn. They fill from your own analytics export.
- **Per-person content attribution is unavailable.** LinkedIn does not expose
  engager identity to a third party.
- **Audience segment sizes are declared, not counted.** LinkedIn gives the
  account holder aggregate demographics, not a list of people.
- **The scoring weights are a modelling choice, not a measurement.** They order
  your attention against goals you stated; they are not a judgement of anyone.
- **No official LinkedIn API client ships.** It needs a Partner Program
  approval most users do not hold; the integration point is defined and left
  unimplemented rather than faked.

## How does it handle data about other people?

- The package ships **no personal data**. `config/profile.yaml` is blank, and a
  test enforces it.
- Fields in `privacy.never_store` — personal email, phone, home address, salary
  and others — are dropped **on import**, before anything is written.
- Every record carries a source and a verification date, or it cannot be
  created.
- Per-person export and deletion are supported and cannot be disabled:
  `python -m lni subject-export <id> --approve`,
  `python -m lni forget <id> --approve`.
- A filled `icps.yaml` or `business_services.yaml` holds your positioning and
  target accounts. Keep it in `$LNI_CONFIG_DIR`, outside the repository.

## How do I verify it works?

```bash
pip install -r requirements-dev.txt
python -m pytest              # 444 tests
python -m evals.run_evals     # 12 evaluation cases, 105 assertions
sh scripts/selftest.sh        # everything, including the secrets scan
```

Python 3.12+, pydantic for validation, SQLite by default with PostgreSQL behind
the same interface, YAML configuration. Two runtime dependencies. No API
credentials anywhere in the package, and no variable to add a LinkedIn one.

Module map and the reasoning behind each decision:
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Documentation

| Document | What is in it |
|---|---|
| [`docs/FAQ.md`](docs/FAQ.md) | 26 direct answers about automation, scraping, terms of service and what this does instead |
| [`docs/INSTALLATION.md`](docs/INSTALLATION.md) | Claude Code, other agents, PostgreSQL, troubleshooting |
| [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) | All seven config files, three worked examples |
| [`docs/USAGE_EXAMPLES.md`](docs/USAGE_EXAMPLES.md) | Per-skill and end-to-end walkthroughs with real output |
| [`docs/SAFETY.md`](docs/SAFETY.md) | Every rule, what it refuses, how it is enforced |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Modules, data models, storage, decisions |
| [`docs/EXISTING_SKILLS_AUDIT.md`](docs/EXISTING_SKILLS_AUDIT.md) | Inventory of 25 existing skills across two other bundles |
| [`docs/CAPABILITY_GAP_ANALYSIS.md`](docs/CAPABILITY_GAP_ANALYSIS.md) | Each capability against prior art, with verdicts |
| [`docs/NEW_SKILLS_ROADMAP.md`](docs/NEW_SKILLS_ROADMAP.md) | Build order, dependencies, what was deferred |
| [`docs/IMPLEMENTATION_REPORT.md`](docs/IMPLEMENTATION_REPORT.md) | Build results and the 13 defects found and fixed |
| [`ATTRIBUTION.md`](ATTRIBUTION.md) | What was adapted from the two upstream MIT bundles |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`SECURITY.md`](SECURITY.md) · [`CHANGELOG.md`](CHANGELOG.md) | — |

## Licence

MIT. See [`LICENSE`](LICENSE). Both upstream bundles are MIT too; what was
adapted from them is recorded in [`ATTRIBUTION.md`](ATTRIBUTION.md).

---

<sub>**Keywords:** LinkedIn CRM · Claude Agent Skills · Claude Code skills ·
LinkedIn networking without scraping · Ideal Connection Profile · ICP builder ·
LinkedIn lead scoring · connection request management · professional
relationship management · B2B social selling · LinkedIn outreach compliance ·
open-source LinkedIn tooling</sub>
