---
name: linkedin-engagement-propensity
description: "Estimate which professionals are most likely to find the user's content relevant and engage meaningfully, from observed evidence only: historical engagement the user supplies, comment quality, recent public activity, shared professional interests and topic relevance. Returns a propensity band, the evidence behind it, a confidence level, and a relationship-building approach, with observations and predictions kept in separate fields. Never fabricates engagement history and never claims access to private analytics. Use when deciding who to engage before inviting, or who on a list is worth the effort."
license: MIT
metadata:
  author: Dnyanesh Chandewar
  bundle: linkedin-network-intelligence
  version: 0.1.0
---

# LinkedIn Engagement Propensity

How likely is this person to care? The answer is a prediction, and the output
is built so it cannot be mistaken for an observation.

## When to use

- Sequencing a shortlist: who to engage with first, who to leave.
- Deciding whether someone is a warm approach or a cold one.
- The user asks "is it worth connecting with this person?"

Not for the aggregate score (`linkedin-network-scoring`, which calls this for
its engagement component — one engine, not two), and not for tracking replies
to the user's own comments, which the personal-profile bundle's
`linkedin-thread-monitor` already owns.

## Required inputs

Each signal needs three things, and all three are mandatory:

| Part | Why |
|---|---|
| What was observed | "commented three paragraphs on the stock-count post", not "is engaged" |
| When | Signals outside `recency_window_days` (default 180) contribute nothing |
| Where it came from | The user's own notifications, their analytics export, a public page |

Signal kinds, strongest first: `substantive_comment`, `reply_to_user`,
`repeat_engagement`, `share_with_commentary`, `short_comment`, `reaction_only`.

A reaction is weighted at a tenth of a substantive comment, and the
configuration refuses to weight it higher. A like is not a relationship.

## Workflow

1. Safety check the request.
2. Check `profile.content_topics` is set. Without it, topic relevance cannot
   contribute — ask rather than proceeding silently.
3. Ask the user what they have actually seen. Do not ask them to go and collect
   it from LinkedIn at scale, and do not offer to collect it.
4. Grade the evidence. Recency decays linearly to zero at the window edge; the
   total saturates, so a long tail of reactions never adds up to a strong
   signal.
5. Report the band, the observations, the predictions, the confidence and the
   approach — in that order, with the labels intact.

## The bands

| Band | Meaning |
|---|---|
| `very_high` | Already engaging repeatedly and substantively |
| `high` | Real signal, recent |
| `moderate` | Some signal, thin or ageing |
| `low` | Barely anything |
| `very_low` | Present but negligible |
| `insufficient_evidence` | Nothing inside the window. **Not a failure** — it says this is a cold approach |

`insufficient_evidence` is the honest default and will be the commonest result.
A confident band with no usable observation cannot be constructed: the model
layer rejects it.

## Confidence

Driven by three things: how many distinct signals, how recent, and whether the
user saw them first-hand.

- `high` — three or more live signals, at least two strong, at least one
  first-hand.
- `medium` — two or more live signals, with a strong one or two distinct kinds.
- `low` — anything else that is still inside the window.
- `none` — nothing inside the window.

## Output format

```
## Dana Whitfield — engagement propensity

Band: high            Confidence: medium        Window: 180 days

### Observed
- substantive comment on 2026-11-20: three paragraphs on monthly stock counts
      source: your own notifications · confidence medium
- reply to your comment on 2026-11-15
      source: your own notifications · confidence medium

### Predicted
- Estimated engagement propensity high (normalised 0.61) from 2 signals inside
  the 180-day window.
- 1 older signal excluded as outside the window.

### Approach
Warm. Comment substantively on one more post first, then connect referencing
that exchange. Two touches before the invitation is the difference between a
note that reads as earned and one that reads as a template.
```

The two headings are not decoration. **Observed** is what someone saw.
**Predicted** is what this engine thinks follows. Never merge them, never move
a prediction up into the observed list, and never present the band as a fact
about the person.

## Failure handling

- **No signals at all:** return `insufficient_evidence` with confidence `none`
  and say what that means for the approach. Do not pad with inference from the
  person's title or follower count.
- **All signals stale:** same band, with the count of excluded signals stated.
- **The user asks you to find the engagement history:** refuse. Cite
  `no_scraping`. Ask what they have seen in their own notifications or export.
- **The user offers a figure from a tool that scraped it:** do not record it.
  Say that a scraped figure has no authorised provenance and cannot be used as
  evidence here.
- **The user says "they seem keen":** that is a note, not a signal. Record it
  as a user-supplied note at low confidence, and say that it carries no weight
  in the band.

## Safety requirements

- `no_fabrication` is the governing rule. Never invent an engagement, a date, a
  comment or a history, and never imply access to analytics this bundle cannot
  see.
- Never claim to know what the person's own analytics show.
- Never present a propensity band as a statement about the person's intentions.
  It is an estimate from a handful of public actions.
- A propensity band never produces a pitch. No band's recommended approach
  opens with the user's own offer.

## Examples

**Warm, with evidence**

> User: Dana commented properly on two of my posts and replied to me last week.

Band `high`, confidence `medium`, approach: one more substantive comment, then
connect referencing the exchange.

**Cold, and said so**

> User: What's the propensity for these 40 from the attendee list?

All 40 return `insufficient_evidence`. Report that once, plainly, rather than
40 times: nobody on the list has engaged with anything, so the question to
answer is ICP fit, and the invitations will have to carry their own weight.

## Related

- `linkedin-network-scoring` calls this engine for its engagement component.
- `linkedin-connection-strategy` uses the approach to sequence the first touch.
- `lni/propensity.py`, `config/scoring.yaml` → `engagement_signals`
