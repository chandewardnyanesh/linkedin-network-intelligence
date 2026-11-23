# Usage examples

Real commands and real output shapes. Nothing here is aspirational; every
command is exercised by `tests/test_integration.py`.

## Setup, once

```bash
$ python -m lni config-check
Configuration loads. Layers: 7
  config/default.yaml
  config/profile.yaml
  …

Scoring profile: default
  icp_relevance              25.0
  observable_activity        15.0
  engagement_signals         20.0
  topic_alignment            15.0
  professional_influence     10.0
  business_opportunity       15.0

Active ICPs: 1
  professional_networking      priority 2  [NO exclusions or signals yet]

Service categories usable: 0
Safety rules loaded: 11
Storage: sqlite

Skills that will ask you for something first:
  linkedin-audience-intelligence
      needs profile.content_topics
      needs audience_plan.exports
      needs audience_plan.desired_audience
  linkedin-icp-builder
      needs profile.primary_objective
  …
```

That last block is the setup task. Nothing is invented on your behalf.

```bash
$ python -m lni missing linkedin-lead-intelligence
linkedin-lead-intelligence needs 2 thing(s). Ask, do not assume:

- business_services.categories
    Which service categories should a lead be classified against? Each needs
    observable signals, or it cannot classify anything.

- profile.services_offered
    What do you offer, if anything? Leave it empty if the networking is not
    commercial — lead intelligence will then correctly report nothing.
```

## A weekly research cycle, end to end

### 1. Import from an authorised source

```bash
$ python -m lni --extra-config ~/.config/lni/local.yaml \
    import-candidates summit-attendees.csv --icp business_development
94 row(s) read from summit-attendees.csv; 91 candidate(s) parsed; 3 row(s) skipped;
2 row(s) with a warning; fields dropped by the privacy filter: Personal Email, Phone
created 71, updated 20, unchanged 0
  warning row 12: unreadable profile URL 'linkedin/in/x'; record kept without one,
    identity falls back to name and company
  skipped row 29: no name and no profile URL

3 possible duplicate(s) for you to resolve — not merged:
  cand_1e42a0ed… ~ cand_9b7c3f21…  [probable 0.94]  near-identical name at the same company
```

Near matches are reported, never merged. A wrong automatic merge destroys a
record and is invisible afterwards.

### 2. Score

```bash
$ python -m lni --extra-config ~/.config/lni/local.yaml score --all
91 candidate(s) scored with profile 'business_development'

   78.40  priority_1   medium   Dana Whitfield
   61.00  priority_2   medium   Sam Okoye
   34.00  monitor      low      Maya Quiet [3 abstained]
    0.00  excluded     low      Rory Reseller

Note: components with no inputs abstain and score zero. A low total on many
abstentions describes the record, not the person.
```

### 3. Read the shortlist

```bash
$ python -m lni shortlist
Shortlist (25 of a possible 25):

  [priority_1 ] Dana Whitfield — VP Operations @ Northfield Foods
      https://linkedin.com/in/dana-whitfield
      next: shortlist now. Prepare a connection recommendation and an invitation
      draft for your review. Warm — comment substantively on one more post first.
  …

You said your own weekly capacity is 15. The top 15 are the ones to work through;
the rest keep.

Nothing here has been sent. Invitations are yours to send in LinkedIn.
```

### 4. Act, then record what you actually did

```bash
$ python -m lni status cand_6956b9d9b7b0dc0e manually_invited
Not recorded: status 'manually_invited' asserts something that happened on
LinkedIn; it may only be set from the user's own confirmation

$ python -m lni status cand_6956b9d9b7b0dc0e manually_invited --confirmed
cand_6956b9d9b7b0dc0e: invitation_prepared -> manually_invited (your confirmation recorded)
```

### 5. Report

```bash
$ python -m lni report --period weekly
# Weekly report — 2026-11-17 to 2026-11-23

## Funnel
profiles_researched                        91
qualified_candidates                       34
invitations_manually_sent                   9
invitations_accepted                        4
acceptance_rate                          0.44
relevant_connections_gained                 3
meaningful_interactions                     6
discovery_meetings                          1
business_opportunities                      2
profile_visits                    unavailable
followers_gained                  unavailable
content_engagement_from_new_connections  unavailable

## Unavailable, and why
profile_visits:
      LinkedIn reports profile visits only inside the account's own analytics.
      Supply an analytics export and this is filled.
…

## Recommended
  - strategic_partnerships has produced 14 researched, 2 invited, 0 accepted
    across three weeks. Either the ICP is wrong or the notes are; the sample is
    now big enough to be worth deciding rather than continuing.
  - 34 candidates are sitting at qualified. The shortlist is the bottleneck, not
    the research — work the queue down before adding to it.

## What this cannot attribute
  - Every figure here comes from records you confirmed. Nothing is read from
    LinkedIn, so the funnel is only as complete as what you told me.
  - Acceptance is attributed to the invitation, which is the only link this store
    holds. In practice a profile view, a comment you left weeks earlier, or a
    mutual connection may have done the work.
```

## Per-skill examples

### `linkedin-icp-builder`

> **You:** I want to meet more people in AI who actually build things.

The skill proposes `ai_technology_networking` and `professional_networking`,
then pushes until "actually build things" becomes checkable:

```yaml
observable_engagement_signals:
  - has published an incident write-up, a paper, or a technical talk
  - comments technically rather than congratulating
  - maintains or contributes to something others use
exclusion_criteria:
  - posts vendor marketing rather than their own work
  - no technical writing or talks of their own anywhere public
```

> `ai_technology_networking` is falsifiable: it has exclusions and signals.

### `linkedin-engagement-propensity`

