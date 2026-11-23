"""Model invariants. These are the guarantees every other module relies on."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from lni.models import (
    AudienceSegment, BusinessOpportunity, Candidate, CandidateScore,
    ComponentScore, Confidence, ContentAnalytics, CRMStatus, Evidence,
    FunnelMetrics, ICPDefinition, InvitationDraft, LEGAL_TRANSITIONS,
    OpportunityStage, PriorityClass, PropensityAssessment, PropensityBand,
    RelationshipEvent, SourceKind, SourceProvenance, StatusChange,
    candidate_id_for, normalise_profile_url,
)
from lni import provenance as prov


# ------------------------------------------------------------ identity ---

@pytest.mark.parametrize("raw,expected", [
    ("https://IN.linkedin.com/in/Some-Person/?trk=x", "https://linkedin.com/in/some-person"),
    ("linkedin.com/in/abc/", "https://linkedin.com/in/abc"),
    ("http://www.linkedin.com/in/ABC", "https://linkedin.com/in/abc"),
    ("https://de.linkedin.com/in/x#foo", "https://linkedin.com/in/x"),
])
def test_profile_url_normalisation(raw, expected):
    assert normalise_profile_url(raw) == expected


def test_normalise_rejects_empty_and_pathless():
    with pytest.raises(ValueError):
        normalise_profile_url("")
    with pytest.raises(ValueError):
        normalise_profile_url("https://linkedin.com")


def test_same_person_two_spellings_one_id():
    a = candidate_id_for("https://WWW.linkedin.com/in/Dana-W/", "Dana W")
    b = candidate_id_for("linkedin.com/in/dana-w", "Dana W")
    assert a == b


def test_candidate_id_must_match_identity_basis():
    with pytest.raises(ValidationError, match="does not match its identity basis"):
        Candidate(
            candidate_id="cand_0000000000000000",
            name="Someone",
            profile_url="https://linkedin.com/in/someone",
            sources=[prov.user_note("x")],
        )


def test_candidate_requires_a_source():
    with pytest.raises(ValidationError):
        Candidate.create(name="Nobody", sources=[])


# ------------------------------------------------------------ evidence ---

def test_evidence_rejects_a_prediction_in_the_observed_field():
    with pytest.raises(ValidationError, match="must state what was seen"):
        Evidence(observed="will likely engage with technical posts",
                 source=prov.user_note("x"))


def test_confidence_none_is_not_usable_as_evidence():
    e = Evidence(observed="reacted once", source=prov.user_note("x"),
                 confidence=Confidence.none)
    assert not e.usable


def test_official_api_provenance_requires_an_authorisation_note():
    with pytest.raises(ValidationError, match="authorisation_note"):
        SourceProvenance(kind=SourceKind.official_api, detail="some api")
    ok = prov.official_api("Partner API", "approved partner access, app 1234")
    assert ok.authorisation_note


def test_provenance_staleness():
    fresh = SourceProvenance(kind=SourceKind.user_supplied_note, detail="x",
                             last_verified=date.today())
    old = SourceProvenance(kind=SourceKind.user_supplied_note, detail="x",
                           last_verified=date.today() - timedelta(days=400))
    never = SourceProvenance(kind=SourceKind.user_supplied_note, detail="x")
    assert not fresh.is_stale and old.is_stale and never.is_stale


# ------------------------------------------------------------- scoring ---

def test_component_cannot_score_without_evidence():
    with pytest.raises(ValidationError, match="no evidence"):
        ComponentScore(component="icp_relevance", points=10.0, max_points=25.0,
                       confidence=Confidence.high)


def test_abstaining_component_cannot_score():
    with pytest.raises(ValidationError, match="abstained but scored"):
        ComponentScore(component="icp_relevance", points=5.0, max_points=25.0,
                       confidence=Confidence.none, abstained=True)


def test_component_cannot_exceed_its_maximum():
    with pytest.raises(ValidationError, match="exceeds max"):
        ComponentScore(component="icp_relevance", points=30.0, max_points=25.0,
                       confidence=Confidence.high,
                       evidence=[Evidence(observed="x", source=prov.user_note("y"))])


def test_score_total_must_equal_its_components():
    comp = ComponentScore(
        component="icp_relevance", points=10.0, max_points=25.0,
        confidence=Confidence.medium,
        evidence=[Evidence(observed="title matches", source=prov.user_note("y"))],
    )
    with pytest.raises(ValidationError, match="does not equal the sum"):
        CandidateScore(candidate_id=candidate_id_for(None, "A", "B"), total=50.0,
                       components=[comp], priority=PriorityClass.priority_3,
                       confidence=Confidence.medium,
                       recommended_next_action="x")


def test_excluded_priority_requires_the_criterion():
    comp = ComponentScore(component="icp_relevance", points=0.0, max_points=25.0,
                          confidence=Confidence.high, abstained=False)
    with pytest.raises(ValidationError, match="requires excluded_by"):
        CandidateScore(candidate_id=candidate_id_for(None, "A", "B"), total=0.0,
                       components=[comp], priority=PriorityClass.excluded,
                       confidence=Confidence.high, recommended_next_action="x")


def test_relevance_score_requires_confidence():
    with pytest.raises(ValidationError, match="number with no support"):
        Candidate.create(name="X", sources=[prov.user_note("y")],
                         relevance_score=40.0, confidence=Confidence.none)


# ---------------------------------------------------------- propensity ---

def test_confident_band_without_observation_is_rejected():
    with pytest.raises(ValidationError, match="no usable observation"):
        PropensityAssessment(candidate_id=candidate_id_for(None, "A", "B"),
                             band=PropensityBand.high, confidence=Confidence.high)


def test_insufficient_evidence_is_the_only_band_with_no_observations():
    a = PropensityAssessment(candidate_id=candidate_id_for(None, "A", "B"),
                             band=PropensityBand.insufficient_evidence,
                             predictions=["cold approach"])
    assert a.confidence is Confidence.none


# ------------------------------------------------------- status machine ---

def test_every_status_can_be_archived():
    for status, allowed in LEGAL_TRANSITIONS.items():
        if status is CRMStatus.archived:
            continue
        assert CRMStatus.archived in allowed, status


def test_no_shortcut_from_prepared_to_accepted():
    assert CRMStatus.accepted not in LEGAL_TRANSITIONS[CRMStatus.invitation_prepared]


def test_illegal_transition_rejected():
    with pytest.raises(ValidationError, match="illegal transition"):
        StatusChange(candidate_id=candidate_id_for(None, "A", "B"),
                     from_status=CRMStatus.discovered,
                     to_status=CRMStatus.converted, confirmed_by_user=True)


@pytest.mark.parametrize("status", [
    CRMStatus.manually_invited, CRMStatus.accepted,
    CRMStatus.conversation_started, CRMStatus.converted,
])
def test_linkedin_side_statuses_need_user_confirmation(status):
    with pytest.raises(ValidationError, match="may only be set from the user"):
        StatusChange(candidate_id=candidate_id_for(None, "A", "B"),
                     from_status=None, to_status=status, confirmed_by_user=False)


# ------------------------------------------------------------- drafts ---

def test_invitation_over_the_limit_is_rejected_not_truncated():
    body = "x" * 301
    with pytest.raises(ValidationError, match="over the 300"):
        InvitationDraft(candidate_id=candidate_id_for(None, "A", "B"),
                        variant_label="direct", body=body, char_count=len(body))


def test_invitation_char_count_must_match():
    with pytest.raises(ValidationError, match="does not match body length"):
        InvitationDraft(candidate_id=candidate_id_for(None, "A", "B"),
                        variant_label="direct", body="hello", char_count=99)


def test_first_touch_invitation_cannot_carry_a_pitch():
    with pytest.raises(ValidationError, match="does not carry a pitch"):
        InvitationDraft(candidate_id=candidate_id_for(None, "A", "B"),
                        variant_label="pitch", body="buy my thing",
                        char_count=12, includes_pitch=True)


# ---------------------------------------------------------- ICP shape ---

def test_active_icp_needs_positive_criteria():
    with pytest.raises(ValidationError, match="no positive criteria"):
        ICPDefinition(key="empty_icp", label="Empty", purpose="professional_networking",
                      active=True, exclusion_criteria=["recruiters"])


def test_falsifiability_needs_both_fields():
    partial = ICPDefinition(key="partial_icp", label="P", purpose="professional_networking",
                            job_titles=["Head of Ops"],
                            exclusion_criteria=["recruiters"])
    assert not partial.is_falsifiable
    full = partial.model_copy(update={"observable_engagement_signals": ["posts monthly"]})
    assert full.is_falsifiable


# ------------------------------------------------------- opportunities ---

def test_opportunity_beyond_hypothesis_needs_a_usable_signal():
    with pytest.raises(ValidationError, match="requires at least one usable signal"):
        BusinessOpportunity(
            opportunity_id=BusinessOpportunity.make_id("cand_" + "0" * 16, "x"),
            candidate_id=candidate_id_for(None, "A", "B"),
            service_category="x", hypothesis="maybe",
            stage=OpportunityStage.signal_observed,
        )


def test_opportunity_stages_past_signal_need_user_confirmation():
    sig = Evidence(observed="public job posting",
                   source=prov.company_site("https://x.example"),
                   confidence=Confidence.medium)
    with pytest.raises(ValidationError, match="only be set from the user"):
        BusinessOpportunity(
            opportunity_id=BusinessOpportunity.make_id("cand_" + "0" * 16, "x"),
            candidate_id=candidate_id_for(None, "A", "B"),
            service_category="x", hypothesis="maybe",
            stage=OpportunityStage.qualified, signals=[sig],
            confirmed_by_user=False,
        )


# ------------------------------------------------------------ metrics ---

def test_segment_size_needs_a_basis():
    with pytest.raises(ValidationError, match="what it was counted from"):
        AudienceSegment(key="seg_one", label="S", size=400)


def test_acceptance_rate_cannot_exceed_invitations():
    with pytest.raises(ValidationError, match="acceptances against"):
        FunnelMetrics(invitations_manually_sent=2, invitations_accepted=5)


def test_acceptance_rate_without_a_denominator_is_rejected():
    with pytest.raises(ValidationError, match="no invitations sent"):
        FunnelMetrics(invitations_manually_sent=0, acceptance_rate=0.5)


def test_content_metrics_keep_none_distinct_from_zero():
    p = ContentAnalytics(post_ref="x", source=prov.analytics_export("e.csv"))
    assert p.engagement_total is None and p.engagement_rate is None
    q = ContentAnalytics(post_ref="y", impressions=100, reactions=5,
                         source=prov.analytics_export("e.csv"))
    assert q.engagement_total == 5 and q.engagement_rate == 0.05


def test_interaction_cannot_be_in_the_future():
    with pytest.raises(ValidationError, match="cannot be recorded in the future"):
        RelationshipEvent(candidate_id=candidate_id_for(None, "A", "B"),
                          occurred_on=date.today() + timedelta(days=1),
                          channel="linkedin_dm", direction="outbound",
                          summary="x")
