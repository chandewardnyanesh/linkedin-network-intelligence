# Changelog

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning is [semantic](https://semver.org/).

## [0.1.0] — 2026-11-24

First release. Twelve skills, a root workflow, and the engine behind them.

### Skills

- `linkedin-policy-safety-governor` — the mandatory safety and compliance
  layer: eleven prohibited rules, prohibited-action classification including
  softened phrasings, the approval gate, platform-restriction halts, and an
  append-only audit trail.
- `linkedin-icp-builder` — configurable ICPs across eight purposes, with
  exclusion criteria and observable engagement signals.
- `linkedin-audience-intelligence` — analytics-export analysis, topic affinity,
  audience segmentation and the gap to the desired audience.
- `linkedin-network-discovery` — candidate sourcing from authorised sources
  only, with provenance, dedupe and missing-field reporting.
- `linkedin-engagement-propensity` — propensity bands with evidence,
  confidence, and observations kept apart from predictions.
- `linkedin-network-scoring` — the configurable 100-point framework, with
  abstention, per-component evidence and a capped follower contribution.
- `linkedin-lead-intelligence` — opportunity hypotheses from public signals,
  with discovery questions and confidence capped until a conversation is
  confirmed.
- `linkedin-connection-strategy` — connection rationale and invitation drafts,
  draft-only.
- `linkedin-network-crm` — records, a thirteen-status pipeline, interaction
  history, dedupe, CSV import and export, subject export and deletion.
- `linkedin-relationship-manager` — person-level follow-up cadence with
  anti-repetition enforced in the engine.
- `linkedin-content-audience-attribution` — content to network growth, with the
  metric hierarchy kept distinct and attribution limits stated.
- `linkedin-network-growth-analyst` — weekly and monthly funnel reports, with
  unavailable metrics named rather than estimated.
- `linkedin-network-growth` (root) — the twelve-step workflow, one-time and
  recurring weekly.

### Engine

- Fourteen pydantic data models, with the bundle's disciplines enforced as
  validators rather than documented as intentions.
- Layered YAML configuration, seven files plus three worked examples, with
  seven settings that refuse to load if relaxed.
- SQLite store by default, PostgreSQL behind the same interface, schema
  version 1 with forward migration and a refusal to write to a newer store.
- A configurable scoring engine with abstention, and a propensity engine shared
  with it so engagement is graded once.
- Importers for candidate CSVs, the user's own LinkedIn `Connections.csv`
  (including its three-line preamble), and post analytics exports.
- `python -m lni` CLI: 14 commands, with `--approve` gating every export and
  deletion.

### Documentation

- Phase 1 audit of both upstream bundles, read from source rather than READMEs:
  `docs/EXISTING_SKILLS_AUDIT.md`, `docs/CAPABILITY_GAP_ANALYSIS.md`,
  `docs/NEW_SKILLS_ROADMAP.md`.
- `docs/ARCHITECTURE.md`, `docs/INSTALLATION.md`, `docs/CONFIGURATION.md`,
  `docs/SAFETY.md`, `docs/USAGE_EXAMPLES.md`.
- `ATTRIBUTION.md` — what was adapted from the two upstream MIT bundles, and
  where this bundle deliberately differs.
- Four bundle-wide references: precedence, untrusted content, data sources,
  metrics taxonomy.

### Discoverability

- `llms.txt` at the repository root and on the Pages site, following the
  llmstxt.org convention: a summary plus one annotated link per document.
- A GitHub Pages landing page (`docs/index.html`) with `SoftwareApplication`,
  `SoftwareSourceCode`, `FAQPage` and `BreadcrumbList` structured data, Open
  Graph and Twitter cards, a canonical URL, and `rel="describedby"` pointing at
  `llms.txt`.
- `docs/FAQ.md` — 26 question-shaped entries answering what people actually
  search for about LinkedIn automation, scraping and terms of service.
- `docs/robots.txt`, `docs/sitemap.xml`, `CITATION.cff`, and
  `scripts/setup-github.sh` for the repository description, topics and Pages.
- `docs/DISCOVERABILITY.md` documents every lever and the four steps that can
  only be done in the GitHub interface.

### Testing

- 444 tests across 10 modules, including 77 safety-boundary cases and an
  end-to-end walk of the twelve-step workflow.
- Twelve graded evaluation cases in `evals/`, covering the Phase-7 scenarios.
- `tests/test_instruction_integrity.py` asserts the documents and the code
  agree: cited rules, commands and files exist, handoff contracts hold on both
  sides, and no personal data or credentials ship.

### Known limitations

Documented in `README.md`. In short: no scraping means discovery volume depends
on sources you can point at; three requested metrics (profile visits, followers
gained, content engagement from new connections) are structurally unavailable
without your own analytics export; per-person content attribution is
unavailable; audience segment sizes are declared rather than counted; no
official LinkedIn API client ships.
