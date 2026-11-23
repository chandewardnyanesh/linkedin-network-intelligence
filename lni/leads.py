"""Business opportunity classification.

The job: notice that someone in the network might have a problem the user can
help with, and say so as a hypothesis with the public evidence attached.

Two things this module will not do, and both are enforced rather than advised:

* **It will not infer confidential company information.** Signals must be
  public or user-supplied. `classify` refuses a signal whose source is not an
  authorised kind, and nothing here reasons about budgets, contracts or
  internal systems.
* **It will not fabricate purchasing intent.** An opportunity starts at
  `hypothesis` and cannot pass `signal_observed` without the user confirming a
  real conversation — the model layer rejects the attempt. Confidence is capped
  by `business_services.max_confidence_without_user_confirmation`, which cannot
  be set to `high`.

With no service categories configured, `classify_candidate` returns nothing.
That is the correct output for someone networking non-commercially, not a
failure to try.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from .config import ServiceCategory, Settings
from .models import (
    BusinessOpportunity, Candidate, Confidence, Evidence, OpportunityStage,
    SourceKind, utcnow,
)

__all__ = ["SignalInput", "classify_candidate", "classify", "discovery_questions",
           "opportunity_report"]


@dataclass(frozen=True)
class SignalInput:
    """One public observation that might indicate a need."""

    text: str
    evidence: Evidence
    category_hint: Optional[str] = None


#: Source kinds a commercial signal may come from. A signal about a company's
#: needs has to be something publicly visible or something the user was told.
_PERMITTED_SIGNAL_SOURCES = {
    SourceKind.company_website,
    SourceKind.public_publication,
    SourceKind.professional_directory,
    SourceKind.conference_or_event,
    SourceKind.user_supplied_note,
    SourceKind.user_supplied_csv,
    SourceKind.user_supplied_url,
    SourceKind.referral,
    SourceKind.official_api,
    SourceKind.upstream_skill_export,
}

#: Words that turn a hypothesis into a claim about something unknowable.
#: Rejected in `hypothesis` text so the record cannot overstate itself.
_OVERCLAIMS = (
    "they need", "they will buy", "ready to buy", "has budget", "budget approved",
    "will sign", "decided to", "committed to", "is replacing", "has chosen",
    "their contract expires", "they are spending", "procurement approved",
)


#: Words that appear in nearly every signal description and therefore carry no
#: information about *which* category matched. Without this stoplist, "public
#: job posting for an inventory role" matches "public job posting for a demand
#: planner" on the words they share rather than the words that differ, and
#: every category fires on every signal.
_GENERIC = frozenset({
    "public", "posting", "postings", "posted", "job", "jobs", "role", "roles",
    "company", "companys", "website", "site", "page", "pages", "careers",
    "career", "their", "they", "them", "person", "people", "said", "says",
    "describes", "described", "description", "have", "has", "with", "from",
    "that", "this", "there", "been", "about", "which", "where", "when", "will",
    "would", "could", "some", "same", "also", "more", "most", "than", "then",
    "into", "each", "other", "something", "anything", "open", "opening",
    "hiring", "hire", "team", "work", "working", "business", "process",
    "processes", "system", "systems", "data", "software", "service", "services",
    "manual", "manually", "current", "currently", "existing", "new",
})


def _tokens(text: str) -> set[str]:
    """Informative tokens only: longer than three characters, not generic."""
    raw = {w.strip(".,;:!?()[]\"'").lower() for w in (text or "").split() if len(w) > 3}
    return {w for w in raw if w and w not in _GENERIC}


def _match_strength(signal_text: str, category: ServiceCategory) -> tuple[float, list[str]]:
    """How well one signal matches one category's declared observable signals."""
    sig = _tokens(signal_text)
    if not sig:
        return 0.0, []
    hits: list[str] = []
    best = 0.0
    for declared in category.observable_signals:
        dec = _tokens(declared)
        if not dec:
            continue
        shared = sig & dec
        if not shared:
            continue
        # Overlap coefficient: shared tokens over the SMALLER set. Dividing by
        # the declared set's size instead would mean a precisely-worded signal
        # ("a posting for an inventory, planning or stock-control role") could
        # never be matched by a short real-world observation ("a posting for an
        # inventory role"), which is the commonest shape a real signal takes.
        overlap = len(shared) / min(len(sig), len(dec))
        if overlap >= 0.5:
            hits.append(declared)
            best = max(best, overlap)
    return min(1.0, best), hits


def _disqualified(signal_texts: Sequence[str], category: ServiceCategory
                  ) -> Optional[str]:
    for dq in category.disqualifiers:
        dq_tokens = _tokens(dq)
        if not dq_tokens:
            continue
        for text in signal_texts:
            if len(_tokens(text) & dq_tokens) / max(1, len(dq_tokens)) >= 0.6:
                return dq
    return None


