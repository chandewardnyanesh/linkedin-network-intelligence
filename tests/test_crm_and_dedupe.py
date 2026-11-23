"""The CRM: identity, merging, the status machine, privacy, subject rights."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from lni.crm import CRMError
from lni.dedupe import compare, find_duplicates, normalise_company, normalise_name
from lni.models import (
    CRMStatus, Confidence, RelationshipEvent, Seniority, TouchChannel,
)
from lni.safety import SafetyRefusal
from lni import provenance as prov
from tests.conftest import make_candidate


# ------------------------------------------------------------ normalise ---

@pytest.mark.parametrize("raw,expected", [
    ("Dr. José  Álvarez-Pérez, PhD", "jose alvarez perez"),
    ("MR Sam Okoye Jr", "sam okoye"),
    ("Priya   Nair 🚀", "priya nair"),
])
def test_name_normalisation(raw, expected):
    assert normalise_name(raw) == expected


def test_name_order_is_preserved_because_reordering_merges_two_people():
    assert normalise_name("Hassan Ali") != normalise_name("Ali Hassan")


@pytest.mark.parametrize("raw,expected", [
    ("Acme Technologies Pvt. Ltd.", "acme"),
    ("Northfield Foods GmbH", "northfield foods"),
    (None, ""),
])
def test_company_normalisation(raw, expected):
    assert normalise_company(raw) == expected


# ------------------------------------------------------------- dedupe ---

def test_same_url_different_spellings_is_one_record(crm):
    a = make_candidate("Dana Whitfield", profile_url="https://WWW.linkedin.com/in/Dana-W/")
    b = make_candidate("Dana W", profile_url="https://linkedin.com/in/dana-w?trk=x")
    assert crm.upsert(a).action == "created"
    assert crm.upsert(b).action in ("unchanged", "updated")
    assert crm.count() == 1


def test_two_different_urls_are_never_merged():
    a = make_candidate("Dana Whitfield", profile_url="https://linkedin.com/in/dana-1")
    b = make_candidate("Dana Whitfield", profile_url="https://linkedin.com/in/dana-2")
    assert compare(a, b) is None


def test_same_name_and_company_without_urls_merges():
    a = make_candidate("Jose Alvarez-Perez", profile_url=None,
                       company="Acme Technologies Ltd")
    b = make_candidate("José Álvarez Pérez", profile_url=None, company="Acme")
    m = compare(a, b)
    assert m and m.auto_mergeable and m.kind == "exact_name_company"


def test_near_matches_are_reported_not_merged(crm):
    a = make_candidate("Jonathan Searle", profile_url=None, company="Westmark",
                       professional_title="Director of Supply Chain")
    b = make_candidate("Jonathon Searle", profile_url=None, company="Westmark",
                       professional_title="Director of Supply Chain")
    crm.upsert(a)
    result = crm.upsert(b)
    assert crm.count() == 2, "a near match must not be merged silently"
    assert result.possible_duplicates, "the near match must be reported"
    assert not result.possible_duplicates[0].auto_mergeable


def test_find_duplicates_orders_exact_before_probable():
    a = make_candidate("Dana Whitfield", profile_url=None, company="Acme Ltd")
    b = make_candidate("Dana Whitfield", profile_url=None, company="Acme")
    c = make_candidate("Dana Whitfeld", profile_url=None, company="Acme")
    kinds = [m.kind for m in find_duplicates([a, b, c])]
    assert kinds and kinds[0] in ("exact_url", "exact_name_company")


# -------------------------------------------------------------- merging ---

def test_update_fills_blanks_and_unions_lists(crm, strong_candidate):
    crm.upsert(strong_candidate)
    incoming = strong_candidate.model_copy(update={
        "industry": None,
        "tags": ["warehouse operations"],
        "sources": [prov.company_site("https://northfield.example/team")],
    })
    crm.upsert(incoming)
    stored = crm.get(strong_candidate.candidate_id)
    assert stored.industry == "Food and beverage manufacturing", "a blank must not overwrite"
    assert "warehouse operations" in stored.tags and "inventory accuracy" in stored.tags
    assert len(stored.sources) == 2


def test_an_import_never_moves_someone_backwards(crm, strong_candidate):
    crm.upsert(strong_candidate)
    crm.set_status(strong_candidate.candidate_id, CRMStatus.researching)
    crm.set_status(strong_candidate.candidate_id, CRMStatus.qualified)
    crm.upsert(strong_candidate)  # the file still says `discovered`
    assert crm.get(strong_candidate.candidate_id).crm_status is CRMStatus.qualified


def test_a_relevance_score_never_arrives_without_its_confidence(crm):
    a = make_candidate("Thin Record", profile_url=None, company="X")
    crm.upsert(a)
    incoming = a.model_copy(update={"relevance_score": 55.0,
                                    "confidence": Confidence.medium})
    crm.upsert(incoming)
    stored = crm.get(a.candidate_id)
    assert stored.relevance_score == 55.0 and stored.confidence is Confidence.medium


# -------------------------------------------------------- status machine ---

def test_the_happy_path_walks_the_whole_funnel(crm, strong_candidate):
    cid = crm.upsert(strong_candidate).candidate.candidate_id
    path = [
        (CRMStatus.researching, False), (CRMStatus.qualified, False),
        (CRMStatus.shortlisted, False), (CRMStatus.invitation_prepared, False),
        (CRMStatus.manually_invited, True), (CRMStatus.accepted, True),
        (CRMStatus.conversation_started, True), (CRMStatus.engaged, False),
        (CRMStatus.potential_lead, False), (CRMStatus.qualified_opportunity, False),
        (CRMStatus.converted, True),
    ]
    for status, confirmed in path:
        crm.set_status(cid, status, confirmed_by_user=confirmed)
    assert crm.get(cid).crm_status is CRMStatus.converted
    assert len(crm.status_history(cid)) == len(path)


def test_an_illegal_jump_is_refused_and_names_the_legal_next(crm, strong_candidate):
    cid = crm.upsert(strong_candidate).candidate.candidate_id
    with pytest.raises(CRMError, match="Legal next"):
        crm.set_status(cid, CRMStatus.converted)


def test_an_unconfirmed_linkedin_side_status_is_refused(crm, strong_candidate):
    cid = crm.upsert(strong_candidate).candidate.candidate_id
    for s in (CRMStatus.researching, CRMStatus.qualified, CRMStatus.shortlisted,
              CRMStatus.invitation_prepared):
        crm.set_status(cid, s)
    with pytest.raises(CRMError, match="only be set from the user"):
        crm.set_status(cid, CRMStatus.manually_invited, confirmed_by_user=False)


def test_archiving_is_available_from_anywhere(crm, strong_candidate):
    cid = crm.upsert(strong_candidate).candidate.candidate_id
    crm.set_status(cid, CRMStatus.archived)
    assert crm.get(cid).crm_status is CRMStatus.archived
    crm.set_status(cid, CRMStatus.researching)  # revivable


def test_status_on_an_unknown_candidate_raises(crm):
    with pytest.raises(CRMError, match="no candidate"):
        crm.set_status("cand_" + "0" * 16, CRMStatus.qualified)


# ------------------------------------------------------- interactions ---

def test_interactions_and_last_touch(crm, strong_candidate, today):
    cid = crm.upsert(strong_candidate).candidate.candidate_id
    crm.add_event(RelationshipEvent(
        candidate_id=cid, occurred_on=today - timedelta(days=30),
        channel=TouchChannel.linkedin_comment, direction="outbound",
        summary="commented on her post", substantive=True))
    crm.add_event(RelationshipEvent(
        candidate_id=cid, occurred_on=today - timedelta(days=2),
        channel=TouchChannel.linkedin_reaction, direction="inbound",
        summary="reacted to mine"))
    assert crm.last_touch(cid) == today - timedelta(days=30)
    assert crm.last_touch(cid, outbound_only=False) == today - timedelta(days=2)
    assert len(crm.events(cid)) == 2


def test_an_event_for_an_unknown_candidate_is_refused(crm, today):
    with pytest.raises(CRMError):
        crm.add_event(RelationshipEvent(
            candidate_id="cand_" + "0" * 16, occurred_on=today,
            channel=TouchChannel.email, direction="outbound", summary="x"))


# ---------------------------------------------------------- filtering ---

def test_filtering_and_segmentation(crm):
    for i, (name, icp, status) in enumerate([
        ("A One", "business_development", CRMStatus.qualified),
        ("B Two", "business_development", CRMStatus.discovered),
        ("C Three", "professional_networking", CRMStatus.qualified),
    ]):
        c = make_candidate(name, primary_icp_key=icp, geography="United States",
                           tags=["ops"] if i == 0 else [])
        crm.upsert(c)
        if status is not CRMStatus.discovered:
            crm.set_status(c.candidate_id, CRMStatus.researching)
            crm.set_status(c.candidate_id, status)
    assert len(crm.filter(status=[CRMStatus.qualified])) == 2
    assert len(crm.filter(icp_key="business_development")) == 2
    assert len(crm.filter(geography="united states")) == 3
    assert len(crm.filter(tag="ops")) == 1
    assert crm.status_counts()["qualified"] == 2


# ------------------------------------------------------------- privacy ---

def test_forbidden_fields_are_dropped_on_the_way_in(crm, strong_candidate):
    res = crm.upsert(strong_candidate,
                     extra_fields={"personal_email": "x@y.com", "salary": "100k"})
    assert "personal_email" in res.dropped_fields
    assert "salary" in res.dropped_fields


def test_fields_outside_the_allow_list_are_discarded(crm, strong_candidate):
    res = crm.upsert(strong_candidate, extra_fields={"favourite_colour": "teal"})
    assert "favourite_colour" in res.dropped_fields


def test_export_and_deletion_both_need_approval(crm, strong_candidate):
    cid = crm.upsert(strong_candidate).candidate.candidate_id
    with pytest.raises(SafetyRefusal):
        crm.subject_export(cid)
    with pytest.raises(SafetyRefusal):
        crm.forget(cid)


def test_subject_export_returns_everything_held(crm, strong_candidate, today):
    cid = crm.upsert(strong_candidate).candidate.candidate_id
    crm.set_status(cid, CRMStatus.researching)
    crm.add_event(RelationshipEvent(
        candidate_id=cid, occurred_on=today, channel=TouchChannel.email,
        direction="outbound", summary="emailed"))
    data = crm.subject_export(cid, approved_by_user=True)
    assert set(data["tables"]) >= {"candidates", "status_changes", "relationship_events"}


def test_deletion_removes_the_person_and_keeps_the_audit_line(crm, audit,
                                                              strong_candidate, today):
    cid = crm.upsert(strong_candidate).candidate.candidate_id
    crm.set_status(cid, CRMStatus.researching)
    crm.add_event(RelationshipEvent(
        candidate_id=cid, occurred_on=today, channel=TouchChannel.email,
        direction="outbound", summary="emailed"))
    before = audit.count()
    counts = crm.forget(cid, approved_by_user=True)
    assert counts["candidates"] == 1
    assert crm.get(cid) is None
    assert crm.count() == 0
    assert audit.count() > before
    assert any("deleted all records" in e.summary for e in audit.read(limit=5))


def test_untouched_records_are_surfaced_not_deleted(crm, strong_candidate):
    crm.upsert(strong_candidate)
    assert crm.untouched_since(days=0), "should surface for review"
    assert crm.count() == 1, "surfacing must not delete"


# ------------------------------------------------------------- storage ---

def test_schema_migrates_and_reports_its_version(db):
    assert db.schema_version == 1
    assert db.migrate() == 1  # idempotent


def test_candidate_round_trips_through_the_store(crm, strong_candidate):
    crm.upsert(strong_candidate)
    stored = crm.get(strong_candidate.candidate_id)
    assert stored.model_dump(mode="json") == strong_candidate.model_dump(mode="json")


def test_lookup_by_url_normalises_first(crm, strong_candidate):
    crm.upsert(strong_candidate)
    assert crm.by_url("HTTPS://WWW.LinkedIn.com/in/dana-whitfield/?trk=z") is not None
