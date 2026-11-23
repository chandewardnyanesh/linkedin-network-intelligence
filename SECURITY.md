# Security

## What counts as a security issue here

This is not ordinary software. Its security properties are mostly about what it
refuses to do, so the issues worth reporting urgently are:

1. **A prohibited action the classifier permits.** A phrasing that gets a
   refusal-worthy request past `lni/safety.py`. The most valuable report you can
   send.
2. **Any route to acting on LinkedIn** from this bundle — sending, liking,
   following, scraping, driving a browser — whether through the code, a
   dependency, or a way of using the CLI nobody intended.
3. **A way to make imported content direct the agent.** A CSV, export or page
   whose contents cause an action rather than being treated as data.
4. **Leakage of records about people**: an export path that bypasses the
   approval gate, a deletion that leaves data behind, a field stored that
   `privacy.never_store` forbids.
5. **A configuration that loads while relaxing a control that cannot be
   relaxed.**
6. **Credentials or personal data in the repository.** Tests check for both, so
   this would mean the tests have a gap too.

Ordinary bugs — a wrong score, a mis-parsed CSV, a crash — are issues, not
security reports. File them normally.

## How to report

Open a private security advisory on the GitHub repository
(`Security` → `Report a vulnerability`), or open a public issue if the matter is
clearly not sensitive.

Include: what you did, what happened, what you expected, and a phrasing or file
that reproduces it. For a classifier gap, the exact wording is the report.

## What to expect

A single-maintainer project, so: acknowledgement when I see it, a fix for
anything in categories 1 to 5 prioritised above features, and credit in
`CHANGELOG.md` unless you would rather not be named.

## Scope

**In scope:** the code in `lni/`, the configuration in `config/`, the skill
documents in `skills/`, and the tests.

**Out of scope:**

- LinkedIn itself. Report platform vulnerabilities to LinkedIn.
- What another tool on your machine does. This bundle cannot stop a scraper in
  another tab; it governs its own behaviour.
- The accuracy of a score or a propensity band. Those are modelling choices,
  documented as such, and arguable on their merits in an issue.
- Whether your sources are what you said they are. The provenance field records
  what you told it.

## Handling your own data safely

- **Keep a filled configuration outside the repository**, in `$LNI_CONFIG_DIR`.
  A filled `icps.yaml` or `business_services.yaml` holds your positioning,
  target accounts and qualification logic.
- **The store holds records about other people.** `data/` and `*.csv` are
  gitignored for that reason. Treat an export the way you would treat a contact
  list, because that is what it is.
- **No credentials are needed and none should be added.** There is no LinkedIn
  credential in this bundle and no environment variable to add one. If you hold
  authorised official API access, the DSN-style pattern in `.env.example` is
  the model: environment only, never a file git can carry.
- **PostgreSQL DSNs go in the environment.** `storage.postgres_dsn_env` names
  the variable; the value never belongs in YAML.

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |

Pre-1.0: fixes land on the latest release, and there are no backports.
