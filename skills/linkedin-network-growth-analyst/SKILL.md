---
name: linkedin-network-growth-analyst
description: "Generate weekly and monthly networking performance reports: profiles researched, qualified candidates, candidates by ICP, invitations manually sent and accepted, acceptance rate, relevant connections gained, meaningful interactions, qualified leads, discovery meetings and business opportunities, with per-ICP performance and recommended improvements. Any metric that cannot be sourced is reported as unavailable with the reason rather than estimated. Use when the user wants a weekly or monthly review, asks whether their networking is working, or needs the funnel from research through to opportunity."
license: MIT
metadata:
  author: Dnyanesh Chandewar
  bundle: linkedin-network-intelligence
  version: 0.1.0
---

# LinkedIn Network Growth Analyst

The funnel, computed from what the user confirmed, with the gaps labelled.

## When to use

- End of a week or a month.
- "Is any of this working?"
- Comparing ICPs: which audience actually converts.
- Deciding whether to change the approach or the targeting.

## Required inputs

The CRM. Everything is computed from status changes the user confirmed and
interactions they logged, plus any analytics export they supply.

At least one active ICP, for the per-ICP breakdown.

## Workflow

1. Safety check the request.
2. `python -m lni report --period weekly` or `--period monthly`.
3. Read the `unavailable` block before the numbers. It says what the report
   cannot see.
4. Present the funnel, the per-ICP breakdown, the audience quality notes, the
   recommendations, and the limits.
5. Agree one change with the user, not five.

## The funnel

| Metric | Source |
|---|---|
| Profiles researched | Candidates created in the window |
| Qualified candidates | Transitions to `qualified` |
| Candidates by ICP | Primary ICP of candidates created |
| Invitations manually sent | Transitions to `manually_invited`, **user-confirmed** |
| Invitations accepted | Transitions to `accepted`, **user-confirmed** |
| Acceptance rate | Derived. `unavailable` when no invitations were sent |
| Relevant connections gained | Acceptances whose primary ICP is still active |
| Meaningful interactions | Logged interactions marked substantive |
| Qualified leads | Transitions to `potential_lead` |
| Discovery meetings | Logged interactions on the meeting or call channel |
| Business opportunities | Opportunities created or updated in the window |

## Three metrics that are structurally unavailable

Phase 2 asks for profile visits, followers gained, and content engagement from
new connections. Nothing in this bundle reads LinkedIn, so all three are
reported as unavailable with the reason, and filled only from the user's own
export:

- **Profile visits** — in the account's own analytics, not in this store.
- **Followers gained** — likewise.
- **Content engagement from new connections** — needs engager identity joined
  to connection dates. LinkedIn does not expose engager identity here. An
  engager roster the user exported themselves fills it.

This is the design, not a limitation to work around. A report that invented
these would be worse than one that names them.

## Never invent a metric

`reporting.estimate_missing_metrics` cannot be enabled; the configuration
refuses to load with it on. In practice:

- No invitations sent means **no acceptance rate**, not 0%. A rate from a zero
  denominator is a fabricated figure.
- No logged interactions means **meeting count unavailable**, not zero. An
  empty log reads as unknown.
- A missing month in a series stays missing. A gap is information.

A reader should never have to guess whether a blank means zero.

## Output format

```
# Weekly report — 2026-11-17 to 2026-11-23

## Funnel
profiles_researched                        71
qualified_candidates                       34
invitations_manually_sent                   9
invitations_accepted                        4
acceptance_rate                          0.44
relevant_connections_gained                 3
meaningful_interactions                     6
qualified_leads                             1
discovery_meetings                          1
business_opportunities                      2
profile_visits                    unavailable
followers_gained                  unavailable
content_engagement_from_new…      unavailable

## By ICP
business_development            52
strategic_partnerships          14
professional_networking          5

## Per-ICP performance
                        researched  invited  accepted  rate   opportunities
business_development            52        7         4   0.57              2
strategic_partnerships          14        2         0   0.00              0
professional_networking          5        0         0  unavailable         0

## Unavailable, and why
profile_visits:
    LinkedIn reports profile visits only inside the account's own analytics.
    Supply an analytics export and this is filled.
…

## Audience quality
- 96 records: discovered 41, qualified 34, manually_invited 9, accepted 12
- 11 of 12 accepted or engaged connections carry an active ICP classification
- 23 records have never been verified or are past the 180-day staleness window

## Recommended
- strategic_partnerships has produced 14 researched, 2 invited, 0 accepted
  across three weeks. Either the ICP is wrong or the notes are; the sample is
  now big enough to be worth deciding rather than continuing.
- 34 candidates are sitting at qualified. The shortlist is the bottleneck, not
  the research — work the queue down before adding to it.

## What this cannot attribute
- Every figure comes from records you confirmed. Nothing is read from
  LinkedIn, so the funnel is only as complete as what you told me.
- Acceptance is attributed to the invitation, which is the only link this
  store holds. A profile view, a comment weeks earlier, or a mutual
  connection may have done the work.
```

## Reading the report honestly

- **A low acceptance rate is usually a note problem, not a targeting problem.**
  If the ICP fit is high and acceptances are low, the notes are generic. Check
  the drafts that were declined before changing the ICP.
- **Acceptances without conversations are a list, not a network.** If
  meaningful interactions are near zero while acceptances climb, the funnel is
  working and the relationship-building is not.
- **Research volume is the easiest number to move and the least important.**
  A hundred researched with nine invited and no conversations is a worse week
  than twenty researched with three real exchanges.
- **Per-ICP comparison is the most useful panel on the page.** It is the one
  that tells the user to stop doing something.

## Failure handling

- **Empty store:** say so. "Nothing to report yet" with the reason, not a page
  of zeros that look like failure.
- **No invitations recorded:** say that the funnel below the invitation stage is
  blank until the user tells you what they sent. Offer to record it.
- **No ICPs active:** the per-ICP panel is omitted, with the reason.
- **The user asks for a benchmark:** this bundle reports against the user's own
  baseline only. Industry acceptance-rate figures circulating online are other
  people's corpora, usually unsourced, and comparing to them produces a
  decision based on a stranger's data.
- **A metric the user expects is unavailable:** say which export would fill it.

## Safety requirements

- `no_fabrication` governs this skill more than any other, because a
  performance report is where an invented figure survives longest. Nothing is
  estimated, interpolated or carried forward.
- Figures come only from user-confirmed statuses and logged interactions.
- The report contains no instruction to increase sending, and no pacing
  guidance. If volume is the question, it is answered against the user's own
  stated capacity.

## Examples

**The finding worth having**

> User: Weekly report please.

Four acceptances, six interactions, one meeting. The useful line is
`strategic_partnerships`: three weeks, no acceptances, and a decision now
worth making.

**The comparison to refuse**

> User: Is 44% a good acceptance rate?

Against what? Report their own trend across the last four weeks instead, and
say that unsourced benchmarks are someone else's corpus.

## Related

- `linkedin-network-crm` supplies every figure.
- `linkedin-content-audience-attribution` connects content to this funnel.
- Company Page equivalent: `page-performance-report` in the company-page bundle.
- `lni/reporting.py`
