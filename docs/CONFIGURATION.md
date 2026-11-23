# Configuration

Seven files in `config/`, layered, with your own filled copy kept outside the
repository.

## Layer order

Lowest precedence first:

1. `config/default.yaml` — behaviour. Ships with the package, no personal data.
2. `config/{profile,audience,icps,business_services,scoring,safety}.yaml` — the
   blanks only you can fill.
3. every `*.yaml` in `$LNI_CONFIG_DIR`, alphabetically.
4. an explicit `overrides` mapping, for tests and scripts.

Mappings merge key by key. Lists replace wholesale, **except** `icps` and
`business_services.categories`, which merge by `key` — so you can redefine one
ICP without restating the other seven.

```bash
mkdir -p ~/.config/lni
export LNI_CONFIG_DIR=~/.config/lni
cp config/examples/b2b-sales.yaml ~/.config/lni/local.yaml
python -m lni config-check
```

## Keep a filled configuration out of the repository

A filled `icps.yaml` holds your positioning, your target accounts and your
exclusion judgements. A filled `business_services.yaml` holds what you sell and
how you qualify. Both are commercially sensitive, and `.gitignore` covers the
obvious filenames — but the reliable answer is to keep them in
`$LNI_CONFIG_DIR`, outside the repository entirely.

`config/profile.yaml` ships blank and a test enforces that it stays blank.

## The files

### `profile.yaml` — who you are

Every field is `null`. A skill that needs one asks; nothing is invented.

| Field | Notes |
|---|---|
| `display_name`, `headline`, `profile_url` | Invitation drafts need the name |
| `primary_objective` | One sentence. Decides which ICPs matter and what a good candidate looks like |
| `secondary_objectives` | A list |
| `industry`, `geography`, `languages` | |
| `content_topics` | **Load-bearing.** What you publish about. Without it the topic-alignment component abstains for every candidate |
| `services_offered` | Drives lead intelligence. Leave empty if the networking is not commercial |
| `weekly_research_target` | Default 100. A research target, not an invitation target |
| `weekly_invitation_capacity` | **Your own capacity**, not a platform limit. The shortlist is trimmed to it as a courtesy. Leave `null` for no trimming |

### `icps.yaml` — who you are looking for

Several ICPs coexist across eight purposes. One ships active and generic; the
other seven are inactive templates.

Two fields do most of the work, and both ship empty because only you can fill
them:

- **`exclusion_criteria`** — what disqualifies someone. This is what stops a
  discovery run returning recruiters, resellers and bulk connectors. A literal,
  specific phrase is checked automatically; a judgement ("sells a competing
  service") is surfaced for you to check by hand rather than guessed at.
- **`observable_engagement_signals`** — what someone in this audience visibly
  does, each checkable from an authorised source. Without these, the engagement
  components abstain, and the ICP is a wish list rather than a profile.

An ICP with neither is reported as not falsifiable by `config-check`. An active
ICP with no positive criteria does not load at all: it would match everyone who
is not excluded.

Other fields: `job_titles`, `title_exclusions`, `seniority`, `industries`,
`company_size_bands`, `geographies`, `professional_interests`,
`content_interests`, `business_relevance`, `priority` (1 is highest, breaks
ties).

**ICPs may not be defined by a protected characteristic.** Use role, seniority,
industry, interest and geography.

### `audience.yaml` — your audience, and the one you want

`current_segments` is filled by `linkedin-audience-intelligence` from your own
analytics export. `desired_audience` is the thing only you can state, as ICP
keys with a `target_share`; the gap between the two is the skill's main output.
`unwanted_audience` records who you would rather not attract —
in practice the most useful field on the page.

Target shares must reference a defined ICP and cannot sum above 1.0.

### `business_services.yaml` — what you can help with

Ships with no categories, which means lead intelligence correctly reports
nothing. Each category needs `observable_signals` or it cannot classify
anything.

A signal must be publicly visible or something you were told. It may never be
an inference about budget, contracts, internal systems or intent to buy.

`max_confidence_without_user_confirmation` defaults to `medium` and cannot be
set to `high`: high confidence in purchasing intent without a confirmed
conversation is a fabricated claim.

### `scoring.yaml` — the engine

Three profiles ship:

| Profile | ICP | Activity | Engagement | Topics | Influence | Opportunity |
|---|---|---|---|---|---|---|
| `default` | 25 | 15 | 20 | 15 | 10 | 15 |
| `networking_only` | 32 | 18 | 25 | 20 | 5 | 0 |
| `business_development` | 30 | 12 | 15 | 10 | 3 | 30 |

Weights must sum to 100, so two scores from different profiles are never
silently compared. The profile is recorded on every score.

`priority_bands` map a score to a priority class, evaluated top down, and must
descend to a `min_total` of 0 so every scored candidate lands in exactly one
band.

`professional_influence.follower_subscore_cap` defaults to 0.3 and is refused
above 0.5. Audience size is the most available signal and the least
informative.

`engagement_signals` weights the kinds of engagement. A reaction cannot be
weighted at or above a substantive comment.

`max_abstentions_before_low_confidence` defaults to 2: above it, the result is
low confidence whatever the total and the candidate cannot be promoted above
`monitor`.

### `safety.yaml` — the rules

Eleven prohibited rules. Removing one makes the configuration invalid, not
permissive. Also here: the approval list, the authorised source kinds, the
platform-restriction policy, audit settings and data-protection settings. Full
detail in `SAFETY.md`.

### `default.yaml` — behaviour

Storage, workflow targets, relationship cadence, audience floors, reporting,
provenance staleness, privacy, output.

## Settings that cannot be relaxed

Seven. Each refuses to load rather than silently weakening the output, and each
error says why:

| Setting | Why it is fixed |
|---|---|
| `reporting.estimate_missing_metrics` | An estimated metric in a performance report is a fabricated one |
| `output.separate_observations_from_predictions` | A prediction printed as an observation is the failure this bundle exists to avoid |
| `provenance.require_source_on_every_record` | A record with no source cannot be re-checked or corrected |
| `privacy.support_subject_export` / `support_subject_deletion` | A store of records about people must be able to produce and remove what it holds about one of them |
| `safety.audit.enabled` / `log_refusals` | An unrecorded refusal cannot be reviewed |
| `workflow.invitation_capacity_is_the_users_own` | The bundle does not model or pace platform limits |
| `safety.platform_restrictions.on_warning_or_restriction` | `stop_and_alert` is the only legal value; anything else is a workaround |

## The three examples

| Example | Shape |
|---|---|
| `personal-brand.yaml` | A practitioner building reach inside one audience. `networking_only` weights, no service categories, an `unwanted_audience` entry that does the real work |
| `b2b-sales.yaml` | A founder-seller. `business_development` weights, two filled service categories with observable signals and discovery questions, raised priority thresholds |
| `technology-professional.yaml` | Non-commercial networking. Opportunity scoring switched off entirely, so lead intelligence correctly reports nothing |

Copy one, replace everything, run `config-check`.

## Diagnosing

```bash
python -m lni config-check             # what loaded, what each skill needs
python -m lni missing <skill-name>     # the questions to ask, verbatim
```

`missing` returns config paths paired with the question to ask the user. Skills
use it so they ask the same way every time instead of improvising — and so they
ask rather than assume.
