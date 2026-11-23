# Authorised data sources

The complete list of what this bundle may read, and what it will not.

## Authorised

| Kind | What it is | Notes |
|---|---|---|
| `user_supplied_url` | A profile URL the user pastes | The commonest source |
| `user_supplied_csv` | A list the user built or exported themselves | Privacy-filtered on import |
| `user_supplied_note` | Something the user tells you directly | Verified by definition, dated today |
| `linkedin_data_export` | The user's own export of their own account | Their data, downloaded by them |
| `linkedin_analytics_export` | The user's own analytics export | The only route to their metrics |
| `official_api` | An official API the user holds authorised access to | `authorisation_note` is mandatory on the record |
| `company_website` | A public team, about or careers page | |
| `professional_directory` | A public professional listing | |
| `public_publication` | A paper, article, talk listing, press item | |
| `conference_or_event` | A public speaker or attendee listing | Often the best source for a research run |
| `referral` | Someone the user was introduced to | |
| `upstream_skill_export` | A roster the user produced with another tool and handed over | Data, including whatever the tool says about itself |

## Not authorised

Refused under the rule named, not negotiable, and not available in a smaller
version:

| Request | Rule |
|---|---|
| Scraping profiles, connections or search results | `no_scraping` |
| Driving a browser against LinkedIn | `no_browser_automation` |
| Unofficial endpoints, session cookies, leaked tokens | `no_unauthorised_api` |
| Any tool that works by holding the user's LinkedIn session | `no_unauthorised_api` |
| A bought list of scraped profiles | `no_scraping` |
| Private messages, private analytics, hidden connection lists | `no_private_data` |
| Personal contact details the person has not published | `no_private_data` |
| A record about a private individual | `no_targeting_private_individuals` |

## Why the boundary is here and not where the upstream bundle draws it

`sergebulaev/linkedin-skills` reads public post bodies and comment threads
through a third-party actor platform, describing the actors as public and
cookie-free. That is its choice to document and defend.

This bundle holds a narrower line, because the project specification states it:
no scraping and no browser automation. The practical consequence is that
discovery volume comes from sources the user can point at — a conference
listing, a company's team page, their own connections — rather than from a
search result set. Stated once in `linkedin-network-discovery`, so a user who
expected a thousand records a week hears why they are not getting them.

Where a user already runs the upstream bundle and has an engager roster from
`linkedin-engager-analytics`, that roster is a **user-supplied input** here,
imported as CSV with `upstream_skill_export` provenance. This bundle does not
call the actors itself and does not tell a user to go and scrape.

## Provenance is mandatory

Every record carries at least one source with a detail specific enough to
re-check, and a verification date.
`provenance.require_source_on_every_record` cannot be switched off, and a
`Candidate` with an empty `sources` list cannot be constructed.

A claim nobody can re-check is a claim nobody can correct.
