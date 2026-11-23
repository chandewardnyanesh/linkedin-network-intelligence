---
name: linkedin-network-scoring
description: "Rank potential connections on a configurable 100-point framework: ICP relevance 25, observable activity 15, meaningful engagement signals 20, content-topic alignment 15, professional influence 10, business opportunity 15. Returns the total, each component with its evidence and confidence, a priority class and a recommended next action. Weights are configurable per profile. A component with no inputs abstains rather than scoring a midpoint, and follower count is capped so audience size can never decide a ranking. Use when a candidate pool needs ordering, or when the user asks who is worth the effort."
license: MIT
metadata:
  author: Dnyanesh Chandewar
  bundle: linkedin-network-intelligence
  version: 0.1.0
---

# LinkedIn Network Scoring

Orders a pool so the user's review time goes to the right twenty-five people.

## When to use

- After discovery, before shortlisting.
- Re-scoring when new evidence arrives, or after the ICPs change.
- The user asks who on a list matters most.

## Required inputs

At least one active ICP. Everything else is optional, and every absence makes a
component abstain rather than guess.

| Component | Default | Needs |
|---|---|---|
| `icp_relevance` | 25 | An active ICP and some known fields on the candidate |
| `observable_activity` | 15 | Dated public activity inside 90 days |
| `engagement_signals` | 20 | Observed signals; delegated to `linkedin-engagement-propensity` |
| `topic_alignment` | 15 | `profile.content_topics` plus something known about the candidate's topics |
| `professional_influence` | 10 | Demonstrated signals; followers optional and capped |
| `business_opportunity` | 15 | An opportunity assessment with usable signals |

## Workflow

1. Safety check the request.
2. `python -m lni config-check` to confirm which weights profile is active.
3. `python -m lni score --all` or score named candidates.
4. Read the abstentions before reading the totals. A score with four
   abstentions describes the record, not the person.
5. Present ranked by priority class, then total.
6. Hand the top of the list to `linkedin-connection-strategy`.

## Abstention, which is the whole design

A component with no inputs **scores zero and says it abstained**. It never
scores a midpoint. A midpoint is a guess that reads like a measurement, and it
is the easiest way for a scoring system to become fiction.

Consequences the user should hear, once:

- A thin record scores low. That is the record's fault, not the person's, and
  the output says so.
- Above `max_abstentions_before_low_confidence` (default 2), the result is
  reported as low confidence whatever the total, and the candidate cannot be
  promoted above `monitor`.
- The next action for a high-fit, no-evidence candidate is "engage and
  re-score", not "invite".

## Follower count

Audience size contributes at most `follower_subscore_cap` (default 0.3) of the
influence component — three points of a hundred on the default profile — on a
log scale. Five hundred followers and fifty thousand differ by less, there,
than one published talk does. The configuration refuses a cap above 0.5.

What counts as influence instead: publishes regularly on the topic, speaks at
industry events, maintains or contributes to something others use, is cited by
others in the field, holds a role with visible decision scope.

## Exclusion beats score

A candidate matching an ICP exclusion criterion is `excluded`, whatever the
arithmetic says, and the criterion is recorded verbatim so the user can see
which rule fired and disagree with it.

Literal, specific criteria are checked automatically. A criterion that is a
judgement — "sells a competing service" — cannot be checked from a record and
is surfaced for the human rather than guessed at.

## Priority classes

| Class | Default threshold | Means |
|---|---|---|
| `priority_1` | 70, confidence medium+ | Shortlist now |
| `priority_2` | 55, confidence low+ | Shortlist if there is room; one engagement touch first |
| `priority_3` | 40 | Keep in the pool, engage, re-score |
| `monitor` | 0 | Not enough evidence to spend an invitation on |
| `excluded` | — | An ICP criterion fired |

Ranking is by class first, then total: a confident 58 outranks a
barely-supported 64.

## Weights profiles

Three ship. `default` is balanced; `networking_only` zeroes business
opportunity and moves the points to fit and engagement; `business_development`
puts 30 on opportunity and 3 on influence. Weights must sum to 100 — the
configuration refuses anything else, so two scores from different profiles are
never silently compared. The profile is recorded on every score.

## Output format

```
## Scored 71 candidates · profile `business_development`

 76.3  priority_1   medium   Dana Whitfield        VP Operations @ Northfield Foods
 61.0  priority_2   medium   Sam Okoye             Director of Supply Chain @ Westmark
 34.0  monitor      low      Maya Quiet            Plant Manager @ Harborline     [3 abstained]
  0.0  excluded     —        Rory Reseller         excluded: "the person is a consultant or reseller"

### Dana Whitfield — 76.3 / 100
  icp_relevance           25.0 / 25   high     fit 1.00 against `business_development`
       title "VP Operations" vs ICP titles · industry "Food and beverage manufacturing"
  observable_activity      8.0 / 15   high     2 observable actions inside 90 days
  engagement_signals      14.4 / 20   medium   propensity high (normalised 0.72)
  topic_alignment          5.0 / 15   medium   1 overlap with your content topics
  professional_influence   2.1 /  3   medium   2 demonstrated signals plus a capped audience contribution
  business_opportunity    21.8 / 30   medium   opportunity relevance 72/100

  Next: shortlist now. Prepare a connection recommendation and an invitation
  draft for your review. Warm — comment substantively on one more post first.

### Maya Quiet — 34.0 / 100 · 3 components abstained
  Strong ICP fit, but nothing observed yet — the gap is in what we know, not in
  who they are. Engage for a few weeks, or verify recent activity, then
  re-score. Do not spend an invitation on a record this thin.
```

Always show the abstentions. A total without them is a number without its
error bars.

## Failure handling

- **No active ICP:** `icp_relevance` abstains, which removes a quarter of the
  scale. Stop and hand to `linkedin-icp-builder` rather than reporting scores
  out of 75 as though they were out of 100.
- **Everything abstains:** say so. "Nothing to score yet" is the answer, and
  the fix is evidence, not a different weighting.
- **A score contradicts the user's instinct:** show the components. Either the
  evidence is missing, which is fixable, or the ICP is wrong, which is more
  interesting.
- **The user asks to weight followers higher:** the cap refuses above 0.5. Say
  why: audience size is the most available signal and the least informative.
- **Weights that do not sum to 100:** refused by the configuration, with the
  reason.

## Safety requirements

- Every point is traceable to an observation. The model layer rejects a scored
  component with no evidence.
- No component infers a protected characteristic, and no ICP may be defined by
  one.
- Scores are never presented as a judgement of a person's worth. They order the
  user's own attention against the user's own stated goals, and the output says
  what it was built from.

## Examples

**The useful disagreement**

> User: Why is Maya only 34? She's exactly who I want.

Show the components: ICP fit 25/25, everything else abstained. The score is
low because the record is empty, not because the fit is poor. The action is to
gather evidence, not to override the number.

**The fix that is not a fix**

> User: Can we just not abstain, and score the middle instead?

No. A midpoint would put Maya at 55 and she would be indistinguishable from a
candidate with real evidence at 55. The abstention is the information.

## Related

- `linkedin-icp-builder`, `linkedin-engagement-propensity`,
  `linkedin-lead-intelligence` supply the inputs.
- `linkedin-network-crm` stores the result.
- `lni/scoring.py`, `config/scoring.yaml`