> **You:** Dana commented properly on two of my posts and replied to me last week.

```
## Dana Whitfield — engagement propensity
Band: high            Confidence: medium        Window: 180 days

### Observed
- substantive comment on 2026-11-20: three paragraphs on monthly stock counts
      source: your own notifications · confidence medium
- reply to your comment on 2026-11-15

### Predicted
- Estimated engagement propensity high (normalised 0.61) from 2 signals inside
  the 180-day window.

### Approach
Warm. Comment substantively on one more post first, then connect referencing
that exchange.
```

> **You:** What's the propensity for these 40 from the attendee list?

All 40 return `insufficient_evidence`, reported once: nobody on the list has
engaged with anything, so the question to answer is ICP fit, and the
invitations will have to carry their own weight.

### `linkedin-network-scoring` — the useful disagreement

> **You:** Why is Maya only 34? She's exactly who I want.

```
### Maya Quiet — 34.0 / 100 · 3 components abstained
  icp_relevance           30.0 / 30   high     fit 1.00 against 'business_development'
  observable_activity      4.0 / 12   medium   1 activity record, none inside 90 days
  engagement_signals      ABSTAIN              no engagement signal inside the window
  topic_alignment         ABSTAIN              nothing known about what she engages with
  professional_influence  ABSTAIN              no influence facts supplied
  business_opportunity    ABSTAIN              no opportunity assessment on record

  Strong ICP fit, but nothing observed yet — the gap is in what we know, not in
  who they are. Engage on their work for a few weeks, or verify their recent
  activity, then re-score. Do not spend an invitation on a record this thin.
```

The fit is perfect; the evidence is absent. A system that scored her 70 would
be more flattering and less useful.

### `linkedin-connection-strategy`

> **You:** Draft notes for all 25 on the shortlist.

> 6 have a checkable reason to connect. 19 do not. I have drafted the 6. For
> the other 19 the honest next step is engagement — a generic note is worse
> than no note, because the one chance is spent.

### `linkedin-lead-intelligence`

> **You:** Work out which of these 30 companies has budget approved this quarter.

> **Not doing that** — `no_private_data`. Budget is not observable from an
> authorised source, and a guess presented as intelligence is what loses a deal
> on the first call. Here is what *is* visible — two companies with public
> postings implying the work — and the discovery questions that would find out.

### `linkedin-relationship-manager`

```
## Follow-ups worth making — week of 2026-11-23

Suppressed from this list: 14 contacts touched in the last 21 days, and 3 who
have not replied to two previous touches. Neither group appears until something
changes.

### 1. Dana Whitfield — last exchange 38 days ago
**Why now:** in October she said the count reconciliation was unsolved. You have
since worked through exactly that at another site.
**If no reply:** leave it. This is touch two; there is no touch three.

### Nothing to say (7)
7 contacts are inside the window with no event, nothing resolved and nothing to
offer. A message to any of them would be a message about nothing.
```

The "nothing to say" section is what stops the skill manufacturing reasons to
message people.

## Refusals, and what comes instead

```bash
$ python -m lni safety-check "automate the connection requests for the whole list"
outcome: refused
rule: no_automated_invitations

**Not doing that** — `no_automated_invitations`.

Never send, queue, schedule or pace LinkedIn connection requests.

Invitations are drafted and handed to the user, who sends them by hand in
LinkedIn. The bundle ships no sender and no scheduler, and it will not produce a
file, script or format whose purpose is to feed one.

What triggered it: "automate the connection requests".

**What I can do instead:** I can prepare the invitation drafts and a review list
with the profile URLs in order. You send them in LinkedIn; tell me which went out
and I will record them as manually_invited.
```

```bash
$ python -m lni safety-check "spread these over three days so it looks organic"
outcome: refused
rule: no_detection_evasion
```

```bash
$ python -m lni safety-check "draft the invitations so I can send them myself"
outcome: allowed
```

## Data subject requests

```bash
$ python -m lni forget cand_6956b9d9b7b0dc0e
Not deleted: deleting records needs your explicit go-ahead first

$ python -m lni forget cand_6956b9d9b7b0dc0e --approve
deleted: {'relationship_events': 2, 'status_changes': 6, 'invitation_drafts': 1,
'recommendations': 1, 'propensity': 1, 'scores': 1, 'candidates': 1}
The audit line recording this deletion is kept. It holds no profile fields and it
is the only proof the deletion happened.
```

```bash
$ python -m lni subject-export cand_6956b9d9b7b0dc0e --approve -o dana.json
written to dana.json
```

## Audit

```bash
$ python -m lni audit --summary
{
  "lines": 243,
  "by_decision": { "allowed": 228, "approved": 4, "refused": 9, "requires_approval": 2 },
  "refusals_by_rule": {
    "no_automated_invitations": 4,
    "no_detection_evasion": 3,
    "no_scraping": 2
  }
}
```

## Running a weekly cycle on a schedule

The bundle has no scheduler of its own, deliberately — a scheduler is one step
from a sender. If you want the research side to run weekly, drive the CLI from
whatever you already use (cron, a task runner, your agent's own scheduling),
and keep the human steps human:

```bash
#!/bin/sh
# Research and score. Steps 7 to 11 need you.
set -e
export LNI_CONFIG_DIR="$HOME/.config/lni"
python -m lni import-candidates "$1" --icp business_development
python -m lni score --all
python -m lni shortlist > "$HOME/lni-shortlist-$(date +%F).txt"
python -m lni report --period weekly > "$HOME/lni-report-$(date +%F).md"
```

What this never does: send anything, pace anything, or decide on your behalf
which of the shortlist deserves an invitation.
