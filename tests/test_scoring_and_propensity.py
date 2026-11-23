"""The scoring engine and the propensity engine.

The behaviours under test are the four disciplines the bundle claims:
abstention instead of a midpoint, evidence behind every point, observations
kept apart from predictions, and follower count kept in its place.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from lni.config import load_config
from lni.models import Confidence, Evidence, PriorityClass, PropensityBand, Seniority
from lni.propensity import ObservedSignal, approach_for, assess
from lni.scoring import (
    ActivityFact, InfluenceFacts, ScoringInput, best_icp, icp_fit, rank,
    score_candidate,
)
from lni import provenance as prov
from tests.conftest import make_candidate

SRC = prov.user_note("seen in my own notifications")


def sig(kind, days_ago, *, topic=None, detail="x"):
    return ObservedSignal(kind, date.today() - timedelta(days=days_ago), SRC,
                          detail, topic)


# ---------------------------------------------------------- propensity ---

def test_no_signals_gives_insufficient_evidence_not_a_low_score(settings, strong_candidate):
    a = assess(strong_candidate, [], settings)
    assert a.band is PropensityBand.insufficient_evidence
    assert a.confidence is Confidence.none
    assert a.raw_score is None
    assert a.observations == []
    assert a.predictions, "it must say what the absence means"


def test_stale_signals_are_excluded_and_counted(settings, strong_candidate):
    a = assess(strong_candidate, [sig("substantive_comment", 400)], settings)
    assert a.band is PropensityBand.insufficient_evidence
    assert any("older than" in p for p in a.predictions)


def test_a_single_reaction_is_near_the_bottom(settings, strong_candidate):
    a = assess(strong_candidate, [sig("reaction_only", 5)], settings)
    assert a.band in (PropensityBand.very_low, PropensityBand.low)
    assert a.confidence is Confidence.low


def test_repeated_substantive_engagement_scores_high(settings, strong_candidate):
    a = assess(strong_candidate, [
        sig("substantive_comment", 3), sig("substantive_comment", 30),
        sig("reply_to_user", 6), sig("repeat_engagement", 12),
    ], settings)
    assert a.band in (PropensityBand.high, PropensityBand.very_high)
    assert a.confidence is Confidence.high


def test_recency_matters(settings, strong_candidate):
    recent = assess(strong_candidate, [sig("substantive_comment", 2)], settings)
    old = assess(strong_candidate, [sig("substantive_comment", 170)], settings)
    assert (recent.raw_score or 0) > (old.raw_score or 0)


def test_observations_and_predictions_never_mix(settings, strong_candidate):
    a = assess(strong_candidate, [sig("substantive_comment", 4)], settings)
    assert all(isinstance(o, Evidence) for o in a.observations)
    assert all(isinstance(p, str) for p in a.predictions)
    for o in a.observations:
        assert "estimated" not in o.observed.lower()


def test_topic_overlap_lifts_the_score_a_little_not_a_lot(strong_candidate):
    s = load_config(overrides={"profile": {"content_topics": ["inventory accuracy"]}})
    with_topic = assess(strong_candidate, [sig("short_comment", 5, topic="inventory accuracy")], s)
    without = assess(strong_candidate, [sig("short_comment", 5)], s)
    delta = (with_topic.raw_score or 0) - (without.raw_score or 0)
    assert 0 < delta <= 0.11


def test_no_band_recommends_a_pitch(settings, strong_candidate):
    for band in PropensityBand:
        text = approach_for(band, strong_candidate).lower()
        for pitchy in ("pitch", "our offering", "book a demo", "buy"):
            assert pitchy not in text, (band, pitchy)


# ------------------------------------------------------------- ICP fit ---

def test_fit_counts_only_dimensions_the_icp_specifies(b2b_settings, strong_candidate):
    icp = b2b_settings.icp("business_development")
    fit, reasons, excluded = icp_fit(strong_candidate, icp)
    assert excluded is None
    assert fit == pytest.approx(1.0)
    assert reasons


def test_a_thin_record_cannot_be_judged(b2b_settings):
    thin = make_candidate("Nobody Known")
    fit, reasons, _ = icp_fit(thin, b2b_settings.icp("business_development"))
    assert fit == 0.0
    assert any("too thin" in r for r in reasons)


def test_title_exclusion_fires(b2b_settings):
    c = make_candidate("Rory Reseller", professional_title="Consultant",
                       industry="Food and beverage manufacturing",
                       seniority=Seniority.director)
    _fit, _reasons, excluded = icp_fit(c, b2b_settings.icp("business_development"))
    assert excluded and "consultant" in excluded.lower()


def test_a_literal_exclusion_phrase_in_the_record_excludes(b2b_settings):
    icp = b2b_settings.icp("business_development")
    criterion = icp.exclusion_criteria[0]
    c = make_candidate("Sam Literal", professional_title="VP Operations",
                       industry="Food and beverage manufacturing",
                       seniority=Seniority.vp, notes=criterion)
    _fit, _r, excluded = icp_fit(c, icp)
    assert excluded == criterion


def test_unverifiable_exclusion_criteria_are_surfaced_not_guessed(b2b_settings):
    """A criterion the engine cannot check must reach the human, not be ignored
    and not be applied on a keyword hunch."""
    c = make_candidate("Sam Softwareseller", professional_title="VP Operations",
                       industry="Food and beverage manufacturing",
                       seniority=Seniority.vp, company_size_band="201-500",
                       geography="United States",
                       notes="their team sells inventory software themselves")
    fit, reasons, excluded = icp_fit(c, b2b_settings.icp("business_development"))
    assert excluded is None, "a judgement criterion must not auto-exclude"
    assert fit > 0
    assert any("check by hand" in r for r in reasons), reasons


def test_ties_break_on_icp_priority(b2b_settings):
    c = make_candidate("Multi Match", professional_title="Founder",
                       seniority=Seniority.founder_owner, industry="Software")
    icp, _fit, _r, _e = best_icp(c, b2b_settings.active_icps)
    assert icp is not None


# ------------------------------------------------------------ scoring ---

def test_a_component_with_no_inputs_abstains(settings):
    thin = make_candidate("Thin Record")
    score, _ = score_candidate(ScoringInput(candidate=thin, icps=settings.active_icps),
                               settings)
    assert len(score.abstentions) >= 4
    for comp in score.components:
        if comp.abstained:
            assert comp.points == 0.0
            assert comp.rationale, "an abstention must say why"


def test_abstention_is_never_a_midpoint(settings):
    thin = make_candidate("Thin Record")
    score, _ = score_candidate(ScoringInput(candidate=thin, icps=settings.active_icps),
                               settings)
    assert score.total < 10.0, "a record with nothing in it must not score mid-range"


def test_many_abstentions_cap_the_priority(b2b_settings):
    """A perfect ICP fit with no evidence cannot be promoted."""
    c = make_candidate("Maya Quiet", professional_title="Plant Manager",
                       industry="Food production", geography="Canada",
                       seniority=Seniority.manager, company_size_band="51-200",
                       company="Harborline Foods")
    score, _ = score_candidate(ScoringInput(candidate=c, icps=b2b_settings.active_icps),
                               b2b_settings)
    icp_comp = next(x for x in score.components if x.component == "icp_relevance")
    assert icp_comp.points == icp_comp.max_points, "fit should be perfect"
    assert score.priority is PriorityClass.monitor
    assert "nothing observed yet" in score.recommended_next_action
    assert "Do not spend an invitation" in score.recommended_next_action


def test_a_complete_record_reaches_priority_one(b2b_settings, strong_candidate):
    inp = ScoringInput(
        candidate=strong_candidate, icps=b2b_settings.active_icps,
        engagement_signals=[sig("substantive_comment", 3, topic="inventory accuracy"),
                            sig("reply_to_user", 8), sig("repeat_engagement", 20)],
        activity=[ActivityFact("posted about a WMS migration", date.today() - timedelta(days=6), SRC),
                  ActivityFact("commented on a peer post", date.today() - timedelta(days=15), SRC)],
        influence=InfluenceFacts(publishes_regularly=True, speaks_at_events=True,
                                 followers=4200, source=SRC),
        candidate_topics=["inventory accuracy", "warehouse operations"],
        opportunity_score=72.0,
        opportunity_evidence=[Evidence(
            observed="careers page lists an inventory analyst opening",
            source=prov.company_site("https://x.example/careers"),
            confidence=Confidence.medium)],
    )
    score, propensity = score_candidate(inp, b2b_settings)
    assert score.priority is PriorityClass.priority_1
    assert score.abstentions == []
    assert score.confidence in (Confidence.medium, Confidence.high)
    assert propensity.band in (PropensityBand.high, PropensityBand.very_high)


def test_every_scored_point_carries_evidence(b2b_settings, strong_candidate):
    inp = ScoringInput(candidate=strong_candidate, icps=b2b_settings.active_icps,
                       engagement_signals=[sig("substantive_comment", 3)],
                       activity=[ActivityFact("posted", date.today(), SRC)],
                       influence=InfluenceFacts(publishes_regularly=True, source=SRC),
                       candidate_topics=["inventory accuracy"])
    score, _ = score_candidate(inp, b2b_settings)
    for comp in score.components:
        if comp.points > 0:
            assert comp.evidence, f"{comp.component} scored with no evidence"


def test_follower_count_alone_cannot_promote_a_candidate(b2b_settings):
    c = make_candidate("Big Audience", professional_title="VP Operations",
                       industry="Food and beverage manufacturing",
                       seniority=Seniority.vp, company_size_band="201-500",
                       geography="United States", company="Loudco")
    huge = score_candidate(ScoringInput(
        candidate=c, icps=b2b_settings.active_icps,
        influence=InfluenceFacts(followers=900_000, source=SRC)), b2b_settings)[0]
    none = score_candidate(ScoringInput(
        candidate=c, icps=b2b_settings.active_icps,
        influence=InfluenceFacts(followers=0, source=SRC)), b2b_settings)[0]
    cap = b2b_settings.scoring.professional_influence.follower_subscore_cap
    max_influence = b2b_settings.scoring.active_weights["professional_influence"]
    assert huge.total - none.total <= cap * max_influence + 0.01
    assert huge.priority is none.priority


def test_demonstrated_influence_beats_audience_size(b2b_settings, strong_candidate):
    speaks = score_candidate(ScoringInput(
        candidate=strong_candidate, icps=b2b_settings.active_icps,
        influence=InfluenceFacts(publishes_regularly=True, speaks_at_events=True,
                                 maintains_something_used=True, source=SRC)),
        b2b_settings)[0]
    followers = score_candidate(ScoringInput(
        candidate=strong_candidate, icps=b2b_settings.active_icps,
        influence=InfluenceFacts(followers=500_000, source=SRC)), b2b_settings)[0]
    assert speaks.total > followers.total


def test_exclusion_beats_the_score(b2b_settings):
    c = make_candidate("Rory Reseller", professional_title="Consultant",
                       industry="Food and beverage manufacturing",
                       seniority=Seniority.director, company_size_band="201-500",
                       geography="United States", company="Reseller Co")
    score, _ = score_candidate(ScoringInput(
        candidate=c, icps=b2b_settings.active_icps,
        engagement_signals=[sig("substantive_comment", 2), sig("reply_to_user", 4)],
        activity=[ActivityFact("posted", date.today(), SRC)]), b2b_settings)
    assert score.priority is PriorityClass.excluded
    assert score.excluded_by


def test_opportunity_points_need_usable_signals(b2b_settings, strong_candidate):
    """A number with nothing behind it scores zero rather than being trusted."""
    score, _ = score_candidate(ScoringInput(
        candidate=strong_candidate, icps=b2b_settings.active_icps,
        opportunity_score=90.0, opportunity_evidence=[]), b2b_settings)
    comp = next(c for c in score.components if c.component == "business_opportunity")
    assert comp.abstained and comp.points == 0.0


def test_zero_weight_component_abstains(strong_candidate):
    s = load_config(extra_files=["config/examples/technology-professional.yaml"])
    score, _ = score_candidate(ScoringInput(candidate=strong_candidate,
                                            icps=s.active_icps), s)
    comp = next(c for c in score.components if c.component == "business_opportunity")
    assert comp.abstained


def test_topic_alignment_abstains_without_user_topics(settings, strong_candidate):
    assert settings.profile.content_topics == []
    score, _ = score_candidate(ScoringInput(
        candidate=strong_candidate, icps=settings.active_icps,
        candidate_topics=["inventory accuracy"]), settings)
    comp = next(c for c in score.components if c.component == "topic_alignment")
    assert comp.abstained


def test_score_records_which_weighting_produced_it(b2b_settings, strong_candidate):
    score, _ = score_candidate(ScoringInput(candidate=strong_candidate,
                                            icps=b2b_settings.active_icps), b2b_settings)
    assert score.weights_profile == "business_development"


def test_ranking_puts_class_before_total(b2b_settings, strong_candidate):
    confident = score_candidate(ScoringInput(
        candidate=strong_candidate, icps=b2b_settings.active_icps,
        engagement_signals=[sig("substantive_comment", 2), sig("reply_to_user", 5),
                            sig("repeat_engagement", 9)],
        activity=[ActivityFact("posted", date.today(), SRC),
                  ActivityFact("commented", date.today() - timedelta(days=3), SRC)],
        influence=InfluenceFacts(publishes_regularly=True, speaks_at_events=True, source=SRC),
        candidate_topics=["inventory accuracy"],
        opportunity_score=70.0,
        opportunity_evidence=[Evidence(observed="job posting", source=prov.company_site("https://x.example"),
                                       confidence=Confidence.medium)]), b2b_settings)[0]
    thin = score_candidate(ScoringInput(candidate=make_candidate("Thin One"),
                                        icps=b2b_settings.active_icps), b2b_settings)[0]
    order = rank([thin, confident])
    assert order[0].candidate_id == confident.candidate_id
