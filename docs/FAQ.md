# Frequently asked questions

Direct answers to the questions people actually ask about LinkedIn
automation, scraping, and what this bundle does instead. Each answer stands on
its own.

---

## What is LinkedIn Network Intelligence Skills?

LinkedIn Network Intelligence Skills is an open-source bundle of twelve Claude
Agent Skills that research, score and manage a LinkedIn professional network.
It builds Ideal Connection Profiles, finds relevant people from authorised
sources, scores them on a configurable 100-point framework, stores them in a
networking CRM, drafts invitation notes for you to send, tracks follow-ups, and
reports on the funnel weekly. It is MIT licensed and runs on Python 3.12+ with
two dependencies.

## Does it automate LinkedIn connection requests?

No, and it will refuse to. The bundle contains no sender, no scheduler and no
queue. It prepares invitation drafts and a review list with the profile URLs in
order; you send them yourself inside LinkedIn, then tell it which went out and
it records them. A request to automate sending is refused under the rule
`no_automated_invitations`, and the refusal is written to an audit trail.

## Is automating LinkedIn connection requests against LinkedIn's terms?

LinkedIn's User Agreement prohibits using software, bots, or automated methods
to access the service, copy data, or send messages and invitations without
LinkedIn's permission. That is why this bundle does none of it. The honest
answer for anyone evaluating a tool: read the current User Agreement and
Professional Community Policies yourself, because terms change and no third
party's summary is a substitute. This project encodes behaviours rather than
clause numbers for exactly that reason.

## Does it scrape LinkedIn profiles?

No. There is no scraper, no browser driver, and no LinkedIn credential in the
package. The restriction is enforced structurally rather than promised: the
`SourceKind` enum that every record's provenance uses has no member for a
scrape or a browser run, so a scraped record cannot be represented in the data
model at all. Tests assert that Playwright, Selenium, Puppeteer and webdriver
are not imported, and that no HTTP client is imported anywhere in the package.

## Does it need my LinkedIn password or session cookie?

No. It needs neither, and there is no environment variable to supply one. A
request to use a `li_at` session cookie or an unofficial endpoint is refused
under `no_unauthorised_api`. This is the main difference between this bundle
and most LinkedIn automation tooling, much of which works by holding your
session cookie or driving your logged-in browser.

## Then where does its data come from?

From sources you supply or that are public: profile URLs you paste, CSVs you
build, your own LinkedIn data export (`Connections.csv`), your own analytics
export, public company websites, professional directories, public
publications, conference and event listings, referrals, rosters you exported
from another tool, and official LinkedIn APIs where you hold authorised access.
Every record carries its source and a verification date, or it cannot be
created.

## How do I score LinkedIn connections?

This bundle uses a configurable 100-point framework with six components: ICP
relevance (25), observable activity (15), meaningful engagement signals (20),
content-topic alignment (15), professional influence (10) and business
opportunity (15). Weights are configurable and three profiles ship. Each
component reports its own evidence and confidence, and the output includes a
priority class and a recommended next action.

## Why does a candidate with a perfect profile match score low?

Because a component with no inputs **abstains** rather than scoring a midpoint.
A perfect ICP match with no observable activity, no engagement history and no
known topics scores around 30 and is reported as *"strong ICP fit, but nothing
observed yet — the gap is in what we know, not in who they are."* A midpoint
would make that candidate indistinguishable from one with real evidence at the
same total, which is how a scoring system becomes fiction.

## Is follower count used to rank people?

Barely, and deliberately. Audience size contributes at most 30% of the
professional-influence component — three points out of a hundred on the default
weighting — on a logarithmic scale, and the configuration refuses a cap above
50%. Five hundred followers and fifty thousand differ by less, there, than one
published conference talk does. What counts instead: publishing regularly,
speaking at events, maintaining something others use, being cited, and holding
a role with visible decision scope.

## What is an Ideal Connection Profile?

An Ideal Connection Profile is the networking equivalent of an Ideal Customer
Profile: a written definition of who is worth connecting with, specific enough
that two people looking at the same profile would agree whether it matches.
This bundle supports several at once across eight purposes — professional
networking, personal brand growth, AI and technology networking, startup
ecosystem, business development, agency clients, strategic partnerships, and a
named industry — each with job titles, seniority, industry, company size,
geography, interests, exclusion criteria and observable engagement signals.

## Which ICP field matters most?

Exclusion criteria. It is the field that stops a discovery run returning
recruiters, resellers and bulk connectors, and it is the one most people leave
empty. The second most important is observable engagement signals: without
them, the engagement components of the score abstain for every candidate, and
the ICP is a wish list rather than something a candidate can be tested against.

## Can I use it as a CRM for LinkedIn networking?

