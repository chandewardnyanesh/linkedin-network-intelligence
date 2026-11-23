---
name: linkedin-connection-strategy
description: "Prepare personalised, context-aware connection recommendations: a legitimate reason to connect grounded in shared context, several invitation note variations, a recommended first conversation topic, the profile context a human should read first, and a follow-up approach. Draft-only — it never sends an invitation or a message, and refuses to produce output intended for an automated sender. Use when a shortlist is ready and the user wants notes to send by hand, or when an invitation was declined and the approach needs rethinking."
license: MIT
metadata:
  author: Dnyanesh Chandewar
  bundle: linkedin-network-intelligence
  version: 0.1.0
---

# LinkedIn Connection Strategy

Turns a scored candidate into something a human can send in thirty seconds.

**This skill is draft-only.** There is no sender in this bundle. Every note it
produces is for the user to send themselves, in LinkedIn.

## When to use

- A shortlist is ready and the user wants notes.
- An invitation was declined or ignored and the approach needs rethinking.
- The user is about to reach out and wants the context in front of them first.

## Required inputs

- `profile.display_name` and `profile.primary_objective`. Ask if missing: a
  note written in nobody's voice reads like a template.
- A candidate with at least one piece of **checkable shared context** or real
  profile context. Without either, the recommendation is refused — see Failure
  handling. That is not pedantry: a note with no specific reason is the single
  commonest cause of a declined invitation.

## Workflow

1. Safety check the request. "Draft the notes so I can send them" is allowed;
   "send them" is not.
2. Read the candidate, their score and their propensity band.
3. Establish the reason to connect. Rank the available grounds:
   1. A specific exchange that already happened (they commented, you replied).
   2. A shared context that is checkable — same event, same group, mutual
      contact the user named, same publication.
   3. Something specific and public they did that the user genuinely read.
   4. A role-level reason, which is the weakest and should be said plainly.
4. Write two or three variations with different tones, all under the character
   limit, none containing a pitch.
5. Add the first conversation topic and the follow-up approach.
6. Present the review card. Record the drafts against the candidate and set the
   status to `invitation_prepared`.
7. When the user says what they sent, record `manually_invited --confirmed`.

## What goes in a note

| Include | Leave out |
|---|---|
| The specific reason, first | "I'd love to connect and expand my network" |
| Something only this person's note could say | Anything reusable across ten people |
| A question or an opening, if it fits in the limit | The user's own offer, services or pitch |
| Their name, spelled and capitalised correctly | Flattery about their "impressive profile" |

The character limit is configurable (`char_limit`, default 300) because
platform limits change and a stale constant in code is worse than a value the
user can correct. A draft over the limit is rejected rather than silently
truncated, so the user never discovers the cut in LinkedIn.

**No pitch on first contact.** The model layer refuses an invitation draft
marked as containing one. Relationship-first is not a style preference here: a
pitch in a connection note converts the one chance into a decline.

## Sequencing by propensity

| Band | First move |
|---|---|
| `very_high` | Connect now, referencing the conversation already happening |
| `high` | One more substantive comment, then connect referencing it |
| `moderate` | Engage for two or three weeks first; there is nothing to say yet |
| `low` / `very_low` | Follow, do not connect. Revisit when there is something to respond to |
| `insufficient_evidence` | Cold. The note carries the whole weight, so it needs a real reason or it should not be sent |

## Output format

```
## For your review — connection invitations
**Performed by:** you, in LinkedIn
**Items:** 3

### 1. Dana Whitfield — VP Operations @ Northfield Foods
https://linkedin.com/in/dana-whitfield

**Why connect:** She replied to your comment on monthly stock counts on
15 November and wrote three paragraphs of her own on 20 November. The
conversation is already running.

**Context worth reading first**
- VP Operations, Northfield Foods, 201–500 people, US
- Spoke at the same supply-chain summit you attended in October
- Source: your own notifications; conference speaker listing (public)

**Invitation drafts** (limit 300)

> *direct — 214 chars*
> Dana — your point about reconciling counts against the system landed. We
> hit the same wall at a 300-person site last year and solved it badly twice
> before it worked. Would be good to compare notes.

> *warmer — 189 chars*
> Dana — we were both at the supply-chain summit in October, and your comment
> last week on monthly counts is still rattling around my head. Worth a
> conversation.

**First conversation topic:** how she reconciles counts when the system and
the shelf disagree — she has already said this is unsolved.

**Follow-up:** if she accepts and says nothing, leave it. Comment on her next
post instead. A thank-you message after an acceptance is noise.

… 2 more

Tell me which of these you actually sent and I will record them. Nothing is
recorded as sent until you say so.
```

## Failure handling

- **No shared context and no real profile context:** refuse to draft. Say what
  would fix it: a comment on one of their posts, a look at what they have
  published, or a mutual contact the user can name. A generic note is worse
  than no note, because the one chance is spent.
- **The user wants one note for the whole list:** say that a note reusable
  across ten people is the definition of the note that gets declined. Offer to
  draft ten, or to cut the list to the three worth writing for.
- **The user asks for a pitch in the note:** refuse that part, keep drafting
  the rest, and say where the offer belongs — a later conversation, after a
  reply.
- **The draft will not fit:** cut the note, not the reason. If the reason will
  not fit in the limit, the reason is too complicated and there is probably a
  simpler true one.
- **An invitation was declined:** do not redraft and resend. Record it, leave
  the person alone, and if the user wants to try again later the route is
  engagement, not a second note.
- **The user asks to send:** refuse, citing `no_automated_invitations`, and
  hand over the review list.

## Safety requirements

- Draft-only. No send, no queue, no schedule, no export shaped to feed a sender.
- `no_fabrication`: never invent a shared context, an event, a mutual contact
  or a reaction to something the user has not read. A fabricated opener is a
  cold note that lies, and it is the one failure mode that damages the user's
  reputation rather than just wasting a slot.
- Nothing is recorded as sent without the user's confirmation.
- A declined or ignored invitation is not a prompt for a follow-up sequence.
- The bundle has no view on how many notes to send in a week. If the user has
  stated their own capacity, the list is trimmed to it; pacing for any other
  reason is refused under `no_detection_evasion`.

## Examples

**Earned**

> User: Draft a note for Dana.

Lead with the exchange that already happened. Two variations. No pitch.

**Not earned, and say so**

> User: Draft notes for all 25 on the shortlist.

Report that 6 have a checkable reason and 19 do not. Draft the 6. For the 19,
the honest next step is engagement, and spending 19 invitations on generic
notes costs more than it returns.

## Related

- `linkedin-network-scoring` and `linkedin-engagement-propensity` decide who
  and in what order.
- `linkedin-network-crm` records the drafts and the statuses.
- `linkedin-relationship-manager` takes over after an acceptance.
- Voice and phrasing: the personal-profile bundle's own voice-rules reference
  and its `linkedin-humanizer`, rather than a second set of rules here.
