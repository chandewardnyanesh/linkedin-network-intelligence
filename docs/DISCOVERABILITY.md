# Discoverability

What was done so that someone with this problem finds this project — across
classic search, answer engines and generative engines — and the few steps that
can only be done in the GitHub interface.

Written down because SEO work that nobody can audit tends to rot.

## Who this is aimed at

The person searching is not looking for "a Claude skill". They have a problem:

| They search | They want |
|---|---|
| "linkedin crm open source" | Somewhere to track who they contacted |
| "linkedin automation without getting banned" | Reassurance, and usually a different tool than the one they were about to use |
| "is automating linkedin connection requests against terms of service" | A straight answer |
| "how to score linkedin connections" | A framework |
| "claude code skills linkedin" | The ecosystem |
| "linkedin skill without session cookie" | Exactly this project |
| "ideal connection profile" | A definition and a template |
| "linkedin outreach tracking spreadsheet alternative" | A CRM |

The content is written to answer those questions directly rather than to
describe the software and hope.

## The positioning, which is also the SEO strategy

Almost every LinkedIn skill and tool in this ecosystem **automates**: several
hold a `li_at` session cookie or drive a logged-in browser. This bundle
deliberately does not.

That is a real differentiator and a real search gap, so it is the first thing
every surface says — repository description, README headline, Pages title,
`llms.txt` summary. A reader deciding between tools gets the distinction in one
line, and an answer engine summarising "safe LinkedIn outreach tooling" has an
unambiguous sentence to quote.

## Three surfaces, three mechanisms

### 1. Classic search, and GitHub's own search

| Lever | Where |
|---|---|
| Repository description, front-loaded, 350-char limit | `scripts/setup-github.sh` |
| 20 repository topics | `scripts/setup-github.sh` |
| Keyword-bearing H1 and first paragraph (becomes the SERP snippet) | `README.md` |
| Question-shaped H2 headings | `README.md`, `docs/FAQ.md` |
| A Pages site with `<title>`, meta description, canonical, Open Graph, Twitter card | `docs/index.html` |
| `sitemap.xml` and `robots.txt` | `docs/` |
| `CITATION.cff` — picked up by GitHub and by citation surfaces | repository root |
| A keyword line in small print at the end of the README | `README.md` |

GitHub topics matter more than they look: they drive GitHub's own search *and*
they are read by the directories in §4.

### 2. Answer engines — Google AI Overviews, Perplexity, Bing Copilot

These extract passages. The content is shaped so a passage can be lifted
without losing its meaning:

- **Question-shaped headings** that match real queries, with the answer in the
  first 40–60 words under the heading.
- **26 FAQ entries** in `docs/FAQ.md`, each self-contained.
- **`FAQPage` structured data** in `docs/index.html` with 12 questions, each
  also rendered visibly on the page — schema that does not match the visible
  content is worse than no schema.
- **Comparison tables**, which extract unusually well and are what a reader
  comparing tools actually wants.
- **Definitions near the top** of each document.

### 3. Generative engines — ChatGPT, Claude, Gemini

Different problem: the model has to be able to describe the project accurately
from a chunk, and recommend it for the right job.

- **`llms.txt`** at the repository root and on the Pages site, following the
  [llmstxt.org](https://llmstxt.org/) convention: a markdown map with a summary
  and one annotated link per document.
- **`rel="describedby"` and `rel="alternate" type="text/markdown"`** on the
  Pages site pointing at `llms.txt`, as the v2 specification recommends.
- **Chunk-safe writing.** Each paragraph makes sense alone: few pronouns
  reaching back across paragraphs, and the project named rather than called
  "it" at the start of a section.
- **Explicit "use this when / this is not for" statements**, so a model
  choosing between tools has something to choose on.
- **Numbers stated plainly** — twelve skills, eleven rules, 444 tests, 100-point
  framework — because specifics survive summarisation and vague claims do not.

### 4. The skill directories, which are the biggest single lever

A sizeable ecosystem indexes GitHub skill repositories automatically and ranks
well for exactly these queries: `claudemarketplaces.com`, `skillsllm.com`,
`claudeskills.info`, `skills.sh`, `awesomeskills.dev`, `tessl.io/registry`,
`hermesatlas.com`, `awesome.ecosyste.ms`, `trendshift.io`, and others.

They crawl on their own; what they extract is what matters:

| What they read | What was done |
|---|---|
| Repository description and topics | Set by `scripts/setup-github.sh` |
| `README.md`, including install commands | Install blocks for the plugin marketplace, manual copy, and `npx skills add` |
| `.claude-plugin/plugin.json` | Present, with a keyword-bearing description |
| Each `skills/*/SKILL.md` frontmatter `description` | All twelve written as trigger descriptions, 120–1024 chars, each saying when to use the skill |
| Licence and stars | MIT, declared in both `LICENSE` and every `SKILL.md` |
| A passing CI badge | `.github/workflows/ci.yml` runs the suite, the evals and the secrets scan on every push |

Nothing needs submitting to them. The repository just has to be legible.

## What cannot be automated from here

Four things need the GitHub interface or an account elsewhere:

1. **Create the repository.** Public, named `linkedin-network-intelligence`.
2. **Run `sh scripts/setup-github.sh`** after the first push, which sets the
   description, homepage and topics and turns on Pages from `/docs`. All three
   can also be set by hand in Settings.
3. **Submit the sitemap once** to [Google Search
   Console](https://search.google.com/search-console) and [Bing Webmaster
   Tools](https://www.bing.com/webmasters). Bing matters more than its market
   share suggests, because it feeds several answer engines.
4. **Decide whether to announce it.** A post that names the problem rather than
   the software is what gets linked, and inbound links are still what moves
   classic rankings.

## What was deliberately not done

- **No keyword stuffing.** The keyword line at the end of the README is one
  line of small print, and every heading reads as a question a person would
  actually ask. Prose written for a crawler reads badly to the reader who
  arrives, which costs more than the ranking gains.
- **No invented metrics or claims.** Test counts and feature counts are real
  and verifiable by running the suite. An answer engine that finds one
  overstated claim has no way to trust the rest.
- **No comparison that misrepresents the alternatives.** The comparison table
  says content bundles write content and automation tools automate, which is
  what they do and what they are good at. The honest version of that table is
  more persuasive than a rigged one.
- **No `llms-full.txt`.** The documentation is large enough that a single
  concatenated file would be mostly noise. `llms.txt` points at the documents
  instead, which is what the specification prefers when the content is
  substantial.

## Keeping it working

| When | What |
|---|---|
| A document is added or renamed | Update `llms.txt` and `docs/sitemap.xml` |
| A skill is added | Update the README table, `llms.txt`, and the count in `.claude-plugin/plugin.json` — a test asserts the manifest's count matches reality |
| The test count changes | Update the README badge and `docs/IMPLEMENTATION_REPORT.md` |
| Quarterly | Check what the Pages site actually ranks for, and whether the FAQ answers the questions people are now asking |
