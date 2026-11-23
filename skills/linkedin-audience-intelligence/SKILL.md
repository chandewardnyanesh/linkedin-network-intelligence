---
name: linkedin-audience-intelligence
description: "Understand who the user's LinkedIn audience actually is and which professional audiences are worth attracting. Analyses the user's own analytics and post exports, identifies recurring engagement patterns and the topics that earn meaningful engagement, segments the audience by professional relevance against the configured ICPs, measures the gap between the existing and the desired audience, and recommends content themes to close it. Use when the user asks who their audience is, whether their reach is the right reach, or what to write more of."
license: MIT
metadata:
  author: Dnyanesh Chandewar
  bundle: linkedin-network-intelligence
  version: 0.1.0
---

# LinkedIn Audience Intelligence

Answers one question: *is the audience you have the audience you want?*

## When to use

- The user asks who their audience is, or whether their reach is the right
  reach.
- Follower count is growing and nothing is happening.
- The user wants to know which topics bring the right people in.
- Before a content plan, so the plan is aimed at a measured gap.

**Not** a per-post engager pull. The personal-profile bundle's
`linkedin-engager-analytics` does that, per post, and its roster is a valid
input here when the user exports one and hands it over. This skill works at
the level of the corpus and the audience over time, which that one does not.

## Required inputs

Ask for all three. None can be invented:

1. **An export.** The user's own LinkedIn analytics or post export. Path to a
   CSV. Without it, there is nothing to analyse and the honest answer is to say
   so.
2. **`profile.content_topics`.** What the user publishes about, so posts can be
   grouped by topic.
3. **`audience.desired_audience`.** Which ICPs they want more of. The gap
   between this and the current audience is the whole output.

`python -m lni missing linkedin-audience-intelligence` lists what is absent.

## Workflow

1. Safety check the request.
2. Ask for the export. Tell the user where it comes from — their own analytics
   page — and never offer to fetch it.
3. `python -m lni import-analytics <path>`.
4. Label posts by topic. The export rarely carries topics, so either the user
   supplies a mapping or the topics come from a column they added. Do not infer
   a topic from a post's metrics.
5. Build the topic affinity matrix. A topic under `min_posts_per_topic`
   (default 3) is reported but not ranked.
6. Segment the audience against the active ICPs, using whatever the export
   carries about who engaged. Where it carries nothing, say so.
7. Measure the gap against `desired_audience`.
8. Recommend themes, each with its basis and its caveat.

## Segmenting honestly

LinkedIn's own analytics give the account holder aggregate demographics — job
titles, industries, seniorities, locations — not a list of people. So:

- A segment built from aggregate demographics has a **declared** size, not a
  counted one, and the output says which.
- A segment with no counted size produces no share of the audience, and
  `AudienceSegment` refuses a size with no stated basis.
- Matching a segment to an ICP is a judgement from the demographic labels, not
  a per-person check. Say that once.

What this means in practice: the skill can tell the user that 34% of their
reach is job titles that match no active ICP. It cannot tell them which
individuals those are, and it does not pretend to.

## Topic affinity

Topics are ranked on **comments per post**, not impressions. A comment is a
person choosing to be identified with the topic in public, which is what brings
the right audience in. Impressions are a delivery figure the platform reports
about itself.

Reported per topic: posts counted, impressions, reactions, comments, shares,
followers gained, and whether the sample is sufficient.

## Output format

```
## Audience intelligence — 38 posts, 2026-05 to 2026-10

### Topic affinity
topic                      posts  impressions  comments/post  followers/post  ranked
inventory accuracy            11      142,000           4.6             2.1  yes
demand planning                9       98,400           3.1             1.4  yes
ERP migrations                 5       61,200           5.8             0.4  yes
hiring                         2       44,900           1.0             0.0  no — 2 posts

### Segments
segment                              basis       share  quality    matches ICP
operations leaders, manufacturing    declared      31%  target     business_development
software and IT services             declared      22%  adjacent   strategic_partnerships
consultants and agencies             declared      19%  irrelevant —
job seekers, unrelated fields        declared      12%  irrelevant —
unclassified                         declared      16%  unknown    —

### The gap
business_development    target 35%   current 31%   gap  +4pp
strategic_partnerships  target 10%   current 22%   gap -12pp  (over target)

You do not have an audience problem on the business-development side; you have
a 19% consultant audience that engages heavily and buys nothing. That is what
is making the engagement rate look healthier than the pipeline.

### Recommended themes
1. ERP migrations — 5.8 comments per post, your highest, on the smallest
   sample of the three ranked topics.
   Caveat: ranked on comments per post, not impressions. Whether those
   commenters are the audience you want depends on who they are, which this
   metric does not know.

### What this cannot attribute
- 14 of 38 posts carry no follower figure, so "which topic grew the audience"
  is answerable only for the rest.
- No post carries attributed profile views. LinkedIn does not expose per-post
  profile views to most accounts.
- No business outcomes are recorded against any post. Engagement counts are
  all this can report; whether any of it produced a conversation is not in
  the data.
- Segment sizes are declared from aggregate demographics, not counted per
  person.
- Per-post engagement and follower change are correlated in time, not causally
  linked. A week with a conference talk in it moves both.
```

The final section is required output. It is built from what the data actually
lacks, not from a fixed paragraph.

## Failure handling

- **No export:** say plainly that nothing can be analysed, where to get the
  export, and that nothing here reads LinkedIn. Do not offer a partial analysis
  from memory or from the user's impressions.
- **Export with no topic labels:** report engagement totals and say that topic
  affinity needs labels. Offer to work from a mapping the user supplies.
- **Fewer than three posts per topic:** report the topic, mark it unranked, and
  say what that means: not evidence it does not work, evidence there is not
  enough to tell.
- **No desired audience set:** report the current audience and ask which ICPs
  they want more of. Do not infer the target from what is already working — that
  makes the gap zero by construction.
- **Columns unrecognised:** list the headers found and which were mapped.

## Safety requirements

- Reads only the user's own exports. `no_scraping` applies: there is no route
  here to anyone else's analytics.
- `no_fabrication`: a metric the export does not carry is reported as
  unavailable with the reason, never estimated, interpolated or carried forward.
  `reporting.estimate_missing_metrics` cannot be enabled.
- Segments are never defined by a protected characteristic, even when the
  platform's demographics offer one.
- Impressions are never presented as readership.

## Examples

**The common finding**

> User: My follower count is up 40% and nothing's coming in.

Segment the audience. If a fifth of it is consultants and job seekers, that is
the answer, and the recommendation is a topic change rather than more posting.

**The honest refusal**

> User: Can you look at my analytics and tell me?

Explain that nothing here reads LinkedIn, that the export comes from their own
analytics page, and that with the file this takes a minute.

## Related

- `linkedin-icp-builder` defines the audiences being measured against.
- `linkedin-content-audience-attribution` goes deeper on topic to audience
  quality over time.
- Per-post engagers: the personal-profile bundle's `linkedin-engager-analytics`.
- Category trends: the company-page bundle's `trend-radar`.
- `lni/attribution.py`, `lni/importers.py`, `config/audience.yaml`
