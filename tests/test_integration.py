"""The master workflow, end to end, and the CLI.

Walks the twelve steps in `SKILL.md` against an in-memory store, including the
one step that matters most: step 9, where nothing happens automatically.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from lni.cli import main
from lni.crm import NetworkCRM
from lni.exporters import candidates_to_csv, shortlist_to_csv
from lni.importers import import_candidates_csv
from lni.models import (
    ActionClass, Confidence, CRMStatus, ConnectionRecommendation, Evidence,
    InvitationDraft, RelationshipEvent, Seniority, TouchChannel,
)
from lni.propensity import ObservedSignal
from lni.reporting import build_report
from lni.safety import SafetyRefusal
from lni.scoring import ActivityFact, InfluenceFacts, ScoringInput, rank, score_candidate
from lni import provenance as prov
from tests.conftest import make_candidate

ROOT = Path(__file__).resolve().parents[1]


def test_the_twelve_step_workflow(b2b_crm, b2b_settings, tmp_path):
    crm, settings = b2b_crm, b2b_settings
    today = date.today()
    src = prov.user_note("seen in my own notifications")

    # Steps 1-3: configuration is in place (the b2b example).
    assert settings.profile.primary_objective
    assert any(i.is_falsifiable for i in settings.active_icps)

    # Step 4: discovery, from an authorised source.
    csv = tmp_path / "attendees.csv"
    csv.write_text(
        "Full Name,LinkedIn URL,Title,Company,Industry,Location,Company size\n"
        "Dana Whitfield,https://linkedin.com/in/dana-whitfield,VP Operations,"
        "Northfield Foods,Food and beverage manufacturing,United States,201-500\n"
        "Maya Quiet,https://linkedin.com/in/maya-quiet,Plant Manager,"
        "Harborline Foods,Food production,Canada,51-200\n"
        "Rory Reseller,https://linkedin.com/in/rory-reseller,Consultant,"
        "Reseller Co,Food and beverage manufacturing,United States,201-500\n",
        encoding="utf-8")
    report = import_candidates_csv(csv, settings, default_icp="business_development")
    assert len(report.candidates) == 3
    for c in report.candidates:
        crm.upsert(c)
    assert crm.count() == 3

    dana = crm.by_url("https://linkedin.com/in/dana-whitfield")
    maya = crm.by_url("https://linkedin.com/in/maya-quiet")
    rory = crm.by_url("https://linkedin.com/in/rory-reseller")
    assert dana and maya and rory

    # Step 5: score and classify. Dana has evidence; Maya has none; Rory is out.
    inputs = {
        dana.candidate_id: ScoringInput(
            candidate=dana, icps=settings.active_icps,
            engagement_signals=[
                ObservedSignal("substantive_comment", today - timedelta(days=3), src,
                               "long reply on stock counts", "inventory accuracy"),
                ObservedSignal("reply_to_user", today - timedelta(days=8), src, "replied"),
                ObservedSignal("repeat_engagement", today - timedelta(days=18), src, "again"),
            ],
            activity=[ActivityFact("posted about a WMS migration",
                                   today - timedelta(days=6), src),
                      ActivityFact("commented on a peer's capacity post",
                                   today - timedelta(days=14), src)],
            influence=InfluenceFacts(publishes_regularly=True, speaks_at_events=True,
                                     followers=4200, source=src),
            candidate_topics=["inventory accuracy"],
            opportunity_score=72.0,
            opportunity_evidence=[Evidence(
                observed="careers page lists an inventory analyst opening",
                source=prov.company_site("https://northfield.example/careers"),
                confidence=Confidence.medium)]),
        maya.candidate_id: ScoringInput(candidate=maya, icps=settings.active_icps),
        rory.candidate_id: ScoringInput(candidate=rory, icps=settings.active_icps),
    }
    scores = {}
    for cid, inp in inputs.items():
        score, propensity = score_candidate(inp, settings, today=today)
        crm.save_score(score)
        crm.save_propensity(propensity)
        scores[cid] = score

    assert scores[dana.candidate_id].priority.value == "priority_1"
    assert scores[dana.candidate_id].abstentions == [], "a complete record should not abstain"
    assert scores[maya.candidate_id].priority.value == "monitor"
    assert scores[rory.candidate_id].priority.value == "excluded"
    assert scores[rory.candidate_id].excluded_by

    # Step 6: the shortlist, in priority order.
    ordered = rank(scores.values())
    assert ordered[0].candidate_id == dana.candidate_id
    for cid in (dana.candidate_id, maya.candidate_id):
        crm.set_status(cid, CRMStatus.researching)
        crm.set_status(cid, CRMStatus.qualified)
    crm.set_status(dana.candidate_id, CRMStatus.shortlisted)

    # Step 7: a draft, with a real reason and no pitch.
    rec = ConnectionRecommendation(
        candidate_id=dana.candidate_id,
        rationale="She replied to your comment on monthly stock counts and wrote "
                  "three paragraphs of her own last week.",
        shared_context=["spoke at the same supply-chain summit, Oct 2026"],
        recommended_conversation_topic="reconciling counts against the system",
        profile_context=["VP Operations, Northfield Foods, 201-500, US"],
        follow_up_approach="if she accepts and says nothing, comment on her next post")
    crm.save_recommendation(rec)
    body = ("Dana - your point about reconciling counts against the system landed. "
            "We hit the same wall at a 300-person site. Would be good to compare notes.")
    draft = InvitationDraft(candidate_id=dana.candidate_id, variant_label="direct",
                            body=body, char_count=len(body))
    crm.save_draft(draft)
    crm.set_status(dana.candidate_id, CRMStatus.invitation_prepared)

    # Step 8: the review card says who performs the action.
    card = crm.governor.approval_card(
        action="connection invitations", items=[draft.body],
        context={"Target": dana.profile_url})
    assert "you, in LinkedIn" in card
    assert "Nothing is recorded as sent until you say so" in card

    # Step 9: the user acts. Nothing automated exists to do it for them.
    for action in (ActionClass.send_invitation, ActionClass.send_message,
                   ActionClass.automate_engagement):
        assert crm.governor.check(action).refused
    assert not hasattr(crm, "send")
    assert not any(hasattr(crm, n) for n in ("send_invitation", "publish", "post"))

    # Step 10: record the confirmed outcome.
    crm.set_status(dana.candidate_id, CRMStatus.manually_invited, confirmed_by_user=True)
    crm.set_status(dana.candidate_id, CRMStatus.accepted, confirmed_by_user=True)
    assert crm.get(dana.candidate_id).crm_status is CRMStatus.accepted

    # Step 11: a substantive interaction.
    crm.add_event(RelationshipEvent(
        candidate_id=dana.candidate_id, occurred_on=today,
        channel=TouchChannel.linkedin_dm, direction="outbound",
        summary="sent her the reconciliation write-up", substantive=True))

    # Step 12: the report, with its gaps labelled.
    period = build_report(crm, settings, period="weekly")
    m = period.metrics
    assert m.profiles_researched == 3
    assert m.invitations_manually_sent == 1
    assert m.invitations_accepted == 1
    assert m.acceptance_rate == 1.0
    assert m.meaningful_interactions == 1
    assert m.followers_gained is None and "followers_gained" in m.unavailable
    assert period.attribution_limits

    # The audit trail covers the run.
    summary = crm.audit.summarise()
    assert summary["lines"] > 10
    assert summary["by_decision"].get("refused", 0) >= 3  # the step-9 refusals


def test_the_whole_run_is_auditable(b2b_crm):
    b2b_crm.governor.guard("scrape their profiles")
    b2b_crm.governor.guard("draft an invitation")
    refusals = b2b_crm.audit.refusals()
    assert refusals
    assert all(r.rule_cited for r in refusals)
    assert all(r.occurred_at for r in refusals)


def test_exports_are_gated_and_then_work(b2b_crm, b2b_settings, tmp_path):
    c = make_candidate("Dana Whitfield", professional_title="VP Operations",
                       seniority=Seniority.vp, primary_icp_key="business_development")
    b2b_crm.upsert(c)
    with pytest.raises(SafetyRefusal):
        candidates_to_csv(b2b_crm, [c])
    out = tmp_path / "out.csv"
    text = candidates_to_csv(b2b_crm, [c], path=out, approved_by_user=True)
    assert out.is_file()
    assert "Dana Whitfield" in text
    assert "candidate_id,name,profile_url" in text
    # The export carries provenance and confidence, not just a name and a score.
    assert "source_kinds" in text and "last_verified" in text and "confidence" in text


def test_the_export_omits_free_text_notes(b2b_crm, tmp_path):
    c = make_candidate("Dana Whitfield", notes="private thought about her")
    b2b_crm.upsert(c)
    text = candidates_to_csv(b2b_crm, [c], approved_by_user=True)
    assert "private thought" not in text


# ------------------------------------------------------------- the CLI ---

def run(args, db):
    return main(["--db", str(db), *args])


def test_cli_config_check_succeeds(tmp_path, capsys):
    assert run(["config-check"], tmp_path / "t.db") == 0
    out = capsys.readouterr().out
    assert "Configuration loads" in out
    assert "Safety rules loaded: 11" in out


def test_cli_refuses_a_prohibited_request(tmp_path, capsys):
    code = run(["safety-check", "automate the invites"], tmp_path / "t.db")
    assert code == 3
    out = capsys.readouterr().out
    assert "no_automated_invitations" in out
    assert "What I can do instead" in out


def test_cli_allows_supported_work(tmp_path, capsys):
    assert run(["safety-check", "draft a note for this person"], tmp_path / "t.db") == 0
    assert "allowed" in capsys.readouterr().out


def test_cli_missing_reports_questions_not_guesses(tmp_path, capsys):
    assert run(["missing", "linkedin-lead-intelligence"], tmp_path / "t.db") == 0
    out = capsys.readouterr().out
    assert "business_services.categories" in out
    assert "Ask, do not assume" in out


def test_cli_full_cycle(tmp_path, capsys):
    db = tmp_path / "cli.db"
    csv = tmp_path / "people.csv"
    csv.write_text(
        "Full Name,LinkedIn URL,Title,Company,Industry,Location,Company size\n"
        "Dana Whitfield,https://linkedin.com/in/dana-whitfield,VP Operations,"
        "Northfield Foods,Food and beverage manufacturing,United States,201-500\n",
        encoding="utf-8")
    extra = ["--extra-config", str(ROOT / "config/examples/b2b-sales.yaml")]

    assert main(["--db", str(db), "init"]) == 0
    assert main(["--db", str(db), *extra, "import-candidates", str(csv),
                 "--icp", "business_development"]) == 0
    assert main(["--db", str(db), *extra, "score", "--all"]) == 0
    capsys.readouterr()

    assert main(["--db", str(db), "shortlist"]) == 0
    out = capsys.readouterr().out
    assert "Invitations are yours to send in LinkedIn" in out

    assert main(["--db", str(db), "report", "--period", "weekly"]) == 0
    out = capsys.readouterr().out
    assert "unavailable" in out
    assert "What this cannot attribute" in out

    assert main(["--db", str(db), "audit", "--summary"]) == 0
    assert '"lines"' in capsys.readouterr().out

    assert main(["--db", str(db), "export"]) == 3  # refused without approval
    assert main(["--db", str(db), "export", "--approve",
                 "-o", str(tmp_path / "e.csv")]) == 0


def test_cli_status_refuses_an_unconfirmed_linkedin_fact(tmp_path, capsys):
    db = tmp_path / "s.db"
    csv = tmp_path / "p.csv"
    csv.write_text("Full Name,LinkedIn URL\nDana W,https://linkedin.com/in/dana-w\n")
    main(["--db", str(db), "import-candidates", str(csv)])
    capsys.readouterr()
    from lni.models import candidate_id_for

    cid = candidate_id_for("https://linkedin.com/in/dana-w", "Dana W")
    for s in ("researching", "qualified", "shortlisted", "invitation_prepared"):
        assert main(["--db", str(db), "status", cid, s]) == 0
    assert main(["--db", str(db), "status", cid, "manually_invited"]) == 1
    assert main(["--db", str(db), "status", cid, "manually_invited", "--confirmed"]) == 0


def test_cli_forget_requires_approval(tmp_path, capsys):
    db = tmp_path / "f.db"
    csv = tmp_path / "p.csv"
    csv.write_text("Full Name,LinkedIn URL\nDana W,https://linkedin.com/in/dana-w\n")
    main(["--db", str(db), "import-candidates", str(csv)])
    capsys.readouterr()
    from lni.models import candidate_id_for

    cid = candidate_id_for("https://linkedin.com/in/dana-w", "Dana W")
    assert main(["--db", str(db), "forget", cid]) == 3
    assert main(["--db", str(db), "forget", cid, "--approve"]) == 0
    out = capsys.readouterr().out
    assert "audit line recording this deletion is kept" in out
