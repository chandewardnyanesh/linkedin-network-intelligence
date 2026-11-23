---
name: linkedin-relationship-manager
description: "Keep professional relationships alive after the connection: recommends who is worth a follow-up and when, prepares context-aware conversation starters from the actual interaction history, spots collaboration and introduction opportunities, and suppresses anyone touched too recently so outreach never becomes repetitive or intrusive. All external communication is drafted for the user to send. Use when the user asks who to follow up with, wants to reconnect with dormant contacts, or is about to message someone they have not spoken to in months."
license: MIT
metadata:
  author: Dnyanesh Chandewar
  bundle: linkedin-network-intelligence
  version: 0.1.0
---

# LinkedIn Relationship Manager

The part people skip. Accepting an invitation is not a relationship; it is a
list entry with a nicer name.

## When to use

- "Who should I follow up with this week?"
- A contact has gone quiet and the user wants to reconnect.
- Two contacts should probably meet each other.
- Before messaging someone the user has not spoken to in months, so the message
  starts from what was actually said.

Works at the level of **people**. Thread-level follow-up — which of the user's
own comments got an author reply, and the 6–24 hour warm window — belongs to
the personal-profile bundle's `linkedin-thread-monitor`, and this skill routes
there rather than reimplementing it.

## Required inputs

The CRM, with interaction history. A relationship nobody logged has no state to
manage, so the first run usually starts by asking the user what has actually
happened with their last few acceptances.

## Anti-repetition, enforced not advised

This is the design decision that matters. Repetitive outreach is the failure
mode of every CRM, and advice does not prevent it. The engine does:

| Setting | Default | Effect |
|---|---|---|
| `min_days_between_outbound_touches` | 21 | A contact touched inside this is **suppressed from the list entirely** |
| `follow_up_window_days` | 7–45 | Outside this, a follow-up reads as either too eager or out of nowhere |
| `max_follow_ups_without_reply` | 2 | After two unanswered touches, the contact stops appearing. No third |
| `dormant_after_days` | 120 | Past this, it is a reconnection, not a follow-up, and reads differently |

A contact who has not replied twice is not a contact who needs a better
message. Leaving people alone is a feature.

## Workflow

1. Safety check the request.
2. Read the CRM: statuses, last outbound touch, inbound replies, substantive
   interactions.
3. Build the candidate list: contacts inside the follow-up window, not
   suppressed by recency, not past the unanswered limit.
4. For each, find the thread — the last substantive thing exchanged, and
   anything since then that is checkable and relevant.
5. Rank by what is actually worth saying, not by how long it has been. Silence
   is not a reason to message someone.
6. Draft the starters. Present the review card.
7. Record what the user actually sent, and log the interaction.

## What makes a follow-up worth sending

Ranked. If none of the first three applies, there is no follow-up to make, and
the honest recommendation is to leave the person alone.

1. **Something they said is now resolved or relevant.** They mentioned a
   project; it shipped. They asked something; the user now knows.
2. **Something the user has that they would want.** A specific thing, not an
   offer: the paper, the name of the person who solved it, the number.
3. **A real event.** They changed role, published something, spoke somewhere.
4. **Reciprocity.** They did something for the user and it was never
   acknowledged properly.
5. **Time has passed.** The weakest, and on its own, not enough.

## Collaboration and introductions

Two contacts worth introducing is the highest-value output here and the one a
CRM can actually see: both in the user's network, complementary rather than
competing, working on adjacent problems.

An introduction is only offered when it would help **both** people, and it is
always drafted for the user to make. Never offer an introduction whose benefit
is only to the user: that spends the user's credibility with both of them.

## Output format

```
## Follow-ups worth making — week of 2026-11-23

Suppressed from this list: 14 contacts touched in the last 21 days, and
3 who have not replied to two previous touches. Neither group appears until
something changes.

### 1. Dana Whitfield — last exchange 38 days ago
**Why now:** in October she said the monthly count reconciliation was
unsolved. You have since worked through exactly that at another site.
**Thread:** her comment 2026-10-16, your reply 2026-10-16, nothing since.
**Status:** engaged · 3 substantive interactions

> *draft*
> Dana — you mentioned the count reconciliation being unsolved back in
> October. We just went through it at a 300-person site and the thing that
> actually worked was unglamorous. Happy to walk you through it if useful.

**If no reply:** leave it. This is touch two; there is no touch three.

### 2. Sam Okoye — introduction opportunity
Sam is building the planning side; Priya Nair solved the same thing last
year at a similar size. Neither sells to the other.

> *draft introduction, for you to send*
> Sam, Priya — you are both wrestling with planning at roughly the same
> scale from opposite directions. Priya, Sam is six months into what you
> finished last year. I will get out of the way.

### Nothing to say (7)
7 contacts are inside the window with no event, nothing resolved and nothing
to offer. A message to any of them would be a message about nothing. They stay
on the list for next week.

### Dormant (11)
Past 120 days. A reconnection, not a follow-up — different message, and worth
doing deliberately rather than in bulk. Ask if you want those drafted.

Tell me which you actually sent and I will log them.
```

The "Nothing to say" section is not filler. It is the section that stops the
skill from manufacturing reasons to message people.

## Failure handling

- **No interaction history:** say so, and ask what has happened with the last
  few acceptances. Offer to log them. Do not generate follow-ups for
  relationships with no recorded content.
- **Everyone suppressed:** say that plainly — it means the user has been in
  touch recently, which is the goal. Do not lower the threshold to produce a
  list.
- **No real reason for anyone:** say there is nothing worth sending this week.
  A quiet week is a correct output.
- **The user wants to message someone suppressed by recency:** tell them the
  last touch date and let them decide. It is their relationship; the engine
  informs, it does not forbid. Record the override.
- **The user wants a sequence:** refuse. A sequence is automation with a human
  pressing the button, and the two-touch limit exists because the third message
  is the one that costs the relationship.
- **A contact asked not to be contacted:** that outranks everything. Archive
  them and never surface them again, whatever the configuration says.

## Safety requirements

- Every external communication is drafted for the user to send.
  `no_automated_messaging` applies to all of it.
- Anti-repetition is enforced in the engine, not left to judgement.
- `no_fabrication`: never invent a thing they said, a project, an event or a
  shared history. The whole value of a follow-up is that it refers to something
  real, and an invented reference destroys more than silence would.
- No introduction that serves only the user.
- A stated request not to be contacted is permanent and overrides the
  configuration.

## Examples

**A real reason**

> User: Who should I follow up with?

One contact with a resolved question, one introduction worth making, seven
with nothing to say and the reason stated, eleven dormant and offered
separately.

**The sequence to refuse**

> User: Set up a three-touch sequence for everyone who accepted but went quiet.

Refuse. Say what the two-touch limit is for: someone who has not replied twice
has answered. Offer the one thing that works instead — engaging with their
posts, where they get to choose whether to reply.

## Related

- `linkedin-network-crm` holds the history this reads.
- `linkedin-connection-strategy` owns the first touch; this one owns everything
  after.
- Comment-thread follow-up: the personal-profile bundle's
  `linkedin-thread-monitor` and `linkedin-reply-handler`.
- `config/default.yaml` → `relationships`
