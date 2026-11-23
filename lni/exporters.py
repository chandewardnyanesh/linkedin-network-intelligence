"""Writing data out: CSV for the user, JSON for a subject export.

Both are gated. An export leaves the machine, so `lni.safety` treats it as an
action needing the user's explicit go-ahead, and the audit trail records it.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from pathlib import Path
from typing import Iterable, Optional, Sequence

from .config import Settings
from .crm import NetworkCRM
from .models import ActionClass, Candidate, CandidateScore, CRMStatus, PeriodReport

__all__ = ["candidates_to_csv", "shortlist_to_csv", "subject_export_json",
           "CANDIDATE_COLUMNS"]

#: The columns a user gets. Deliberately no free-text notes field: an export is
#: usually going into a spreadsheet that gets shared, and a private note about
#: a person is the thing most likely to be regretted there.
CANDIDATE_COLUMNS: tuple[str, ...] = (
    "candidate_id", "name", "profile_url", "professional_title", "company",
    "industry", "geography", "seniority", "primary_icp_key", "relevance_score",
    "priority", "engagement_propensity", "business_opportunity_score",
    "confidence", "crm_status", "source_kinds", "last_verified",
    "missing_fields",
)


def _row(c: Candidate, score: Optional[CandidateScore]) -> dict:
    return {
        "candidate_id": c.candidate_id,
        "name": c.name,
        "profile_url": c.profile_url or "",
        "professional_title": c.professional_title or "",
        "company": c.company or "",
        "industry": c.industry or "",
        "geography": c.geography or "",
        "seniority": c.seniority.value,
        "primary_icp_key": c.primary_icp_key or "",
        "relevance_score": "" if c.relevance_score is None else f"{c.relevance_score:.1f}",
        "priority": score.priority.value if score else "",
        "engagement_propensity": c.engagement_propensity.value,
        "business_opportunity_score": (
            "" if c.business_opportunity_score is None
            else f"{c.business_opportunity_score:.1f}"
        ),
        "confidence": c.confidence.value,
        "crm_status": c.crm_status.value,
        "source_kinds": "|".join(sorted({s.kind.value for s in c.sources})),
        "last_verified": c.last_verified.isoformat() if c.last_verified else "",
        "missing_fields": "|".join(c.missing_fields),
    }


def candidates_to_csv(
    crm: NetworkCRM,
    candidates: Sequence[Candidate],
    *,
    path: Optional[Path | str] = None,
    approved_by_user: bool = False,
) -> str:
    """Write candidates to CSV. Returns the CSV text; also writes it when `path` is set."""
    crm.governor.check(
        ActionClass.export_user_data, approved_by_user=approved_by_user
    ).raise_if_refused()
    if not approved_by_user:
        from .safety import SafetyRefusal

        raise SafetyRefusal(
            "an export needs your explicit go-ahead first",
            rule_id="requires_human_approval",
            action_class=ActionClass.export_user_data,
        )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(CANDIDATE_COLUMNS),
                            lineterminator="\n")
    writer.writeheader()
    for c in candidates:
        writer.writerow(_row(c, crm.get_score(c.candidate_id)))
    text = buf.getvalue()
    if path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    crm.audit.record(
        action_class=ActionClass.export_user_data, decision="approved",
        summary=f"exported {len(candidates)} candidate row(s)"
                + (f" to {path}" if path else ""),
        actor="user", skill=crm.governor.skill,
    )
    return text


def shortlist_to_csv(
    crm: NetworkCRM,
    settings: Settings,
    *,
    path: Optional[Path | str] = None,
    approved_by_user: bool = False,
    limit: Optional[int] = None,
) -> str:
    """The current shortlist, in priority order, for working through by hand."""
    size = limit or settings.workflow.shortlist_size
    candidates = crm.filter(
        status=[CRMStatus.shortlisted, CRMStatus.invitation_prepared],
        order_by="relevance", limit=size,
    )
    return candidates_to_csv(crm, candidates, path=path,
                             approved_by_user=approved_by_user)


def subject_export_json(
    crm: NetworkCRM,
    candidate_id: str,
    *,
    path: Optional[Path | str] = None,
    approved_by_user: bool = False,
) -> str:
    """Everything held about one person, as JSON. A data-subject request."""
    data = crm.subject_export(candidate_id, approved_by_user=approved_by_user)
    text = json.dumps(data, indent=2, default=str)
    if path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return text
