"""Engagement propensity: how likely someone is to find the user's work relevant.

This is a prediction, and the module is built so that it cannot be mistaken for
an observation. Three mechanisms:

* The input type `ObservedSignal` carries a date and a source. There is no way
  to feed the engine an engagement that nobody saw.
* With no usable signal the band is `insufficient_evidence` and the confidence
  is `none`. The model layer rejects any other combination, so a confident band
  with no evidence cannot be constructed, let alone stored.
* The output keeps `observations` and `predictions` in separate fields.

`lni.scoring` calls this for its engagement component rather than scoring
engagement a second time of its own. One engine, cited by both skills.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Literal, Optional, Sequence

from .config import Settings
from .models import (
    Candidate, Confidence, Evidence, ICPDefinition, PropensityAssessment,
    PropensityBand, SourceProvenance,
)

__all__ = ["ObservedSignal", "SignalKind", "assess", "BAND_THRESHOLDS",
           "approach_for"]

SignalKind = Literal[
    "substantive_comment", "reply_to_user", "repeat_engagement",
    "share_with_commentary", "short_comment", "reaction_only",
]


@dataclass(frozen=True)
class ObservedSignal:
    """One engagement that was actually seen, with when and from where.

    `detail` is what makes the evidence checkable later; a signal with a vague
    detail is still recorded, but it reads as vague in the output, which is the
    honest result.
    """

    kind: SignalKind
    occurred_on: date
    source: SourceProvenance
    detail: str = ""
    topic: Optional[str] = None

    def as_evidence(self, confidence: Confidence) -> Evidence:
        label = self.kind.replace("_", " ")
        observed = f"{label} on {self.occurred_on.isoformat()}"
        if self.detail:
            observed += f": {self.detail}"
        return Evidence(
            observed=observed,
            source=self.source,
            confidence=confidence,
            observed_on=self.occurred_on,
        )


#: Lower bound of each band on the normalised 0..1 score.
BAND_THRESHOLDS: tuple[tuple[float, PropensityBand], ...] = (
    (0.75, PropensityBand.very_high),
    (0.50, PropensityBand.high),
    (0.28, PropensityBand.moderate),
    (0.12, PropensityBand.low),
    (0.00, PropensityBand.very_low),
)

#: Sources whose claims we treat as first-hand. Anything else contributes at
#: medium confidence at best, because the user did not see it themselves.
_FIRST_HAND = {
    "user_supplied_note", "linkedin_analytics_export", "linkedin_data_export",
    "official_api",
}


def _recency_factor(signal_date: date, window_days: int, today: date) -> float:
    """Linear decay to zero at the window edge. Nothing outside counts.

    Linear rather than exponential on purpose: an exponential curve implies a
    precision about decay rates that nothing here measures.
    """
    age = (today - signal_date).days
    if age < 0:
        return 0.0
    if age >= window_days:
        return 0.0
    return 1.0 - (age / window_days)


def _topic_bonus(signals: Sequence[ObservedSignal], user_topics: Sequence[str]) -> float:
    """Up to +0.1 when the engagement was on topics the user actually writes about."""
    if not user_topics:
        return 0.0
    wanted = {t.lower().strip() for t in user_topics if t}
    hits = sum(
        1 for s in signals
        if s.topic and any(w in s.topic.lower() for w in wanted)
    )
    if not hits:
        return 0.0
    return min(0.1, 0.035 * hits)


def _confidence_for(signals: Sequence[ObservedSignal], settings: Settings,
                    today: date) -> Confidence:
    """How much the band can be trusted.

    Driven by three things: how many distinct signals there are, how recent
    they are, and whether the user saw them first-hand. One reaction six months
    ago supports nothing.
    """
    window = settings.scoring.engagement_signals.recency_window_days
    live = [s for s in signals if _recency_factor(s.occurred_on, window, today) > 0]
    if not live:
        return Confidence.none
    first_hand = sum(1 for s in live if s.source.kind.value in _FIRST_HAND)
    distinct_kinds = len({s.kind for s in live})
    strong = sum(1 for s in live
                 if s.kind in ("substantive_comment", "reply_to_user", "repeat_engagement"))

    if len(live) >= 3 and strong >= 2 and first_hand >= 1:
        return Confidence.high
    if len(live) >= 2 and (strong >= 1 or distinct_kinds >= 2):
        return Confidence.medium
    return Confidence.low


def assess(
    candidate: Candidate,
    signals: Iterable[ObservedSignal],
    settings: Settings,
    *,
    icps: Sequence[ICPDefinition] = (),
    today: Optional[date] = None,
) -> PropensityAssessment:
    """Grade the evidence and return a band, its support and its limits.

    With no signals inside the recency window the result is
    `insufficient_evidence` with confidence `none` — which is a usable answer,
    not a failure: it tells the user this person is a cold approach rather than
    a warm one.
    """
    today = today or date.today()
    cfg = settings.scoring.engagement_signals
    window = cfg.recency_window_days
    sigs = list(signals)

    weights = {
        "substantive_comment": cfg.substantive_comment,
        "reply_to_user": cfg.reply_to_user,
        "repeat_engagement": cfg.repeat_engagement,
        "share_with_commentary": cfg.share_with_commentary,
        "short_comment": cfg.short_comment,
        "reaction_only": cfg.reaction_only,
    }

    live = [s for s in sigs if _recency_factor(s.occurred_on, window, today) > 0]
    confidence = _confidence_for(sigs, settings, today)

    if not live:
        stale_note = (
            f"{len(sigs)} signal(s) on record, all older than the "
            f"{window}-day window" if sigs else "no engagement signals on record"
        )
        return PropensityAssessment(
            candidate_id=candidate.candidate_id,
            band=PropensityBand.insufficient_evidence,
            raw_score=None,
            observations=[],
            predictions=[
                f"Propensity cannot be estimated: {stale_note}. Treat as a cold "
                f"approach and judge on ICP fit and shared context instead."
            ],
            confidence=Confidence.none,
            recommended_approach=approach_for(
                PropensityBand.insufficient_evidence, candidate, icps
            ),
        )

    # Weighted, recency-decayed sum, then squashed. The saturating curve stops
    # a long tail of reactions from adding up to a strong signal.
    raw = 0.0
    for s in live:
        raw += weights.get(s.kind, 0.1) * _recency_factor(s.occurred_on, window, today)
    score = 1.0 - math.exp(-raw / 2.2)
    score = min(1.0, score + _topic_bonus(live, settings.profile.content_topics))

    band = next(b for threshold, b in BAND_THRESHOLDS if score >= threshold)

    observations = [s.as_evidence(confidence) for s in sorted(
        live, key=lambda x: x.occurred_on, reverse=True
    )][: settings.output.max_evidence_shown_per_candidate]

    predictions: list[str] = [
        f"Estimated engagement propensity {band.value} "
        f"(normalised {score:.2f}) from {len(live)} signal(s) inside the "
        f"{window}-day window."
    ]
    if confidence is Confidence.low:
        predictions.append(
            "Low confidence: too few recent signals, or none the user saw "
            "first-hand. Worth re-checking before acting on it."
        )
    stale = len(sigs) - len(live)
    if stale:
        predictions.append(
            f"{stale} older signal(s) excluded as outside the window."
        )

    return PropensityAssessment(
        candidate_id=candidate.candidate_id,
        band=band,
        raw_score=round(score, 4),
        observations=observations,
        predictions=predictions,
        confidence=confidence,
        recommended_approach=approach_for(band, candidate, icps),
    )


def approach_for(band: PropensityBand, candidate: Candidate,
                 icps: Sequence[ICPDefinition] = ()) -> str:
    """The relationship-building move that fits the evidence.

    Relationship-first throughout: no band produces a pitch, because a pitch on
    first contact is the thing that burns the connection this bundle exists to
    build.
    """
    name = candidate.name.split(" ")[0] if candidate.name else "them"
    base = {
        PropensityBand.very_high: (
            f"Already engaging. A connection request with a note referencing "
            f"what {name} actually said is likely to land. Keep it to the "
            f"conversation you are already having."
        ),
        PropensityBand.high: (
            f"Warm. Comment substantively on one more post first, then connect "
            f"referencing that exchange. Two touches before the invitation is "
            f"the difference between a note that reads as earned and one that "
            f"reads as a template."
        ),
        PropensityBand.moderate: (
            f"Some signal. Engage on their work for two or three weeks before "
            f"inviting. Nothing to say yet means nothing to say in the note."
        ),
        PropensityBand.low: (
            f"Thin. Worth following rather than connecting. Revisit when there "
            f"is something specific to respond to."
        ),
        PropensityBand.very_low: (
            f"No usable signal of interest. Follow, or leave it. An invitation "
            f"now is a cold one with nothing to say in it."
        ),
        PropensityBand.insufficient_evidence: (
            f"Cold approach. Judge on ICP fit and shared context, and expect "
            f"the invitation to carry the whole weight — so it needs a real, "
            f"specific reason or it should not be sent."
        ),
    }[band]
    if candidate.shared_context:
        base += (
            f" Shared context on record: {candidate.shared_context[0]} — lead "
            f"with that rather than with your own work."
        )
    return base
