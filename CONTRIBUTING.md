# Contributing

Contributions welcome. A few things are settled, and knowing which saves
everyone time.

## Not open to change

These are the reason the bundle exists. A pull request that weakens one will be
declined with thanks:

1. **No sender, no scheduler, no scraper, no browser driver.** Not behind a
   flag, not opt-in, not "for testing".
2. **The eleven prohibited rules.** Adding one is welcome. Removing or
   narrowing one is not.
3. **Abstention over imputation.** A component with no inputs scores zero and
   says so. No midpoints, no defaults, no "reasonable assumptions".
4. **No invented metric.** Unavailable is reported as unavailable, with a
   reason.
5. **Observations and predictions in separate fields.**
6. **Subject export and deletion.** Cannot be disabled.
7. **No personal data in the package.** `config/profile.yaml` ships blank, and
   a test enforces it.

If you think one of these is wrong, open an issue and make the argument. That is
a more interesting conversation than a declined pull request.

## Good contributions

- **More prohibited phrasings.** The classifier catches what it has been shown.
  If you find a wording that gets past it, that is the most valuable issue you
  can file — and a test case is better still.
- **Importer formats.** LinkedIn's exports change, and everyone's spreadsheet is
  different. New header aliases in `COLUMN_ALIASES` cost nothing and help
  immediately.
- **Scoring profiles.** The three that ship cover common cases, not all of them.
  A well-reasoned fourth, with a description saying who it is for, is useful.
- **Honest limitations.** If a document overclaims, say so. A document that
  promises more than the code does is a bug.
- **Localisation of normalisation.** `normalise_name` and `normalise_company`
  handle Latin scripts and a list of legal suffixes. Both are incomplete.

## How to work on it

```bash
git clone https://github.com/chandewardnyanesh/linkedin-network-intelligence.git
cd linkedin-network-intelligence
pip install -r requirements-dev.txt
python -m pytest
```

All 444 tests should pass before you start, and before you open a pull request.

### Conventions

- **Python 3.12+, typed, pydantic for anything that crosses a boundary.** If a
  rule can be a validator, make it one: "a score with no evidence cannot be
  built" is a stronger guarantee than a comment saying not to.
- **No new runtime dependencies** without a reason in the pull request. Two is
  the current count and it is a feature.
- **A rule lives in one module.** If two skills need it, one module owns it and
  both cite it. Two copies of a rule is how two paths quietly stop agreeing.
- **Tests that would fail if the behaviour regressed.** A test asserting that a
  function returns something is not a test.
- **Comments explain why, not what.** The code says what.

### If you change a skill document

`tests/test_instruction_integrity.py` checks that documents and code agree:
every rule id cited exists, every CLI command cited exists, every cited file is
present, every handoff contract holds on both sides, and required sections are
there. Run it.

Required sections in every `SKILL.md`: when to use, required inputs, workflow,
output format, failure handling, safety requirements, examples.

### If you add a skill

- Its own directory under `skills/`, with a `SKILL.md` whose `name` matches the
  directory.
- An entry in `SKILL_REQUIREMENTS` in `lni/config.py`, even if empty — a test
  asserts the sets match.
- A route to it from the root `SKILL.md`.
- An honest gap analysis: if it overlaps something in either upstream bundle,
  say so in `docs/CAPABILITY_GAP_ANALYSIS.md` and scope it down.

### Commit messages

What changed and why. If it fixes a case the classifier missed, quote the
phrasing.

## Reporting a safety gap

A prohibited action the classifier permits, or any route to acting on LinkedIn
from this bundle, is a security issue rather than a bug. See `SECURITY.md`.

## Licence

MIT. By contributing you agree your contribution is licensed the same way.
