"""Imports: the whole input surface of the bundle, so the whole privacy surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from lni.importers import (
    COLUMN_ALIASES, import_candidates_csv, import_connections_export,
    import_post_analytics, sniff_columns,
)
from lni.models import Seniority

CANDIDATES_CSV = """Full Name,LinkedIn URL,Title,Company,Location,Industry,Personal Email,Tags
Dana Whitfield,https://www.linkedin.com/in/dana-whitfield/,VP Operations,Northfield Foods,"Chicago, US",Food production,dana@x.com,"inventory|planning"
,https://linkedin.com/in/anon-person,Plant Manager,Harborline,,,,
Rory Reseller,not-a-url,Consultant,Reseller Co,,,,
,,,,,,,
Sam Okoye,https://linkedin.com/in/sam-okoye,Founder,Okoye Labs,Lagos,Software,,
"""

ANALYTICS_CSV = """Post URL,Date,Impressions,Reactions,Comments,Reposts,New followers,Topic
https://linkedin.com/feed/update/1,2026-10-02,"12,400",180,34,9,21,inventory accuracy
https://linkedin.com/feed/update/2,14/10/2026,8900,96,12,2,,demand planning
https://linkedin.com/feed/update/3,2026-11-01,15200,240,61,14,33,"inventory accuracy, ERP"
,2026-11-05,100,1,0,0,0,orphan
"""

# LinkedIn ships three notes lines before the header in Connections.csv.
CONNECTIONS_CSV = """Notes:
"When exporting your connection data, you may notice that some of the fields are empty."

