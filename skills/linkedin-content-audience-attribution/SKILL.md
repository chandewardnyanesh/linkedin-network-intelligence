---
name: linkedin-content-audience-attribution
description: "Connect content performance to professional network growth: which posts attracted relevant professionals, how engagement differs by audience segment, how followers and connections grew against what was published, and which themes performed. Distinguishes impressions, reactions, comments, shares and followers from actual business outcomes, and states plainly what the data cannot attribute. Use when the user asks whether their posting is working, which posts brought the right people, or wants to connect content to pipeline."
license: MIT
metadata:
  author: Dnyanesh Chandewar
  bundle: linkedin-network-intelligence
  version: 0.1.0
---

# LinkedIn Content Audience Attribution

Whether the posting is working — judged by who it brought in, not by how many.

The honest-attribution discipline here is adapted from the monthly Page report
in the company-page bundle (`page-performance-report`, MIT), which states
plainly what the data cannot attribute. That is the right default and it is
reused rather than reinvented. See `ATTRIBUTION.md`.

## When to use

- "Is my posting actually doing anything?"
- Which posts brought in people worth having.
- Connecting content to the network funnel at the end of a month.
- Before deciding what to write next quarter.

Distinct from `linkedin-audience-intelligence`, which measures the audience as
it stands today. This one works over time and joins content to what happened in
the network afterwards.

## Required inputs

- The user's own post analytics export.
- `profile.content_topics`, or topic labels on the posts.
- Optionally: the CRM, which is what lets content be joined to connections and
  opportunities rather than to engagement alone.

## The metric hierarchy, which is the point

Five things get confused constantly. They are reported separately and never
summed:

| Level | What it is | What it proves |
|---|---|---|
| Impressions | A delivery figure the platform reports about itself | Nothing about readership |
| Reactions | A tap | Recognition, at most |
| Comments | Someone choosing to be identified with the topic in public | Real interest |
| Shares | Someone spending their own credibility | Strong interest |
| Followers | Someone opting into more | Audience growth |
| **Business outcomes** | A conversation, a meeting, an opportunity — **user-confirmed** | The only level that answers "is it working" |

A post with 40,000 impressions and no outcome is not a successful post. The
report says so.

## Workflow

1. Safety check the request.
2. Import the analytics; import or confirm the topic labels.
3. Roll up by topic, with the sufficiency floor applied.
4. Build the growth series by month: followers gained, engagement, posts.
5. Join to the network where the CRM supports it: candidates created,
   accepted connections, and opportunities in the same windows as the posts.
6. Record the business outcomes the user confirms, per post. This is the only
   way they enter the data, and most posts will have none.
7. Report, with the limits section built from the actual gaps.

## Joining content to the network, and its limit

The join this skill can make: posts published in a window, and connections
accepted or opportunities created in the same window.

That is correlation in time. It is useful and it is not causation, and the
report says which it is every time. A month with a conference in it moves both
series. So does a month with a product launch, a hiring push, or a holiday.

The join this skill **cannot** make is per-person: LinkedIn does not expose
engager identity to this bundle, so "this specific post brought this specific
connection" is unavailable unless the user says so themselves, or supplies an
engager roster they exported. Reported as unavailable with that reason.

## Output format

```
## Content to audience — 2026-05 to 2026-10, 38 posts

### By theme
theme                 posts  impressions  comments/post  followers/post  outcomes
inventory accuracy       11      142,000           4.6             2.1         3
ERP migrations            5       61,200           5.8             0.4         2
demand planning           9       98,400           3.1             1.4         0
hiring                    2       44,900           1.0             0.0         0  (unranked, 2 posts)

Highest impressions: hiring. Highest comments and every confirmed outcome:
inventory accuracy and ERP migrations. On this evidence the impressions
column is the least informative one on the page.

### Growth by month
month    posts  followers gained  engagement
2026-05      6               118         734
2026-06      7               142         910
2026-07      5         unavailable         602
2026-08      8               201       1,340
2026-09      6               166         988
2026-10      6               193       1,205

### Network, same windows
Candidates created 71 · accepted connections 18 · opportunities 6
Of the 18 accepted, 11 carry an active ICP classification.

Correlation only. These windows overlap with your posting; nothing here shows
that a post caused a connection.

### Confirmed business outcomes (5)
- 2026-06-14, inventory accuracy: discovery call with a mid-size producer
- 2026-08-02, ERP migrations: introduction to a partner
… 3 more

### What this cannot attribute
- 14 of 38 posts carry no follower figure.
- No post carries attributed profile views; LinkedIn does not expose them.
- Per-person attribution is unavailable: engager identity is not exposed to
  this bundle. Import a roster you exported yourself to fill this.
- Connections accepted in a window are not attributable to posts in that
  window. The invitation, a profile view, a comment weeks earlier, or a mutual
  contact may each have done the work.
- Impressions are a delivery figure, not readership.
```

## Failure handling

- **No export:** nothing to attribute. Say so and say where the export comes
  from.
- **No topic labels:** report totals and the growth series; say that theme
  analysis needs labels.
- **No confirmed outcomes:** report that plainly. It is the commonest case and
  it is informative: six months of engagement with no recorded outcome either
  means the outcomes were not recorded, or that the content is not reaching
  people who buy. Ask which.
- **Thin per-topic samples:** report, mark unranked, and say what the floor
  means.
- **The user asks which post brought a specific connection:** unavailable, with
  the reason. If they know, record it as a confirmed outcome — their knowledge
  is data, an inference is not.
- **Metrics missing for a month:** report `unavailable`, never interpolate. A
  gap in a series is information.

## Safety requirements

- `no_fabrication`: no estimated metric, ever.
  `reporting.estimate_missing_metrics` cannot be enabled, and the configuration
  refuses to load with it on.
- No per-person attribution without the user's own statement or their own
  export.
- Business outcomes are user-confirmed only. Nothing is counted as an outcome
  because it looks like one.
- Impressions are never reported as readership or as reach into a segment.

## Examples

**The useful reframe**

> User: My hiring post did 45k impressions, should I do more of those?

Show the columns: highest impressions, lowest comments, no outcomes. Then the
honest answer — the impressions column is measuring something other than what
the user wants, and the topics with a tenth of the reach produced every
confirmed conversation.

**The limit, stated**

> User: So did the May posts bring those connections?

No. The windows overlap; that is all the data shows. If the user remembers
which, that is worth recording as a confirmed outcome.

## Related

- `linkedin-audience-intelligence` for the audience as it stands.
- `linkedin-network-growth-analyst` for the funnel.
- Company Page equivalent: `page-performance-report` in the company-page bundle.
- `lni/attribution.py`, `lni/reporting.py`
