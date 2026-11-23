---
name: Safety gap
about: A prohibited action the classifier permits, or any route to acting on LinkedIn from this bundle
title: "[safety] "
labels: safety
---

**The most valuable report this project can receive.** The classifier matches
phrasings, and a wording nobody anticipated can get past it — that has already
happened once, and the evaluation suite caught it after the unit tests had not.

## The exact wording

Paste the request verbatim. The precise phrasing *is* the report.

```
```

## What happened

What the agent or the CLI did with it.

## What should have happened

Which rule in `config/safety.yaml` should have fired, if you know.

## Reproduce

```bash
python -m lni safety-check "<the wording>"
```

Output:

```
```

---

If the gap is a route to actually acting on LinkedIn — sending, liking,
following, scraping, driving a browser — please use a private security advisory
instead of a public issue. See `SECURITY.md`.
