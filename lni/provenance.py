"""Source records and verification dates.

Phase 5 requires `Source` and `Last verified date` on every candidate record.
The point is not bookkeeping: it is that a claim nobody can re-check is a claim
nobody can correct. These helpers make the right thing the short path.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Optional

from .config import Settings
from .models import Candidate, Evidence, SourceKind, SourceProvenance

__all__ = [
    "user_url", "user_csv", "user_note", "data_export", "analytics_export",
    "company_site", "directory", "official_api", "upstream_skill",
    "stale_candidates", "verification_report", "touch_verification",
]


def _p(kind: SourceKind, detail: str, *, verified: Optional[date] = None,
       authorisation: Optional[str] = None) -> SourceProvenance:
    return SourceProvenance(
        kind=kind, detail=detail,
        last_verified=verified or date.today(),
        authorisation_note=authorisation,
    )


def user_url(url: str) -> SourceProvenance:
    """A profile URL the user supplied. The commonest source in practice."""
    return _p(SourceKind.user_supplied_url, f"profile URL supplied by the user: {url}")


def user_csv(path: str, *, row: Optional[int] = None) -> SourceProvenance:
    detail = f"CSV supplied by the user: {path}"
    if row is not None:
        detail += f" (row {row})"
    return _p(SourceKind.user_supplied_csv, detail)


def user_note(what: str) -> SourceProvenance:
    """Something the user told us directly. Verified by definition, today."""
    return _p(SourceKind.user_supplied_note, f"stated by the user: {what}")


def data_export(path: str) -> SourceProvenance:
    return _p(SourceKind.linkedin_data_export,
              f"the user's own LinkedIn data export: {path}")


def analytics_export(path: str, *, covers: Optional[str] = None) -> SourceProvenance:
    detail = f"the user's own LinkedIn analytics export: {path}"
    if covers:
        detail += f" covering {covers}"
    return _p(SourceKind.linkedin_analytics_export, detail)


def company_site(url: str) -> SourceProvenance:
    return _p(SourceKind.company_website, f"public company website: {url}")


def directory(name: str, *, url: Optional[str] = None) -> SourceProvenance:
    detail = f"professional directory: {name}"
    if url:
        detail += f" ({url})"
    return _p(SourceKind.professional_directory, detail)


def official_api(api_name: str, authorisation: str) -> SourceProvenance:
    """An official API the user holds authorised access to.

    `authorisation` is mandatory and is enforced by the model: a record that
    came from an API has to say under whose authorisation.
    """
    return _p(SourceKind.official_api, f"official API: {api_name}",
              authorisation=authorisation)


def upstream_skill(skill_name: str, *, detail: str = "") -> SourceProvenance:
    """An export the user produced with another skill and handed to this one."""
    text = f"export from {skill_name}, supplied by the user"
    if detail:
        text += f": {detail}"
    return _p(SourceKind.upstream_skill_export, text)


def stale_candidates(candidates: Iterable[Candidate], settings: Settings,
                     *, today: Optional[date] = None) -> list[Candidate]:
    """Candidates whose facts are old enough to need re-checking."""
    cutoff = (today or date.today()) - timedelta(days=settings.provenance.stale_after_days)
    out = []
    for c in candidates:
        if c.last_verified is None or c.last_verified < cutoff:
            out.append(c)
    return out


def touch_verification(candidate: Candidate, *, on: Optional[date] = None) -> Candidate:
    """Record that a candidate's facts were re-checked today.

    Returns a copy. Nothing in this package mutates a record in place, so a
    caller always knows which object it is holding.
    """
    when = on or date.today()
    sources = [s.model_copy(update={"last_verified": when}) for s in candidate.sources]
    return candidate.model_copy(update={"last_verified": when, "sources": sources})


def verification_report(candidates: Iterable[Candidate], settings: Settings,
                        *, today: Optional[date] = None) -> dict:
    """How much of the store is still trustworthy, and what needs a look."""
    items = list(candidates)
    stale = stale_candidates(items, settings, today=today)
    never = [c for c in items if c.last_verified is None]
    by_kind: dict[str, int] = {}
    for c in items:
        for s in c.sources:
            by_kind[s.kind.value] = by_kind.get(s.kind.value, 0) + 1
    return {
        "records": len(items),
        "never_verified": len(never),
        "stale": len(stale),
        "fresh": len(items) - len(stale),
        "stale_after_days": settings.provenance.stale_after_days,
        "sources_by_kind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])),
        "needs_recheck": [c.candidate_id for c in stale][:50],
    }
