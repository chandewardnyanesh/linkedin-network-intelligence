---
name: linkedin-network-growth
description: "Master workflow for LinkedIn network intelligence and relationship growth. Orchestrates twelve skills end to end: understand the objective, analyse audience and content analytics, build or update ICPs, discover relevant professionals from authorised sources, score and classify them, produce a prioritised shortlist, prepare personalised invitation drafts, present them for human review, let the user act in LinkedIn, record confirmed outcomes, track meaningful engagement, and report weekly. Runs one-time or as a recurring weekly research cycle. Use when the user wants to grow or work their LinkedIn network systematically, asks who to connect with, wants a weekly research cycle, or asks whether their networking is working. Drafts everything, sends nothing."
license: MIT
metadata:
  author: Dnyanesh Chandewar
  bundle: linkedin-network-intelligence
  version: 0.1.0
---

# LinkedIn Network Growth

A bundle of twelve skills for turning LinkedIn from a feed into a researched
network. Built for Claude Code and the Agent Skills open standard.

**Not affiliated with, endorsed by, or connected to LinkedIn Corporation.**

## The one thing to know first

This bundle **drafts and records. It never sends.** There is no sender, no
scheduler and no browser driver anywhere in it. Every invitation, message,
comment and follow is performed by the user, by hand, in LinkedIn. That is not
a limitation worked around later; it is the design, and
`linkedin-policy-safety-governor` enforces it.

It also does not read LinkedIn. Everything it knows comes from what the user
supplies or from public pages. See `references/data-sources.md`.

## When to use which skill

| Want to… | Skill |
|---|---|
| Define who you are looking for | `linkedin-icp-builder` |
| Know who your audience actually is | `linkedin-audience-intelligence` |
| Find candidates and build a shortlist | `linkedin-network-discovery` |
| Judge who is likely to care | `linkedin-engagement-propensity` |
| Rank a pool | `linkedin-network-scoring` |
| Spot commercial opportunities | `linkedin-lead-intelligence` |
| Write invitation notes | `linkedin-connection-strategy` |
| Store and track everything | `linkedin-network-crm` |
| Keep relationships alive after the connection | `linkedin-relationship-manager` |
| Connect content to network growth | `linkedin-content-audience-attribution` |
| Get a weekly or monthly report | `linkedin-network-growth-analyst` |
| Decide whether something is allowed | `linkedin-policy-safety-governor` |

## The twelve-step workflow

Run in order. Steps 1 to 3 are setup and happen once; 4 to 12 are the cycle.

| # | Step | Skill | Output |
|---|---|---|---|
| 1 | Understand the profile and objectives | this skill | `config/profile.yaml` filled, or the questions asked |
| 2 | Analyse available audience and content analytics | `linkedin-audience-intelligence` | Segments, topic affinity, the audience gap |
| 3 | Build or update ICP definitions | `linkedin-icp-builder` | `config/icps.yaml`, falsifiable |
| 4 | Discover relevant professionals | `linkedin-network-discovery` | Candidate records with provenance |
| 5 | Score and classify | `linkedin-network-scoring` + `linkedin-engagement-propensity` + `linkedin-lead-intelligence` | Scores, bands, opportunity hypotheses |
| 6 | Produce a prioritised shortlist | `linkedin-network-discovery` | Ranked list, trimmed to the user's own capacity |
| 7 | Prepare personalised invitation drafts | `linkedin-connection-strategy` | Drafts, rationale, conversation topics |
| 8 | Present for human review | this skill | A review card, with the profile URLs in order |
| 9 | **The user acts in LinkedIn** | — | Nothing automated happens here, ever |
| 10 | Record confirmed outcomes | `linkedin-network-crm` | Status changes, user-confirmed |
| 11 | Track meaningful engagement | `linkedin-relationship-manager` | Follow-ups worth making, repetition suppressed |
| 12 | Report | `linkedin-network-growth-analyst` | Weekly or monthly funnel, with the gaps labelled |

Step 9 is the load-bearing one. The workflow is built around a human doing the
acting, which is why steps 8 and 10 exist at all.

## Starting from nothing

```bash
python -m lni config-check      # what loads, and what each skill still needs
python -m lni init              # create the store
```

`config-check` ends with a list of the skills that will ask you for something.
That list is the setup task. Nothing is invented on your behalf: a skill with a
missing input asks a question.

The bundle works with no personal configuration at all, on sensible defaults —
one generic ICP, the balanced scoring profile, the full safety layer. It will
just be broad until the ICPs are narrowed.

## One-time or weekly

**One-time research.** `workflow.one_time_research_target` defaults to 25.
Right for trying the bundle, or for a single list — a conference attendee page,
a team page, a set of URLs. Run steps 4 to 8 and stop.

