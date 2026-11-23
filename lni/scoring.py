"""The configurable 100-point scoring engine.

Six components, weights from `scoring.yaml`, evidence on every point. The
engine's three disciplines, enforced in code rather than documented as advice:

* **Abstention.** A component with no inputs scores zero and records that it
  abstained. It never scores a midpoint. A midpoint is a guess that reads like
  a measurement, and it is the single easiest way for a scoring system to
  become fiction.
* **Evidence.** The `ComponentScore` model rejects points above zero with no
  evidence behind them, so an unevidenced score cannot be built.
* **Follower count is capped.** Audience size can contribute at most
  `follower_subscore_cap` of the influence component and can never, alone,
  move a candidate between priority classes.

Exclusion beats score: a candidate matching any ICP exclusion criterion is
`excluded`, whatever the arithmetic says, and the criterion is recorded
verbatim so the user can see which rule fired.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Optional, Sequence

from .config import Settings
from .models import (
    Candidate, CandidateScore, ComponentScore, Confidence, Evidence,
    ICPDefinition, PriorityClass, PropensityAssessment, PropensityBand,
    SourceProvenance,
)
from .propensity import ObservedSignal, assess as assess_propensity

__all__ = ["ScoringInput", "ActivityFact", "InfluenceFacts", "score_candidate",
           "icp_fit", "rank"]


@dataclass
class ActivityFact:
    """One piece of observable activity, with its date and source."""

    what: str
    occurred_on: date
    source: SourceProvenance


@dataclass
class InfluenceFacts:
    """What the person demonstrably does, plus audience size if known.

    `followers` is deliberately last and deliberately capped. It is the field
    most people reach for and the least informative.
    """

    publishes_regularly: bool = False
    speaks_at_events: bool = False
    maintains_something_used: bool = False
    cited_by_others: bool = False
    visible_decision_scope: bool = False
    followers: Optional[int] = None
    source: Optional[SourceProvenance] = None

    @property
    def demonstrated_count(self) -> int:
        return sum([
            self.publishes_regularly, self.speaks_at_events,
            self.maintains_something_used, self.cited_by_others,
            self.visible_decision_scope,
        ])


@dataclass
class ScoringInput:
    """Everything the engine needs. Anything absent makes a component abstain."""

    candidate: Candidate
    icps: Sequence[ICPDefinition] = ()
    engagement_signals: Sequence[ObservedSignal] = ()
    activity: Sequence[ActivityFact] = ()
    influence: Optional[InfluenceFacts] = None
    candidate_topics: Sequence[str] = ()
    opportunity_score: Optional[float] = None
    opportunity_evidence: Sequence[Evidence] = ()
    matched_exclusion: Optional[str] = None
    propensity: Optional[PropensityAssessment] = None


# ------------------------------------------------------------- ICP fit ---


def _norm(values: Iterable[str]) -> set[str]:
    return {v.lower().strip() for v in values if v and v.strip()}


def _overlap(a: Iterable[str], b: Iterable[str]) -> int:
    """Substring-tolerant overlap: 'VP Operations' matches 'Operations'."""
    left, right = _norm(a), _norm(b)
    hits = 0
    for x in left:
        if any(x in y or y in x for y in right):
            hits += 1
    return hits


def icp_fit(candidate: Candidate, icp: ICPDefinition) -> tuple[float, list[str], Optional[str]]:
    """Fit of one candidate to one ICP, as (0..1, reasons, matched exclusion).

    Only dimensions the ICP actually specifies are scored, and only dimensions
    the candidate actually has are counted. An ICP that names three things and
    a candidate who matches two of three scores 0.67 — rather than 0.22 against
    nine dimensions the ICP never asked about.
    """
    haystack = " ".join(filter(None, [
        candidate.professional_title, candidate.company, candidate.industry,
        candidate.notes, " ".join(candidate.tags),
    ])).lower()
    unchecked: list[str] = []
    for criterion in icp.exclusion_criteria:
        # Only a literal, specific phrase auto-excludes. Exclusion criteria are
        # usually judgements ("sells a competing service rather than operating"),
        # and guessing them from keyword overlap would reject good candidates
        # silently — the one failure mode nobody notices. A criterion the engine
        # cannot check is surfaced for the human instead of being guessed at.
        phrase = criterion.lower().strip()
        if len(phrase) > 6 and phrase in haystack:
            return 0.0, [], criterion
        unchecked.append(criterion)

    if _norm(icp.title_exclusions) and candidate.professional_title:
        for bad in _norm(icp.title_exclusions):
            if bad in candidate.professional_title.lower():
                return 0.0, [], f"title exclusion: {bad}"

    checks: list[tuple[bool, bool, str]] = []  # (specified, matched, reason)

    if icp.job_titles:
        matched = bool(candidate.professional_title) and _overlap(
            icp.job_titles, [candidate.professional_title or ""]
        ) > 0
        checks.append((bool(candidate.professional_title), matched,
                       f"title {candidate.professional_title!r} vs ICP titles"))
    if icp.seniority:
        known = candidate.seniority.value != "unknown"
        checks.append((known, known and candidate.seniority in icp.seniority,
                       f"seniority {candidate.seniority.value}"))
    if icp.industries:
        checks.append((bool(candidate.industry),
                       _overlap(icp.industries, [candidate.industry or ""]) > 0,
                       f"industry {candidate.industry!r}"))
    if icp.company_size_bands:
        checks.append((bool(candidate.company_size_band),
                       candidate.company_size_band in icp.company_size_bands,
                       f"company size {candidate.company_size_band!r}"))
    if icp.geographies:
        checks.append((bool(candidate.geography),
                       _overlap(icp.geographies, [candidate.geography or ""]) > 0,
                       f"geography {candidate.geography!r}"))
    if icp.professional_interests or icp.content_interests:
        pool = list(candidate.tags) + list(candidate.shared_context)
        wanted = list(icp.professional_interests) + list(icp.content_interests)
        checks.append((bool(pool), _overlap(wanted, pool) > 0,
                       "interests from tags and shared context"))

    checkable = [c for c in checks if c[0]]
    if not checkable:
        reasons = ["no checkable dimension: the record is too thin to judge"]
        if unchecked:
            reasons.append(_unchecked_note(unchecked))
        return 0.0, reasons, None
    matched = [c for c in checkable if c[1]]
    fit = len(matched) / len(checkable)
    reasons = [c[2] for c in matched] or ["no dimension matched"]
    if len(checkable) < len(checks):
        reasons.append(
            f"{len(checks) - len(checkable)} ICP dimension(s) not checkable: "
            f"the record is missing those fields"
        )
    if unchecked:
        reasons.append(_unchecked_note(unchecked))
    return fit, reasons, None


def _unchecked_note(criteria: Sequence[str]) -> str:
    """Exclusion criteria that need a human eye, named so they get one."""
    shown = "; ".join(criteria[:3])
    more = f" (+{len(criteria) - 3} more)" if len(criteria) > 3 else ""
    return (
        f"unverifiable exclusion criteria to check by hand: {shown}{more}"
    )


def best_icp(candidate: Candidate, icps: Sequence[ICPDefinition]
             ) -> tuple[Optional[ICPDefinition], float, list[str], Optional[str]]:
    """The ICP this candidate fits best, with ties broken by ICP priority."""
    best: tuple[Optional[ICPDefinition], float, list[str], Optional[str]] = (None, 0.0, [], None)
    for icp in icps:
        fit, reasons, excluded = icp_fit(candidate, icp)
        if excluded:
            return icp, 0.0, reasons, excluded
        better = fit > best[1] or (
            best[0] is not None and fit == best[1] and icp.priority < best[0].priority
        )
        if best[0] is None or better:
            best = (icp, fit, reasons, None)
    return best


# ------------------------------------------------------------ components ---


def _ev(observed: str, source: SourceProvenance, confidence: Confidence) -> Evidence:
    return Evidence(observed=observed, source=source, confidence=confidence)


def _component_icp(inp: ScoringInput, max_points: float
                   ) -> tuple[ComponentScore, Optional[ICPDefinition], Optional[str]]:
    if not inp.icps:
        return (
            ComponentScore(component="icp_relevance", points=0.0, max_points=max_points,
                           confidence=Confidence.none, abstained=True,
                           rationale="no active ICP is defined, so fit cannot be judged"),
            None, None,
        )
    icp, fit, reasons, excluded = best_icp(inp.candidate, inp.icps)
    if excluded or inp.matched_exclusion:
        return (
            ComponentScore(component="icp_relevance", points=0.0, max_points=max_points,
                           confidence=Confidence.high, abstained=False,
                           rationale=f"excluded by ICP criterion: "
                                     f"{excluded or inp.matched_exclusion}"),
            icp, excluded or inp.matched_exclusion,
        )
    source = inp.candidate.sources[0]
    conf = (Confidence.high if fit >= 0.75 else
            Confidence.medium if fit >= 0.4 else Confidence.low)
    if fit <= 0:
        return (
            ComponentScore(component="icp_relevance", points=0.0, max_points=max_points,
                           confidence=Confidence.low, abstained=False,
                           rationale=f"no ICP dimension matched ({icp.key if icp else 'n/a'})"),
            icp, None,
        )
    return (
        ComponentScore(
            component="icp_relevance", points=round(fit * max_points, 2),
            max_points=max_points, confidence=conf,
            evidence=[_ev(f"ICP {icp.key}: {r}", source, conf) for r in reasons[:3]],
            rationale=f"fit {fit:.2f} against ICP {icp.key!r}",
        ),
        icp, None,
    )


def _component_activity(inp: ScoringInput, settings: Settings, max_points: float,
                        today: date) -> ComponentScore:
    window = settings.scoring.observable_activity.recency_window_days
    live = [a for a in inp.activity if 0 <= (today - a.occurred_on).days < window]
    if not inp.activity:
        return ComponentScore(
            component="observable_activity", points=0.0, max_points=max_points,
            confidence=Confidence.none, abstained=True,
            rationale=f"no activity supplied; nothing observed in the last {window} days",
        )
    if not live:
        return ComponentScore(
            component="observable_activity", points=0.0, max_points=max_points,
            confidence=Confidence.medium, abstained=False,
            rationale=(f"{len(inp.activity)} activity record(s), none inside the "
                       f"{window}-day window — dormant on the evidence available"),
        )
    # Diminishing returns: three visible actions is active; thirty is not ten
    # times as active.
    ratio = min(1.0, len(live) / 3.0)
    conf = Confidence.high if len(live) >= 2 else Confidence.medium
    return ComponentScore(
        component="observable_activity", points=round(ratio * max_points, 2),
        max_points=max_points, confidence=conf,
        evidence=[_ev(f"{a.what} on {a.occurred_on.isoformat()}", a.source, conf)
                  for a in sorted(live, key=lambda x: x.occurred_on, reverse=True)[:3]],
        rationale=f"{len(live)} observable action(s) inside {window} days",
    )


def _component_engagement(inp: ScoringInput, settings: Settings, max_points: float,
                          today: date) -> tuple[ComponentScore, PropensityAssessment]:
    """Delegates to `lni.propensity`. One engine, two skills."""
    assessment = inp.propensity or assess_propensity(
        inp.candidate, inp.engagement_signals, settings, icps=inp.icps, today=today
    )
    if assessment.band is PropensityBand.insufficient_evidence:
        return (
            ComponentScore(
                component="engagement_signals", points=0.0, max_points=max_points,
                confidence=Confidence.none, abstained=True,
                rationale="no engagement signal inside the recency window",
            ),
            assessment,
        )
    raw = assessment.raw_score or 0.0
    return (
        ComponentScore(
            component="engagement_signals", points=round(raw * max_points, 2),
            max_points=max_points, confidence=assessment.confidence,
            evidence=list(assessment.observations)[:3],
            rationale=f"propensity {assessment.band.value} (normalised {raw:.2f})",
        ),
        assessment,
    )


def _component_topics(inp: ScoringInput, settings: Settings, max_points: float
                      ) -> ComponentScore:
    user_topics = settings.profile.content_topics
    if not user_topics:
        return ComponentScore(
            component="topic_alignment", points=0.0, max_points=max_points,
            confidence=Confidence.none, abstained=True,
            rationale="profile.content_topics is empty, so alignment cannot be judged",
        )
    pool = list(inp.candidate_topics) or list(inp.candidate.tags)
    if not pool:
        return ComponentScore(
            component="topic_alignment", points=0.0, max_points=max_points,
            confidence=Confidence.none, abstained=True,
            rationale="nothing known about what this person engages with",
        )
    hits = _overlap(user_topics, pool)
    need = settings.scoring.topic_alignment.min_overlap_for_points
    if hits < need:
        return ComponentScore(
            component="topic_alignment", points=0.0, max_points=max_points,
            confidence=Confidence.medium, abstained=False,
            rationale=f"{hits} topic overlap(s), below the {need} required",
        )
    ratio = min(1.0, hits / max(1, min(len(user_topics), 3)))
    source = inp.candidate.sources[0]
    return ComponentScore(
        component="topic_alignment", points=round(ratio * max_points, 2),
        max_points=max_points, confidence=Confidence.medium,
        evidence=[_ev(f"{hits} topic overlap with the user's own topics: "
                      f"{', '.join(sorted(_norm(pool))[:4])}", source, Confidence.medium)],
        rationale=f"{hits} overlap(s) with profile.content_topics",
    )


def _component_influence(inp: ScoringInput, settings: Settings, max_points: float
                         ) -> ComponentScore:
    facts = inp.influence
    if facts is None:
        return ComponentScore(
            component="professional_influence", points=0.0, max_points=max_points,
            confidence=Confidence.none, abstained=True,
            rationale="no influence facts supplied",
        )
    cap = settings.scoring.professional_influence.follower_subscore_cap
    demonstrated_share = 1.0 - cap
    n = facts.demonstrated_count
    demonstrated = min(1.0, n / 3.0) * demonstrated_share

    follower_part = 0.0
    follower_note = None
    if facts.followers is not None:
        # Log-scaled and capped. 500 followers and 50,000 followers differ by
        # less here than one published talk does, which is the intent.
        import math

        follower_part = min(1.0, math.log10(max(1, facts.followers)) / 5.0) * cap
        follower_note = (
            f"{facts.followers} followers, contributing at most "
            f"{cap:.0%} of this component"
        )

    total = round((demonstrated + follower_part) * max_points, 2)
    if total <= 0:
        return ComponentScore(
            component="professional_influence", points=0.0, max_points=max_points,
            confidence=Confidence.medium, abstained=False,
            rationale="no demonstrated influence signal and no audience figure",
        )
    source = facts.source or inp.candidate.sources[0]
    evidence = []
    labels = [
        (facts.publishes_regularly, "publishes regularly on the topic"),
        (facts.speaks_at_events, "speaks at industry events"),
        (facts.maintains_something_used, "maintains or contributes to something others use"),
        (facts.cited_by_others, "cited or quoted by others in the field"),
        (facts.visible_decision_scope, "holds a role with visible decision scope"),
    ]
    for present, label in labels:
        if present:
            evidence.append(_ev(label, source, Confidence.medium))
    if follower_note:
        evidence.append(_ev(follower_note, source, Confidence.low))
    return ComponentScore(
        component="professional_influence", points=total, max_points=max_points,
        confidence=Confidence.medium if n else Confidence.low,
        evidence=evidence[:4],
        rationale=(f"{n} demonstrated signal(s)"
                   + (f" plus a capped audience contribution" if follower_note else "")),
    )


def _component_opportunity(inp: ScoringInput, settings: Settings, max_points: float
                           ) -> ComponentScore:
    if max_points == 0:
        return ComponentScore(
            component="business_opportunity", points=0.0, max_points=0.001,
            confidence=Confidence.none, abstained=True,
            rationale="this scoring profile assigns the component no weight",
        )
    if inp.opportunity_score is None:
        return ComponentScore(
            component="business_opportunity", points=0.0, max_points=max_points,
            confidence=Confidence.none, abstained=True,
            rationale="no opportunity assessment on record",
        )
    usable = [e for e in inp.opportunity_evidence if e.usable]
    if not usable:
        return ComponentScore(
            component="business_opportunity", points=0.0, max_points=max_points,
            confidence=Confidence.none, abstained=True,
            rationale=("an opportunity score was supplied with no usable signal "
                       "behind it; scoring zero rather than trusting the number"),
        )
    ratio = max(0.0, min(1.0, inp.opportunity_score / 100.0))
    conf = min(
        [e.confidence for e in usable] + [settings.business_services.max_confidence_without_user_confirmation],
        key=lambda c: c.weight,
    )
    return ComponentScore(
        component="business_opportunity", points=round(ratio * max_points, 2),
        max_points=max_points, confidence=conf, evidence=usable[:3],
        rationale=f"opportunity relevance {inp.opportunity_score:.0f}/100",
    )


# -------------------------------------------------------------- scoring ---


def _priority_for(total: float, confidence: Confidence, abstentions: int,
                  settings: Settings) -> PriorityClass:
    limit = settings.scoring.max_abstentions_before_low_confidence
    capped = abstentions > limit
    for band in settings.scoring.priority_bands:
        if total >= band.min_total and confidence.weight >= band.min_confidence.weight:
            if capped and band.band_class in (
                PriorityClass.priority_1, PriorityClass.priority_2, PriorityClass.priority_3
            ):
                return PriorityClass.monitor
            return band.band_class
    return PriorityClass.monitor


def _overall_confidence(components: Sequence[ComponentScore], settings: Settings
                        ) -> Confidence:
    """Weighted by the points each component actually contributed.

    A high-confidence component worth 2 points does not make an otherwise
    unsupported score confident.
    """
    scored = [c for c in components if not c.abstained and c.points > 0]
    if not scored:
        return Confidence.none
    abstentions = sum(1 for c in components if c.abstained)
    weight = sum(c.points for c in scored)
    if weight <= 0:
        return Confidence.none
    avg = sum(c.confidence.weight * c.points for c in scored) / weight
    if abstentions > settings.scoring.max_abstentions_before_low_confidence:
        return Confidence.low
    if avg >= 0.8:
        return Confidence.high
    if avg >= 0.5:
        return Confidence.medium
    return Confidence.low


def score_candidate(inp: ScoringInput, settings: Settings,
                    *, today: Optional[date] = None) -> tuple[CandidateScore, PropensityAssessment]:
    """Score one candidate. Returns the score and the propensity behind it."""
    today = today or date.today()
    weights = settings.scoring.active_weights

    icp_component, icp, excluded = _component_icp(inp, weights["icp_relevance"])
    activity = _component_activity(inp, settings, weights["observable_activity"], today)
    engagement, propensity = _component_engagement(
        inp, settings, weights["engagement_signals"], today
    )
    topics = _component_topics(inp, settings, weights["topic_alignment"])
    influence = _component_influence(inp, settings, weights["professional_influence"])
    opportunity = _component_opportunity(inp, settings, weights["business_opportunity"])

    components = [icp_component, activity, engagement, topics, influence, opportunity]
    total = round(sum(c.points for c in components), 2)
    abstentions = sum(1 for c in components if c.abstained)
    confidence = _overall_confidence(components, settings)

    if excluded:
        priority = PriorityClass.excluded
        action = (f"Excluded. The ICP criterion {excluded!r} matched this record. "
                  f"Nothing further unless you disagree with the criterion.")
    else:
        priority = _priority_for(total, confidence, abstentions, settings)
        action = _next_action(priority, propensity, abstentions, inp,
                             icp_points=icp_component.points,
                             icp_max=icp_component.max_points)

    score = CandidateScore(
        candidate_id=inp.candidate.candidate_id,
        total=total,
        components=components,
        priority=priority,
        confidence=confidence,
        recommended_next_action=action,
        excluded_by=excluded,
        weights_profile=settings.scoring.active_profile,
    )
    return score, propensity


def _next_action(priority: PriorityClass, propensity: PropensityAssessment,
                 abstentions: int, inp: ScoringInput,
                 *, icp_points: float = 0.0, icp_max: float = 1.0) -> str:
    good_fit = icp_max > 0 and (icp_points / icp_max) >= 0.75
    if abstentions >= 4 and not good_fit:
        return (
            f"Hold. {abstentions} of 6 components had no inputs, so this score "
            f"says more about the record than the person. Verify the basics "
            f"first: title, company, and whether they have been active at all."
        )
    if abstentions >= 4 and good_fit:
        return (
            f"Strong ICP fit, but nothing observed yet — {abstentions} of 6 "
            f"components had no inputs, so the gap is in what we know, not in "
            f"who they are. Engage on their work for a few weeks, or verify "
            f"their recent activity, then re-score. Do not spend an invitation "
            f"on a record this thin."
        )
    # A strong ICP fit with no engagement evidence is a different situation
    # from a weak fit, and deserves a different instruction: the gap is in what
    # we know, not in who they are.
    base = {
        PriorityClass.priority_1: (
            "Shortlist now. Prepare a connection recommendation and an "
            "invitation draft for your review."
        ),
        PriorityClass.priority_2: (
            "Shortlist if there is room this week. Worth one engagement touch "
            "first."
        ),
        PriorityClass.priority_3: (
            "Keep in the pool. Engage on their work and re-score when there is "
            "a signal."
        ),
        PriorityClass.monitor: (
            "Monitor only. Not enough evidence to spend an invitation on yet."
        ),
        PriorityClass.excluded: "Excluded.",
    }[priority]
    if propensity.recommended_approach and priority in (
        PriorityClass.priority_1, PriorityClass.priority_2
    ):
        return base + " " + propensity.recommended_approach
    if priority is PriorityClass.monitor and good_fit:
        return (
            "Strong ICP fit, but nothing observed yet — the gap is in what we "
            "know, not in who they are. Engage on their work for a few weeks, "
            "or verify their recent activity, then re-score. Do not spend an "
            "invitation on a record this thin."
        )
    return base


def rank(scores: Iterable[CandidateScore], *, limit: Optional[int] = None
         ) -> list[CandidateScore]:
    """Order by priority class, then total, then confidence.

    Priority first rather than raw total, so a confident 58 outranks a
    barely-supported 64.
    """
    order = {
        PriorityClass.priority_1: 0, PriorityClass.priority_2: 1,
        PriorityClass.priority_3: 2, PriorityClass.monitor: 3,
        PriorityClass.excluded: 4,
    }
    out = sorted(scores, key=lambda s: (order[s.priority], -s.total,
                                        -s.confidence.weight))
    return out[:limit] if limit else out