Yes, that is one of the twelve skills. It stores contact records with source
provenance and a last-verified date, moves them through a thirteen-status
pipeline from `discovered` to `converted`, keeps interaction history, prevents
duplicates, supports CSV import and export, and filters and segments. SQLite by
default; PostgreSQL behind the same interface for a longer-lived store.

## Why do some statuses need my confirmation?

Four statuses — `manually_invited`, `accepted`, `conversation_started` and
`converted` — assert something that happened on LinkedIn, which this bundle
cannot see. They can only be set from your own confirmation, and attempting to
set one without it is refused. Recording them from inference would make the
whole funnel fiction, and the funnel is the thing you would make decisions
from.

## Does it work without any configuration?

Yes. It ships with sensible defaults: one generic active ICP, a balanced
scoring profile, and the full safety layer. `python -m lni config-check` lists
exactly what each skill still needs from you. Where a value is missing, a skill
asks rather than inventing one — the package contains no personal data at all,
and a test enforces that `config/profile.yaml` ships blank.

## Which metrics can it not report?

Three, and it says so rather than estimating them: profile visits, followers
gained, and content engagement from new connections. All three live in your own
LinkedIn analytics, and nothing here reads LinkedIn. They are reported as
`unavailable` with the reason and fill in when you supply your own analytics
export. Per-person content attribution is also unavailable, because LinkedIn
does not expose engager identity to a third party.

## Does it estimate missing numbers?

Never, and the setting that would allow it refuses to load. An acceptance rate
from zero invitations is reported as unavailable, not as 0%. A missing month in
a series stays missing. A reader should never have to guess whether a blank
means zero, and an estimated metric in a performance report is a fabricated
one.

## How is this different from other LinkedIn Claude skills?

Most LinkedIn skills in the ecosystem are either content tools — writing posts,
comments and replies — or automation tools that drive a browser or hold a
session cookie. This bundle is neither. It is a research, scoring and
relationship-management layer that writes no content and automates nothing, and
it routes content work to the bundles that already do it well.

## Can I use it alongside other LinkedIn skill bundles?

Yes, and it is designed to. It writes no posts, comments or replies and
optimises no profile, so it does not overlap with content bundles such as
`sergebulaev/linkedin-skills`, nor with company-Page bundles such as
`chandewardnyanesh/linkedin-company-page-skills`. Running all three gives
thirty-seven skills with one overlap of substance, documented on both sides in
the capability gap analysis.

## Which agents does it work with?

Any host that supports the Agent Skills open standard. The skills are plain
Markdown with YAML frontmatter and nothing in them is Claude-specific. Tested
with Claude Code; the same files work in other Agent Skills hosts. An agent
that can also run shell commands gets the real Python engine for scoring,
storage and reporting; one that cannot will still follow the documented
workflows.

## What happens if LinkedIn restricts my account?

The run stops. If you report a warning, a security challenge or a restriction,
every subsequent action refuses until you state the matter is resolved, and the
response says plainly that no workaround will be suggested — not a different
tool, not a slower pace, not a second account. You are pointed at completing
what LinkedIn is asking and at LinkedIn's own appeal route. Nothing in this
bundle touches your account, so the cause lies elsewhere.

## Will it help me pace outreach to stay under LinkedIn's limits?

No. Pacing activity to avoid detection is refused under
`no_detection_evasion`, and the classifier catches the softened phrasings —
"spread these over three days so it looks organic", "how many can I send before
I get flagged", "warm up the account first". If the real question is how much
outreach is sustainable for *you*, state your own weekly capacity and the
shortlist is trimmed to it.

## How does it handle data about other people?

Data minimisation is enforced on import: fields in `privacy.never_store` —
personal email, phone, home address, salary and others — are dropped before
anything is written, and the import report names what was dropped. Every record
carries a source and a verification date. Per-person export and deletion are
supported and cannot be disabled. Records nobody has touched in a year are
surfaced for review rather than deleted silently.

## How do I delete everything it holds about one person?

```bash
python -m lni forget <candidate_id> --approve
```

That removes every record about them across all tables. The audit line
recording the deletion is kept deliberately: it holds no profile fields and it
is the only proof the deletion happened.

## Is it affiliated with LinkedIn?

No. This project is not affiliated with, endorsed by, or connected to LinkedIn
Corporation. "LinkedIn" is a trademark of its owner and is used here only to
describe what the software is for.

## What does it cost?

Nothing. MIT licensed, two Python dependencies, no API keys, no hosted service
and no account to create. The only requirement is a Claude plan that supports
skills if you want to run it as an Agent Skill rather than as a CLI.

## Where do I start?

```bash
git clone https://github.com/chandewardnyanesh/linkedin-network-intelligence.git
cd linkedin-network-intelligence
pip install -r requirements.txt
python -m lni config-check
```

`config-check` ends by telling you what each skill needs from you. That list is
the setup task.