**Recurring weekly.** `workflow.weekly_research_target` defaults to 100. The
cycle is steps 4 to 12, once a week, with step 2 revisited monthly and step 3
revisited when the objective changes.

> **100 researched candidates does not mean 100 invitations.**
>
> Researching is reading. Inviting is the user's own action at whatever rate
> they choose. This bundle has no view on how many invitations are safe to
> send; it does not model, pace or schedule around platform limits, and a
> request to help time outreach to avoid detection is refused under
> `no_detection_evasion`.
>
> If you tell it your own weekly capacity in `config/profile.yaml`, the
> shortlist is trimmed to it — as a courtesy to your week, not as a limit
> calculation.

## Configuration

Seven files in `config/`, layered over `default.yaml`, with
`$LNI_CONFIG_DIR/*.yaml` on top for a filled copy kept outside the repository.
Three worked examples ship in `config/examples/`: a personal brand, a B2B
seller, and a technology professional networking non-commercially.

Full reference: `docs/CONFIGURATION.md`.

**Keep a filled configuration out of a public repository.** A filled
`icps.yaml` or `business_services.yaml` holds your positioning, your target
accounts and your pricing posture.

## What makes the output trustworthy

Four disciplines, enforced in code rather than documented as intentions. They
are the reason to use this rather than asking a model to guess:

1. **A component with no inputs abstains.** It scores zero and says so. It
   never scores a midpoint, because a midpoint is a guess that reads like a
   measurement.
2. **Every point carries evidence.** A scored component with no observation
   behind it cannot be constructed; the model layer rejects it.
3. **Observations and predictions are separate fields.** A confident propensity
   band with no usable observation cannot exist.
4. **A metric that cannot be sourced is `unavailable`, with the reason.** Never
   estimated, never interpolated, never carried forward.
   `reporting.estimate_missing_metrics` cannot be enabled.

## Relationship to the other two bundles

Three bundles, 37 skills, one real overlap.

| Bundle | Surface | Owns |
|---|---|---|
| [`sergebulaev/linkedin-skills`](https://github.com/sergebulaev/linkedin-skills) | Personal profile, content | Posts, comments, replies, hooks, humanising, content planning, profile optimisation, per-post engagers, thread follow-up |
| [`chandewardnyanesh/linkedin-company-page-skills`](https://github.com/chandewardnyanesh/linkedin-company-page-skills) | Company Page | Page content, articles, newsletters, Page audits, employee amplification, competitor Pages, trends, Page reporting |
| **this one** | Personal network | ICPs, discovery, scoring, propensity, CRM, leads, connection strategy, relationships, attribution, reporting, safety |

This bundle writes no content and optimises no profile. Where the work is
content, it routes to the other two. Where it needs voice rules or an AI-tell
pass on a draft note, it cites the upstream bundle's own voice-rules reference
and its `linkedin-humanizer` rather than carrying a second copy.

The overlap is `linkedin-engager-analytics` upstream: a per-post engager pull
with a four-way tier. Its roster is a valid **input** here when the user
exports one. Documented on both sides in `docs/CAPABILITY_GAP_ANALYSIS.md`.

## Safety, in one paragraph

Eleven prohibited rules, loaded from `config/safety.yaml`, which refuses to
load if one is removed: no automated invitations, messaging, liking, commenting
or following; no scraping; no browser automation; no CAPTCHA bypass; no
detection evasion; no engagement manipulation; no unauthorised APIs; no private
data; no fabrication; no records about private individuals. Every decision is
written to an append-only audit trail. If LinkedIn flags anything on the
account, the run stops and no workaround is offered. Safety controls here are
not obstacles to work around, and a request to disable one is itself refused
and recorded. Full detail: `docs/SAFETY.md`.

## Engineering

Python 3.12+, pydantic for validation, SQLite by default with PostgreSQL
behind the same interface, YAML configuration, JSON output, no API credentials
anywhere in the package. `docs/ARCHITECTURE.md` for the module map,
`docs/INSTALLATION.md` to install.

## Resources

- `docs/INSTALLATION.md`, `docs/CONFIGURATION.md`, `docs/USAGE_EXAMPLES.md`
- `docs/SAFETY.md`, `docs/ARCHITECTURE.md`
- `docs/EXISTING_SKILLS_AUDIT.md`, `docs/CAPABILITY_GAP_ANALYSIS.md`,
  `docs/NEW_SKILLS_ROADMAP.md`
- `references/precedence.md`, `references/untrusted-content.md`,
  `references/data-sources.md`, `references/metrics-taxonomy.md`
- `ATTRIBUTION.md` — what is adapted from the two upstream MIT bundles