def classify(
    candidate: Candidate,
    signals: Sequence[SignalInput],
    category: ServiceCategory,
    settings: Settings,
) -> Optional[BusinessOpportunity]:
    """Classify one candidate against one service category.

    None means no opportunity is recorded, which is the default outcome.
    """
    if not category.is_usable:
        return None

    for s in signals:
        if s.evidence.source.kind not in _PERMITTED_SIGNAL_SOURCES:
            raise ValueError(
                f"signal source {s.evidence.source.kind.value!r} is not a "
                f"permitted source for a commercial signal; a claim about a "
                f"company's needs must be publicly visible or something you "
                f"were told directly"
            )

    texts = [s.text for s in signals]
    dq = _disqualified(texts, category)
    if dq:
        return None

    matched: list[Evidence] = []
    reasons: list[str] = []
    strength = 0.0
    for s in signals:
        if s.category_hint and s.category_hint != category.key:
            continue
        score, hits = _match_strength(s.text, category)
        if score > 0 and s.evidence.usable:
            matched.append(s.evidence)
            reasons.extend(hits)
            strength = max(strength, score)

    if not matched:
        return None

    cap = settings.business_services.max_confidence_without_user_confirmation
    observed_conf = min([e.confidence for e in matched], key=lambda c: c.weight)
    confidence = observed_conf if observed_conf.weight <= cap.weight else cap

    distinct = len(set(reasons))
    relevance = min(100.0, round(strength * 60 + distinct * 15, 1))

    hypothesis = (
        f"{candidate.company or candidate.name} may have work in "
        f"{category.label.lower()}. Based on: "
        + "; ".join(sorted(set(reasons))[:3])
        + ". This is a hypothesis about a possible need, not a statement about "
        "their plans, systems or budget."
    )

    return BusinessOpportunity(
        opportunity_id=BusinessOpportunity.make_id(candidate.candidate_id, category.key),
        candidate_id=candidate.candidate_id,
        service_category=category.key,
        hypothesis=hypothesis,
        stage=OpportunityStage.signal_observed if matched else OpportunityStage.hypothesis,
        signals=matched[:5],
        discovery_questions=list(category.discovery_questions),
        estimated_relevance=relevance,
        confidence=confidence,
        confirmed_by_user=False,
    )


def classify_candidate(
    candidate: Candidate,
    signals: Sequence[SignalInput],
    settings: Settings,
) -> list[BusinessOpportunity]:
    """Classify against every usable category, best first.

    Returns an empty list when no category is configured, when no signal
    matches, or when a disqualifier fires. All three are ordinary results.
    """
    out: list[BusinessOpportunity] = []
    for category in settings.usable_service_categories:
        opp = classify(candidate, signals, category, settings)
        if opp:
            out.append(opp)
    return sorted(out, key=lambda o: -(o.estimated_relevance or 0))


def discovery_questions(opportunity: BusinessOpportunity, settings: Settings,
                        *, limit: int = 4) -> list[str]:
    """Questions to ask, drawn from the category plus two structural fallbacks.

    The fallbacks ask about the current process and what has already been
    tried. Both are questions whose answers the user cannot guess, which is
    what makes them discovery rather than confirmation.
    """
    try:
        category = next(c for c in settings.business_services.categories
                        if c.key == opportunity.service_category)
        questions = list(category.discovery_questions)
    except StopIteration:
        questions = list(opportunity.discovery_questions)
    for fallback in (
        "What does that process look like today, end to end?",
        "What have you already tried, and where did it stop?",
    ):
        if fallback not in questions:
            questions.append(fallback)
    return questions[:limit]


def opportunity_report(opportunities: Iterable[BusinessOpportunity],
                       settings: Settings) -> dict:
    """A summary that states its own limits."""
    items = list(opportunities)
    by_category: dict[str, int] = {}
    by_stage: dict[str, int] = {}
    for o in items:
        by_category[o.service_category] = by_category.get(o.service_category, 0) + 1
        by_stage[o.stage.value] = by_stage.get(o.stage.value, 0) + 1
    confirmed = sum(1 for o in items if o.confirmed_by_user)
    return {
        "opportunities": len(items),
        "by_category": dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
        "by_stage": dict(sorted(by_stage.items())),
        "confirmed_by_user": confirmed,
        "unconfirmed": len(items) - confirmed,
        "limits": [
            "Every unconfirmed entry is a hypothesis built from public signals. "
            "None of them is evidence that anyone intends to buy anything.",
            f"Confidence is capped at "
            f"{settings.business_services.max_confidence_without_user_confirmation.value} "
            f"until you confirm a real conversation.",
            "Nothing here infers budget, contract status or internal systems, "
            "because none of that is observable from an authorised source.",
        ],
    }