First Name,Last Name,URL,Email Address,Company,Position,Connected On
Priya,Nair,https://www.linkedin.com/in/priya-nair,,Northfield Foods,VP Operations,18 Nov 2026
Alex,Stone,https://www.linkedin.com/in/alex-stone,alex@x.com,Westmark,Director of Supply Chain,02 Mar 2025
"""


@pytest.fixture
def cand_csv(tmp_path):
    p = tmp_path / "cands.csv"
    p.write_text(CANDIDATES_CSV, encoding="utf-8")
    return p


@pytest.fixture
def analytics_csv(tmp_path):
    p = tmp_path / "posts.csv"
    p.write_text(ANALYTICS_CSV, encoding="utf-8")
    return p


@pytest.fixture
def connections_csv(tmp_path):
    p = tmp_path / "Connections.csv"
    p.write_text(CONNECTIONS_CSV, encoding="utf-8")
    return p


# ------------------------------------------------------------ headers ---

def test_headers_are_matched_by_alias_not_exact_string():
    mapping, unmapped = sniff_columns(
        ["Full Name", "LinkedIn URL", "Title", "Employer", "Mystery Column"])
    assert mapping["name"] == "Full Name"
    assert mapping["profile_url"] == "LinkedIn URL"
    assert mapping["professional_title"] == "Title"
    assert mapping["company"] == "Employer"
    assert unmapped == ["Mystery Column"]


def test_unmapped_columns_are_reported_not_guessed(cand_csv, settings):
    report = import_candidates_csv(cand_csv, settings)
    assert "Personal Email" in report.unmapped_columns or \
           "Personal Email" in report.dropped_fields


def test_alias_table_covers_both_name_shapes():
    assert "first name" in COLUMN_ALIASES["first_name"]
    assert "full name" in COLUMN_ALIASES["name"]


# --------------------------------------------------------- candidates ---

def test_rows_parse_with_provenance_and_missing_fields(cand_csv, settings):
    report = import_candidates_csv(cand_csv, settings)
    assert report.rows_read == 5
    names = [c.name for c in report.candidates]
    assert "Dana Whitfield" in names and "Sam Okoye" in names
    dana = next(c for c in report.candidates if c.name == "Dana Whitfield")
    assert dana.sources and dana.sources[0].kind.value == "user_supplied_csv"
    assert "row 2" in dana.sources[0].detail
    assert dana.last_verified is not None


def test_a_row_with_no_name_and_no_url_is_skipped(cand_csv, settings):
    report = import_candidates_csv(cand_csv, settings)
    assert any("no name and no profile URL" in reason for _row, reason in report.skipped)


def test_a_url_with_no_name_is_kept_and_the_gap_recorded(cand_csv, settings):
    report = import_candidates_csv(cand_csv, settings)
    anon = next(c for c in report.candidates if c.name == "(name not supplied)")
    assert anon.profile_url.endswith("/in/anon-person")
    assert "industry" in anon.missing_fields


def test_an_unreadable_url_warns_rather_than_dropping_the_person(cand_csv, settings):
    report = import_candidates_csv(cand_csv, settings)
    assert any("unreadable profile URL" in w for _row, w in report.warnings)
    rory = next(c for c in report.candidates if c.name == "Rory Reseller")
    assert rory.profile_url is None
    assert rory.identity_basis == "name_company"


def test_forbidden_columns_are_dropped_on_import(cand_csv, settings):
    report = import_candidates_csv(cand_csv, settings)
    assert "Personal Email" in report.dropped_fields
    for c in report.candidates:
        assert "dana@x.com" not in (c.notes or "")


@pytest.mark.parametrize("title,expected", [
    ("VP Operations", Seniority.vp),
    ("Founder", Seniority.founder_owner),
    ("Chief Operating Officer", Seniority.c_level),
    ("Head of Supply Chain", Seniority.director),
    ("Plant Manager", Seniority.manager),
    ("Staff Engineer", Seniority.lead),
    ("Senior Analyst", Seniority.senior_ic),
    ("Graduate Trainee", Seniority.student_early_career),
    ("Gardener", Seniority.unknown),
])
def test_seniority_is_inferred_from_the_title(tmp_path, settings, title, expected):
    p = tmp_path / "one.csv"
    p.write_text(f"Name,LinkedIn URL,Title\nX Person,https://linkedin.com/in/xp,{title}\n")
    report = import_candidates_csv(p, settings)
    assert report.candidates[0].seniority is expected


def test_the_summary_reports_what_happened(cand_csv, settings):
    summary = import_candidates_csv(cand_csv, settings).summary()
    for fragment in ("row(s) read", "candidate(s) parsed", "skipped",
                     "privacy filter"):
        assert fragment in summary


# ------------------------------------------------- connections export ---

def test_linkedin_preamble_is_skipped(connections_csv, settings):
    report = import_connections_export(connections_csv, settings)
    assert report.rows_read == 2
    names = sorted(c.name for c in report.candidates)
    assert names == ["Alex Stone", "Priya Nair"]


def test_connections_export_is_stamped_as_the_users_own_data(connections_csv, settings):
    report = import_connections_export(connections_csv, settings)
    assert all(c.sources[0].kind.value == "linkedin_data_export"
               for c in report.candidates)


def test_email_in_a_connections_export_is_dropped(connections_csv, settings):
    report = import_connections_export(connections_csv, settings)
    for c in report.candidates:
        assert "alex@x.com" not in c.model_dump_json()


# ------------------------------------------------------- analytics ---

def test_analytics_rows_parse_with_number_and_date_formats(analytics_csv, settings):
    report = import_post_analytics(analytics_csv, settings, covers="2026-10..2026-11")
    assert len(report.posts) == 3
    first = report.posts[0]
    assert first.impressions == 12400, "thousands separators must parse"
    assert first.followers_gained == 21
    second = report.posts[1]
    assert second.published_on is not None, "dd/mm/yyyy must parse"
    assert second.followers_gained is None, "an empty cell is unknown, not zero"


def test_multiple_topics_in_one_cell_split(analytics_csv, settings):
    report = import_post_analytics(analytics_csv, settings)
    third = report.posts[2]
    assert set(third.topics) == {"inventory accuracy", "ERP"}


def test_a_row_with_no_post_reference_is_skipped(analytics_csv, settings):
    report = import_post_analytics(analytics_csv, settings)
    assert any("no post reference" in reason for _row, reason in report.skipped)


def test_topic_map_labels_posts_the_export_does_not(tmp_path, settings):
    p = tmp_path / "bare.csv"
    p.write_text("Post URL,Impressions\nhttps://linkedin.com/feed/update/99,500\n")
    report = import_post_analytics(p, settings,
                                   topic_map={"update/99": ["inventory accuracy"]})
    assert report.posts[0].topics == ["inventory accuracy"]


def test_analytics_provenance_records_the_window(analytics_csv, settings):
    report = import_post_analytics(analytics_csv, settings, covers="2026-10..2026-11")
    assert "2026-10..2026-11" in report.posts[0].source.detail
