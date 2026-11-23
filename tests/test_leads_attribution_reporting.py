"""Lead intelligence, content attribution and reporting.

One rule runs through all three: a figure that cannot be sourced is reported as
unavailable, never estimated.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from lni.attribution import (
    audience_gap, build_affinity, growth_series, limits_for, recommend_topics,
)
from lni.config import load_config
from lni.leads import (
    SignalInput, classify_candidate, discovery_questions, opportunity_report,
)
from lni.models import (
    AudienceSegment, Confidence, ContentAnalytics, CRMStatus, Evidence,
    OpportunityStage, RelationshipEvent, Seniority, TouchChannel,
)
from lni.reporting import build_report, compute_funnel, period_bounds
from lni import provenance as prov
from tests.conftest import make_candidate


def pub_sig(text, observed, *, conf=Confidence.medium):
    return SignalInput(text, Evidence(observed=observed,
                                      source=prov.company_site("https://x.example"),
                                      confidence=conf))


# ------------------------------------------------------------- leads ---

def test_no_categories_means_no_opportunities(settings):
    c = make_candidate("Dana Whitfield", company="Northfield Foods")
    assert settings.usable_service_categories == []
    assert classify_candidate(c, [pub_sig("anything", "anything")], settings) == []


def test_a_real_signal_produces_one_hypothesis(b2b_settings):
    c = make_candidate("Dana Whitfield", company="Northfield Foods")
    opps = classify_candidate(c, [
        pub_sig("careers page has a job posting for an inventory and stock-control role",
                "inventory analyst posting on careers page"),
        pub_sig("website describes manual stock counts each month",
                "site states stock counts are manual"),
    ], b2b_settings)
    assert len(opps) == 1
    opp = opps[0]
    assert opp.service_category == "inventory_implementation"
    assert opp.stage is OpportunityStage.signal_observed
    assert "hypothesis" in opp.hypothesis.lower()
    assert not opp.confirmed_by_user
    assert opp.confidence.weight <= Confidence.medium.weight


def test_generic_words_do_not_match_every_category(b2b_settings):
    """A signal about inventory must not also fire the demand-planning category."""
    c = make_candidate("Dana Whitfield", company="Northfield Foods")
    opps = classify_candidate(c, [
        pub_sig("careers page has a public job posting for an inventory role",
                "inventory posting")], b2b_settings)
    assert [o.service_category for o in opps] == ["inventory_implementation"]


def test_an_unrelated_signal_produces_nothing(b2b_settings):
    c = make_candidate("Dana Whitfield", company="Northfield Foods")
    assert classify_candidate(c, [
        pub_sig("the founder spoke at a food safety conference",
                "spoke at a conference")], b2b_settings) == []


def test_a_disqualifier_blocks_the_category(b2b_settings):
    c = make_candidate("Rival Rick", company="Rival Software")
    opps = classify_candidate(c, [
        pub_sig("job posting for an inventory and stock-control role", "posting"),
        pub_sig("the company sells inventory software itself", "they sell it"),
    ], b2b_settings)
    assert opps == []


def test_a_signal_from_an_unauthorised_source_is_refused(b2b_settings):
    c = make_candidate("Dana Whitfield", company="Northfield Foods")
    bad = [SignalInput("inventory role posting", Evidence(
        observed="x", source=prov.data_export("export.zip"),
        confidence=Confidence.high))]
    with pytest.raises(ValueError, match="not a permitted source"):
        classify_candidate(c, bad, b2b_settings)


def test_confidence_is_capped_without_user_confirmation(b2b_settings):
    c = make_candidate("Dana Whitfield", company="Northfield Foods")
    opps = classify_candidate(c, [
        pub_sig("job posting for an inventory and stock-control role", "posting",
                conf=Confidence.high)], b2b_settings)
    cap = b2b_settings.business_services.max_confidence_without_user_confirmation
    assert opps[0].confidence.weight <= cap.weight


def test_discovery_questions_include_the_unguessable_two(b2b_settings):
    c = make_candidate("Dana Whitfield", company="Northfield Foods")
    opp = classify_candidate(c, [
        pub_sig("job posting for an inventory and stock-control role", "posting")],
        b2b_settings)[0]
    qs = discovery_questions(opp, b2b_settings, limit=6)
    joined = " ".join(qs).lower()
    assert "end to end" in joined
    assert "already tried" in joined


def test_the_opportunity_report_states_its_limits(b2b_settings):
    c = make_candidate("Dana Whitfield", company="Northfield Foods")
    opps = classify_candidate(c, [
        pub_sig("job posting for an inventory and stock-control role", "posting")],
        b2b_settings)
    rep = opportunity_report(opps, b2b_settings)
    assert rep["unconfirmed"] == 1 and rep["confirmed_by_user"] == 0
    joined = " ".join(rep["limits"]).lower()
    assert "intends to buy" in joined
    assert "budget" in joined


# -------------------------------------------------------- attribution ---

def posts():
    src = prov.analytics_export("posts.csv")
    base = date(2026, 10, 1)
    out = []
    for i, (topic, impressions, comments, followers) in enumerate([
        ("inventory accuracy", 12400, 34, 21),
        ("inventory accuracy", 15200, 61, 33),
        ("inventory accuracy", 9800, 28, None),
        ("demand planning", 8900, 12, 2),
        ("hiring", 44900, 3, 0),
    ]):
        out.append(ContentAnalytics(
            post_ref=f"https://linkedin.com/feed/update/{i}",
            published_on=base + timedelta(days=i * 7),
            topics=[topic], impressions=impressions, comments=comments,
            reactions=impressions // 100, followers_gained=followers, source=src))
    return out


def test_a_topic_below_the_floor_is_reported_but_not_ranked(settings):
    m = build_affinity(posts(), settings)
    assert m.rollups["inventory accuracy"].sufficient
    assert not m.rollups["demand planning"].sufficient
    ranked = [r.topic for r in m.best_by("comments_per_post", min_posts=settings.audience.min_posts_per_topic)]
    assert ranked == ["inventory accuracy"]
    note = [r for r in recommend_topics(m, settings) if r.get("note")]
    assert any("fewer than 3 posts" in n["note"] for n in note)


def test_missing_metrics_stay_missing(settings):
    m = build_affinity(posts(), settings)
    roll = m.rollups["inventory accuracy"]
    assert roll.followers_gained == 54, "two known values summed, the None ignored"
    assert any("no follower figure" in l for l in m.limits)


def test_a_topicless_corpus_is_counted_not_guessed(settings):
    src = prov.analytics_export("x.csv")
    bare = [ContentAnalytics(post_ref="a", impressions=100, source=src)]
    m = build_affinity(bare, settings)
    assert m.posts_without_topics == 1 and m.rollups == {}


def test_limits_are_built_from_the_actual_gaps(settings):
    assert "nothing can be attributed" in " ".join(limits_for([], settings))
    joined = " ".join(limits_for(posts(), settings))
    assert "profile views" in joined
    assert "business outcomes" in joined
    assert "not causally linked" in joined
    assert "not evidence that anyone read" in joined


def test_impressions_are_never_called_readership(settings):
    joined = " ".join(limits_for(posts(), settings)).lower()
    assert "delivery figure" in joined


def test_growth_series_keeps_gaps(settings):
    series = growth_series(posts())
    assert series and all("month" in row for row in series)
    assert sum(r["posts"] for r in series) == 5


def test_audience_gap_without_a_target_asks_for_one(settings):
    gap = audience_gap([], settings)
    assert gap["status"] == "no target"
    assert "which audience do you want" in gap["detail"].lower()


def test_audience_gap_measures_against_counted_segments(b2b_settings):
    segments = [
        AudienceSegment(key="ops_leaders", label="Ops leaders",
                        matched_icp_keys=["business_development"], size=300,
                        size_basis="follower export 2026-11", quality="target"),
        AudienceSegment(key="consultants", label="Consultants", size=700,
                        size_basis="follower export 2026-11", quality="irrelevant"),
    ]
    gap = audience_gap(segments, b2b_settings)
    assert gap["audience_counted"] == 1000
    bd = next(g for g in gap["gaps"] if g["icp_key"] == "business_development")
    assert bd["current_share"] == pytest.approx(0.3)
    assert bd["gap"] == pytest.approx(0.05)


# ---------------------------------------------------------- reporting ---

def test_period_bounds():
    end = date(2026, 11, 23)
    assert period_bounds("weekly", end=end) == (date(2026, 11, 17), end)
    assert period_bounds("monthly", end=end) == (date(2026, 10, 25), end)
    with pytest.raises(ValueError):
        period_bounds("yearly")


def seed(crm, *, invited=2, accepted=1):
    ids = []
    for i in range(3):
        c = make_candidate(f"Person {i}", professional_title="VP Operations",
                           seniority=Seniority.vp,
                           primary_icp_key="business_development")
        crm.upsert(c)
        crm.set_status(c.candidate_id, CRMStatus.researching)
        crm.set_status(c.candidate_id, CRMStatus.qualified)
        ids.append(c.candidate_id)
    for cid in ids[:invited]:
        crm.set_status(cid, CRMStatus.shortlisted)
        crm.set_status(cid, CRMStatus.invitation_prepared)
        crm.set_status(cid, CRMStatus.manually_invited, confirmed_by_user=True)
    for cid in ids[:accepted]:
        crm.set_status(cid, CRMStatus.accepted, confirmed_by_user=True)
    return ids


def test_the_funnel_counts_confirmed_events(b2b_crm, b2b_settings):
    seed(b2b_crm)
    start, end = period_bounds("weekly")
    m = compute_funnel(b2b_crm, b2b_settings, start, end)
    assert m.profiles_researched == 3
    assert m.qualified_candidates == 3
    assert m.invitations_manually_sent == 2
    assert m.invitations_accepted == 1
    assert m.acceptance_rate == pytest.approx(0.5)


def test_no_invitations_means_no_rate_not_zero(b2b_crm, b2b_settings):
    seed(b2b_crm, invited=0, accepted=0)
    start, end = period_bounds("weekly")
    m = compute_funnel(b2b_crm, b2b_settings, start, end)
    assert m.acceptance_rate is None
    assert "fabricated figure" in m.unavailable["acceptance_rate"]


def test_platform_only_metrics_are_unavailable_with_a_reason(b2b_crm, b2b_settings):
    seed(b2b_crm)
    start, end = period_bounds("weekly")
    m = compute_funnel(b2b_crm, b2b_settings, start, end)
    for name in ("profile_visits", "followers_gained",
                 "content_engagement_from_new_connections"):
        assert getattr(m, name) is None
        assert name in m.unavailable
        assert len(m.unavailable[name]) > 40, "the reason must be a real explanation"


def test_an_analytics_export_fills_what_it_can(b2b_crm, b2b_settings):
    seed(b2b_crm)
    start, end = period_bounds("weekly")
    content = [ContentAnalytics(
        post_ref="p1", published_on=end, followers_gained=12,
        profile_views_attributed=30, source=prov.analytics_export("a.csv"))]
    m = compute_funnel(b2b_crm, b2b_settings, start, end, content=content)
    assert m.followers_gained == 12
    assert m.profile_visits == 30
    assert "followers_gained" not in m.unavailable


def test_the_report_has_the_required_sections(b2b_crm, b2b_settings):
    seed(b2b_crm)
    report = build_report(b2b_crm, b2b_settings, period="weekly")
    assert report.period == "weekly"
    assert report.icp_performance, "per-ICP breakdown is required"
    assert report.audience_quality_notes
    assert report.recommended_improvements
    assert report.attribution_limits
    joined = " ".join(report.attribution_limits).lower()
    assert "nothing is read from linkedin" in joined


def test_an_empty_store_reports_emptiness_not_zeros(crm, settings):
    report = build_report(crm, settings, period="weekly")
    assert any("store is empty" in n for n in report.audience_quality_notes)


def test_a_low_acceptance_rate_is_diagnosed_as_a_note_problem(b2b_crm, b2b_settings):
    ids = seed(b2b_crm, invited=3, accepted=0)
    report = build_report(b2b_crm, b2b_settings, period="weekly")
    joined = " ".join(report.recommended_improvements).lower()
    assert "note problem" in joined or "no invitations were recorded" in joined


def test_substantive_interactions_are_counted_and_reactions_are_not(b2b_crm,
                                                                    b2b_settings):
    ids = seed(b2b_crm)
    today = date.today()
    b2b_crm.add_event(RelationshipEvent(
        candidate_id=ids[0], occurred_on=today, channel=TouchChannel.linkedin_dm,
        direction="outbound", summary="real exchange", substantive=True))
    b2b_crm.add_event(RelationshipEvent(
        candidate_id=ids[1], occurred_on=today,
        channel=TouchChannel.linkedin_reaction, direction="outbound",
        summary="liked a post", substantive=False))
    start, end = period_bounds("weekly")
    m = compute_funnel(b2b_crm, b2b_settings, start, end)
    assert m.meaningful_interactions == 1
