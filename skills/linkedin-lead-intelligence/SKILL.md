---
name: linkedin-lead-intelligence
description: "Identify potential business opportunities inside networking research: relevant decision-makers, possible demand for AI implementation, automation, website and ecommerce work, CRM and operational automation, against configurable service categories. Classifies each as a hypothesis with the public evidence behind it and recommends discovery questions. Does not infer confidential company information and does not fabricate purchasing intent. Use when the user wants to know which contacts might become customers, or what to ask on a first call."
license: MIT
metadata:
  author: Dnyanesh Chandewar
  bundle: linkedin-network-intelligence
  version: 0.1.0
---

# LinkedIn Lead Intelligence

Notices that someone in the network might have a problem the user can help
with, and says so as a hypothesis with its evidence attached.

## When to use

- The user wants to know which contacts might become customers.
- A first call is coming up and the user wants the questions worth asking.
- A new service category needs defining.

## Required inputs

- `business_services.categories`, each with **observable signals**. A category
  without them cannot classify anything.
- `profile.services_offered`, so the categories match what the user actually
  does.

Run `python -m lni missing linkedin-lead-intelligence`. If both are empty, ask
whether the networking is commercial at all. **With no categories configured,
this skill correctly reports nothing** — that is the right answer for someone
networking non-commercially, not a failure to try.

## What a signal may and may not be

| Allowed | Not allowed |
|---|---|
| A public job posting implying the work | "They must be hiring for this" |
| The company's own site describing a process | "Their systems are probably legacy" |
| Something the person said in public | "They seem frustrated with their vendor" |
| A talk, paper or case study | Anything about budget |
| Something the user was told directly | Anything about contract terms or renewal dates |
| A referral's description | Anything about an internal system nobody published |

The engine enforces the source side of this: a signal whose provenance is not a
permitted kind is rejected outright.

## The two rules that shape every output

**Do not infer confidential company information.** Budget, contracts, renewal
dates, internal systems and procurement status are not observable from an
authorised source. Nothing here reasons about them, and a request to is
refused.

**Do not fabricate purchasing intent.** An opportunity is a *hypothesis about a
possible need*, never a statement about plans. Stages:

| Stage | How it is reached |
|---|---|
| `hypothesis` | A category looks plausible, no signal yet |
| `signal_observed` | At least one usable public signal matched |
| `discussed` | **The user confirms a real conversation happened** |
| `qualified` | The user confirms it is real |
| `won` / `lost` / `declined` | The user says so |

Anything past `signal_observed` requires the user's confirmation; the model
layer refuses the attempt otherwise. Confidence is capped at
`max_confidence_without_user_confirmation` (default medium) until then, and the
configuration refuses to set that to high.

## Workflow

1. Safety check the request.
2. Confirm the categories are usable. Hand back to the user to define them if
   not.
3. Collect the signals the user has, or that a public page states. Stamp each
   with provenance.
4. Classify: each candidate against each usable category. Disqualifiers are
   checked first.
5. Report the hypotheses, highest relevance first, each with its signals and
   confidence.
6. Produce discovery questions — the category's own, plus two structural ones
   whose answers the user cannot guess.
7. Record against the candidate. Only the user's confirmation moves a stage.

## Discovery questions

The point is to learn, not to confirm. Two structural questions are always
added because their answers cannot be predicted:

- What does that process look like today, end to end?
- What have you already tried, and where did it stop?

A good question has no good answer the user already knows. "Are you looking to
improve your inventory accuracy?" is a pitch with a question mark.

## Output format

```
## Opportunity hypotheses — 3 contacts, 2 categories

### Dana Whitfield @ Northfield Foods
**inventory_implementation** · relevance 85/100 · confidence medium ·
stage signal_observed

Hypothesis: Northfield Foods may have work in inventory system
implementation. Based on: public job posting for an inventory, planning or
stock-control role; the company's own site describes a manual process in this
area. This is a hypothesis about a possible need, not a statement about their
plans, systems or budget.

Signals
- job posting for an inventory analyst on the careers page
      source: company_website (https://northfield.example/careers) · medium
- the site states stock counts are done manually each month
      source: company_website (https://northfield.example/ops) · medium

Discovery questions
1. How do you know today what is actually on the shelf?
2. What happens when the count and the system disagree?
3. What does that process look like today, end to end?
4. What have you already tried, and where did it stop?

### What this cannot tell you
- Every unconfirmed entry is a hypothesis built from public signals. None of
  them is evidence that anyone intends to buy anything.
- Confidence is capped at medium until you confirm a real conversation.
- Nothing here infers budget, contract status or internal systems, because
  none of that is observable from an authorised source.
```

The closing section is required output, not a disclaimer.

## Failure handling

- **No categories:** report nothing and say why. Offer to define them.
- **Categories with no observable signals:** say which, and that they cannot
  classify anything until they have signals.
- **A disqualifier fires:** no opportunity is recorded. Say which disqualifier,
  so the user can disagree with it.
- **Signals match several categories weakly:** report the strongest and say the
  others were below threshold. Do not list five hypotheses off one job posting.
- **The user asks for budget or contract information:** refuse, citing
  `no_private_data`. Offer the discovery question that would actually answer it
  — asked of the person, by the user.
- **The user wants the stage moved without a conversation:** refuse. A stage
  past `signal_observed` is a claim about something that happened.

## Safety requirements

- `no_private_data` and `no_fabrication` govern this skill.
- Signal sources are restricted at the engine level, not by convention.
- Nothing here produces outreach. A hypothesis is for the user to test in a
  conversation, and `linkedin-connection-strategy` still refuses a pitch on
  first contact.
- A filled `business_services.yaml` is commercially sensitive. Say so once:
  keep it out of a public repository.

## Examples

**A real signal**

> User: Northfield posted a job for an inventory analyst and their site
> mentions monthly manual counts.

One hypothesis, `inventory_implementation`, `signal_observed`, confidence
medium, four discovery questions, and the limits section.

**The overreach to refuse**

> User: Work out which of these 30 companies has budget approved this quarter.

Refuse. Budget is not observable from an authorised source, and a guess
presented as intelligence is the thing that loses a deal on the first call.
Offer the signals that are visible, and the questions that would find out.

## Related

- `linkedin-network-scoring` uses the opportunity score as one component.
- `linkedin-network-crm` stores the opportunities.
- `lni/leads.py`, `config/business_services.yaml`
