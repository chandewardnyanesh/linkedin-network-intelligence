# Metrics taxonomy

What each number means, and what it does not. Shared by
`linkedin-audience-intelligence`, `linkedin-content-audience-attribution` and
`linkedin-network-growth-analyst`, so the three never describe the same figure
differently.

## Content metrics, weakest to strongest

| Metric | What it is | What it proves |
|---|---|---|
| Impressions | A delivery count the platform reports about itself | Nothing about readership |
| Members reached | Unique accounts the platform served it to | Nothing about attention |
| Reactions | A tap | Recognition, at most |
| Short comments | A few words, often courtesy | Weak interest |
| Substantive comments | More than a sentence, on the subject | Real interest, and public association with the topic |
| Shares with commentary | Someone spending their own credibility | Strong interest |
| Followers gained | Someone opting into more | Audience growth |
| **Business outcomes** | A conversation, meeting or opportunity, user-confirmed | The only level that answers "is it working" |

These are never summed into one "engagement" figure. A post with forty thousand
impressions and no outcome is not a successful post.

## Network funnel metrics

| Metric | Definition here |
|---|---|
| Profiles researched | Candidate records created in the window |
| Qualified candidates | Moved to `qualified` in the window |
| Invitations manually sent | Moved to `manually_invited`, user-confirmed |
| Invitations accepted | Moved to `accepted`, user-confirmed |
| Acceptance rate | Accepted ÷ sent. `unavailable` when sent is zero |
| Relevant connections gained | Acceptances whose primary ICP is still active |
| Meaningful interactions | Logged interactions marked substantive. A reaction is not one |
| Qualified leads | Moved to `potential_lead` |
| Discovery meetings | Logged interactions on the meeting or call channel |
| Business opportunities | Opportunities created or updated in the window |

## Structurally unavailable

Not missing because nobody built it. Unavailable because this bundle does not
read LinkedIn:

- **Profile visits** — in the account's own analytics. Filled from an export.
- **Followers gained** — likewise.
- **Content engagement from new connections** — needs engager identity joined
  to connection dates. LinkedIn does not expose engager identity here. Filled
  from a roster the user exported themselves.

## Rate rules

- A rate with a zero denominator is not zero; it is unavailable.
- A share of an audience requires a counted size, not a declared one.
- A per-topic figure below `audience.min_posts_per_topic` is reported and not
  ranked. Insufficient sample is not evidence of a poor topic.
- A missing month stays missing. Nothing is interpolated or carried forward.

## What `unavailable` means

That the figure could not be sourced, with the reason given. It never means
zero, and `reporting.estimate_missing_metrics` cannot be enabled to make it
mean something else.
