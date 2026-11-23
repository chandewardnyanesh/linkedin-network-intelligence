"""Funnel metrics and period reports.

The rule that shapes this module: **never invent an unavailable metric.** Every
field is optional, and anything that cannot be sourced from the store is left
`None` with its reason recorded in `FunnelMetrics.unavailable`. A reader should
never have to guess whether a blank means zero.

Three metrics in the Phase-2 list cannot come from this store at all, because
LinkedIn does not expose them to a third party and nothing here reads the
platform: profile visits, followers gained, and content engagement from new
connections. They are reported as unavailable with that reason, and they become
available only when the user supplies their own analytics export.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Optional, Sequence

from .config import Settings
from .crm import NetworkCRM
from .models import (
    ContentAnalytics, CRMStatus, FunnelMetrics, OpportunityStage, PeriodReport,
    PriorityClass, TouchChannel, utcnow,
)

__all__ = ["compute_funnel", "build_report", "period_bounds", "report_id_for"]

#: Metrics that cannot be derived from this store, with the reason.
_PLATFORM_ONLY: dict[str, str] = {
    "profile_visits": (
        "LinkedIn reports profile visits only inside the account's own "
        "analytics. Supply an analytics export and this is filled."
    ),
    "followers_gained": (
        "Follower change is in the account's own analytics, not in this store. "
        "Supply an analytics export and this is filled."
    ),
    "content_engagement_from_new_connections": (
        "Requires joining per-post engager identity to connection dates. "
        "LinkedIn does not expose engager identity to this bundle, and nothing "
        "here reads the platform. Import an engager roster you exported "
        "yourself to fill it."
    ),
}


def period_bounds(period: str, *, end: Optional[date] = None) -> tuple[date, date]:
    """The window a report covers. `end` defaults to today."""
    last = end or date.today()
    if period == "weekly":
        return last - timedelta(days=6), last
    if period == "monthly":
        return last - timedelta(days=29), last
    raise ValueError(f"unknown period {period!r}")


def report_id_for(period: str, start: date, end: date) -> str:
    return f"{period}-{start.isoformat()}-to-{end.isoformat()}"


def compute_funnel(
    crm: NetworkCRM,
    settings: Settings,
    start: date,
    end: date,
    *,
    icp_key: Optional[str] = None,
    content: Sequence[ContentAnalytics] = (),
) -> FunnelMetrics:
    """The funnel for a window, from the store alone plus any supplied analytics."""
    unavailable: dict[str, str] = {}

    candidates = crm.all_candidates()
    if icp_key:
        candidates = [c for c in candidates if c.primary_icp_key == icp_key
                      or icp_key in c.secondary_icp_keys]
    ids = {c.candidate_id for c in candidates}

    created = [c for c in candidates if start <= c.created_at.date() <= end]
    researched = len(created)

    # Status transitions inside the window are the funnel's real events: a
    # candidate created in March and invited this week counts this week.
    changes = [
        ch for ch in _all_status_changes(crm)
        if start <= ch.changed_at.date() <= end and ch.candidate_id in ids
    ]
    def moved_to(status: CRMStatus) -> int:
        return len({ch.candidate_id for ch in changes if ch.to_status is status})

    qualified = moved_to(CRMStatus.qualified)
    shortlisted = moved_to(CRMStatus.shortlisted)
    invited = moved_to(CRMStatus.manually_invited)
    accepted = moved_to(CRMStatus.accepted)
    conversations = moved_to(CRMStatus.conversation_started)
    leads = moved_to(CRMStatus.potential_lead)
    quals = moved_to(CRMStatus.qualified_opportunity)

    acceptance_rate: Optional[float] = None
    if invited:
        acceptance_rate = round(min(1.0, accepted / invited), 4)
    else:
        unavailable["acceptance_rate"] = (
            "no invitations were recorded as sent in this window, so there is "
            "no denominator. An acceptance rate from zero invitations would be "
            "a fabricated figure."
        )

    events = [e for e in crm.events_between(start, end) if e.candidate_id in ids]
    meaningful = sum(1 for e in events if e.substantive)

    relevant_connections: Optional[int] = None
    if accepted:
        relevant_connections = len({
            ch.candidate_id for ch in changes if ch.to_status is CRMStatus.accepted
            and _primary_icp_is_active(crm, ch.candidate_id, settings)
        })
    else:
        unavailable["relevant_connections_gained"] = (
            "no acceptances recorded in this window"
        )

    meetings = sum(1 for e in events if e.channel in (TouchChannel.meeting, TouchChannel.call))
    if not events:
        unavailable["discovery_meetings"] = (
            "no interactions recorded in this window. Meetings are counted from "
            "interactions you log, so an empty log reads as unknown, not zero."
        )
        meetings = None  # type: ignore[assignment]

    opps = [o for o in crm.opportunities() if o.candidate_id in ids
            and start <= o.updated_at.date() <= end]
    business_opportunities = len(opps) if opps else 0

    by_icp: dict[str, int] = {}
    for c in created:
        key = c.primary_icp_key or "unclassified"
        by_icp[key] = by_icp.get(key, 0) + 1

    followers = None
    profile_visits = None
    engagement_from_new = None
    if content:
        gains = [p.followers_gained for p in content
                 if p.followers_gained is not None
                 and p.published_on and start <= p.published_on <= end]
        if gains:
            followers = sum(gains)
        views = [p.profile_views_attributed for p in content
                 if p.profile_views_attributed is not None
                 and p.published_on and start <= p.published_on <= end]
        if views:
            profile_visits = sum(views)
    for name, value in (("followers_gained", followers),
                        ("profile_visits", profile_visits),
                        ("content_engagement_from_new_connections", engagement_from_new)):
        if value is None:
            unavailable[name] = _PLATFORM_ONLY[name]

    return FunnelMetrics(
        profiles_researched=researched,
        qualified_candidates=qualified or None if not created else qualified,
        candidates_by_icp=by_icp,
        invitations_manually_sent=invited,
        invitations_accepted=accepted,
        acceptance_rate=acceptance_rate,
        relevant_connections_gained=relevant_connections,
        meaningful_interactions=meaningful if events else None,
        content_engagement_from_new_connections=engagement_from_new,
        profile_visits=profile_visits,
        followers_gained=followers,
        qualified_leads=leads or None if not changes else leads,
        discovery_meetings=meetings,
        business_opportunities=business_opportunities,
        unavailable=unavailable,
    )


def _all_status_changes(crm: NetworkCRM):
    from .models import StatusChange

    rows = crm.db.query("SELECT payload FROM status_changes")
    return [StatusChange.model_validate_json(r[0]) for r in rows]


def _primary_icp_is_active(crm: NetworkCRM, candidate_id: str,
                           settings: Settings) -> bool:
    c = crm.get(candidate_id)
    if c is None or not c.primary_icp_key:
        return False
    return any(i.key == c.primary_icp_key and i.active for i in settings.icps)


def build_report(
    crm: NetworkCRM,
    settings: Settings,
    *,
    period: Optional[str] = None,
    end: Optional[date] = None,
    content: Sequence[ContentAnalytics] = (),
) -> PeriodReport:
    """A weekly or monthly report, with per-ICP breakdown and stated limits."""
    period = period or settings.reporting.default_period
    start, finish = period_bounds(period, end=end)
    metrics = compute_funnel(crm, settings, start, finish, content=content)

    per_icp: dict[str, FunnelMetrics] = {}
    for icp in settings.active_icps:
        per_icp[icp.key] = compute_funnel(
            crm, settings, start, finish, icp_key=icp.key, content=content
        )

    notes = _audience_quality_notes(crm, settings)
    improvements = _improvements(metrics, settings, crm)
    limits = _limits(metrics, settings, content)

    return PeriodReport(
        report_id=report_id_for(period, start, finish),
        period=period,  # type: ignore[arg-type]
        period_start=start,
        period_end=finish,
        metrics=metrics,
        icp_performance=per_icp,
        audience_quality_notes=notes,
        recommended_improvements=improvements,
        attribution_limits=limits,
    )


def _audience_quality_notes(crm: NetworkCRM, settings: Settings) -> list[str]:
    counts = crm.status_counts()
    total = sum(counts.values())
    if not total:
        return ["The store is empty, so there is nothing to assess."]
    notes = [f"{total} records in the store: " + ", ".join(
        f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
    )]
    accepted = counts.get("accepted", 0) + counts.get("engaged", 0)
    if accepted:
        active_icps = {i.key for i in settings.active_icps}
        on_icp = sum(
            1 for c in crm.filter(status=[CRMStatus.accepted, CRMStatus.engaged], limit=1000)
            if c.primary_icp_key in active_icps
        )
        notes.append(
            f"{on_icp} of {accepted} accepted or engaged connections carry an "
            f"active ICP classification. The rest are either unclassified or "
            f"matched an ICP you have since switched off."
        )
    stale = len([c for c in crm.all_candidates() if c.needs_verification])
    if stale:
        notes.append(
            f"{stale} record(s) have never been verified or are past the "
            f"{settings.provenance.stale_after_days}-day staleness window."
        )
    return notes


def _improvements(metrics: FunnelMetrics, settings: Settings,
                  crm: NetworkCRM) -> list[str]:
    out: list[str] = []
    target = settings.workflow.weekly_research_target
    researched = metrics.profiles_researched or 0
    if researched < target * 0.5:
        out.append(
            f"Research volume was {researched} against a target of {target}. "
            f"Either the target is wrong for the time you have, or the week got "
            f"away — both are worth deciding deliberately rather than drifting."
        )
    if metrics.invitations_manually_sent == 0:
        out.append(
            "No invitations were recorded as sent. If you did send some, tell me "
            "which and I will record them; the funnel below the invitation stage "
            "is blank until then."
        )
    elif metrics.acceptance_rate is not None and metrics.acceptance_rate < 0.3:
        out.append(
            f"Acceptance rate was {metrics.acceptance_rate:.0%}. On this bundle's "
            f"model that is usually a note problem rather than a targeting "
            f"problem: a note with no specific shared reason reads as a template. "
            f"Worth reviewing the drafts that were declined."
        )
    if metrics.meaningful_interactions in (0, None):
        out.append(
            "No substantive interactions are logged for this window. Acceptances "
            "without conversations are a list, not a network."
        )
    shortlist_ready = len(crm.filter(status=[CRMStatus.qualified], limit=500))
    if shortlist_ready > settings.workflow.shortlist_size * 2:
        out.append(
            f"{shortlist_ready} candidates are sitting at 'qualified'. The "
            f"shortlist is the bottleneck, not the research — work the queue "
            f"down before adding to it."
        )
    if not out:
        out.append("Nothing in this window suggests a change of approach.")
    return out


def _limits(metrics: FunnelMetrics, settings: Settings,
            content: Sequence[ContentAnalytics]) -> list[str]:
    limits = [
        "Every figure here comes from records you confirmed. Nothing is read "
        "from LinkedIn, so the funnel is only as complete as what you told me.",
    ]
    for name, reason in metrics.unavailable.items():
        limits.append(f"`{name}` is unavailable: {reason}")
    if not content:
        limits.append(
            "No content analytics were supplied, so nothing connects posting to "
            "network growth in this report."
        )
    limits.append(
        "Acceptance is attributed to the invitation, which is the only link "
        "this store holds. In practice a profile view, a comment you left "
        "weeks earlier, or a mutual connection may have done the work."
    )
    return limits
