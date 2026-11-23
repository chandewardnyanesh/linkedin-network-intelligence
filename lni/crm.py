"""The networking CRM: records, identity, status, history.

The repository the other eleven skills write through. Four behaviours are worth
knowing before reading the code:

* **Privacy filtering happens on the way in.** `privacy.never_store` fields are
  dropped at `upsert`, not at read time, so a field that should not be held is
  never written in the first place.
* **Status transitions are validated.** The legal graph lives in
  `models.LEGAL_TRANSITIONS`, and four statuses that assert a LinkedIn-side
  fact can only be set from the user's own confirmation.
* **Merging is conservative.** An exact identity match updates in place.
  Anything less is returned for the user to decide, never merged silently.
* **Nothing is mutated in place.** Reads return validated copies.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Iterable, Literal, Optional, Sequence

from .audit import AuditLog
from .config import Settings
from .db import Database
from .dedupe import DuplicateMatch, compare
from .models import (
    ActionClass, BusinessOpportunity, Candidate, CandidateScore, CRMStatus,
    Confidence, ConnectionRecommendation, InvitationDraft, LEGAL_TRANSITIONS,
    PriorityClass, PropensityAssessment, RelationshipEvent, StatusChange,
    utcnow,
)
from .safety import SafetyGovernor, SafetyRefusal

__all__ = ["NetworkCRM", "UpsertResult", "CRMError"]


class CRMError(RuntimeError):
    pass


class UpsertResult:
    """What happened to one record, so a caller can report it accurately."""

    def __init__(self, candidate: Candidate, action: Literal["created", "updated", "unchanged"],
                 dropped_fields: Sequence[str] = (),
                 possible_duplicates: Sequence[DuplicateMatch] = ()):
        self.candidate = candidate
        self.action = action
        self.dropped_fields = list(dropped_fields)
        self.possible_duplicates = list(possible_duplicates)

    def __repr__(self) -> str:  # pragma: no cover
        return (f"UpsertResult({self.candidate.candidate_id}, {self.action}, "
                f"dropped={self.dropped_fields}, dupes={len(self.possible_duplicates)})")


class NetworkCRM:
    def __init__(self, db: Database, settings: Settings,
                 audit: Optional[AuditLog] = None,
                 governor: Optional[SafetyGovernor] = None):
        self.db = db
        self.settings = settings
        self.audit = audit or AuditLog(db, settings)
        self.governor = governor or SafetyGovernor(settings, self.audit)

    # ------------------------------------------------------------ privacy ---
    def _strip_forbidden(self, payload: dict) -> tuple[dict, list[str]]:
        """Remove fields `privacy.never_store` forbids, before anything is written."""
        never = {f.lower() for f in self.settings.privacy.never_store}
        dropped: list[str] = []
        clean = dict(payload)
        for key in list(clean):
            if key.lower() in never:
                clean.pop(key)
                dropped.append(key)
        # Free-text fields can smuggle the same data in. Flag rather than edit:
        # silently rewriting a user's note is worse than telling them.
        return clean, dropped

    # ------------------------------------------------------------- upsert ---
    def upsert(self, candidate: Candidate, *, extra_fields: Optional[dict] = None,
               check_near_duplicates: bool = True) -> UpsertResult:
        """Create or update one candidate.

        `extra_fields` is anything an importer picked up that is not part of the
        model; it is filtered against `privacy.allowed_candidate_fields` and
        `privacy.never_store` and otherwise discarded, which is what data
        minimisation means in practice.
        """
        dropped: list[str] = []
        if extra_fields:
            _, dropped = self._strip_forbidden(extra_fields)
            allowed = set(self.settings.privacy.allowed_candidate_fields)
            for k in extra_fields:
                if k not in allowed and k not in dropped:
                    dropped.append(k)

        existing = self.get(candidate.candidate_id)
        near: list[DuplicateMatch] = []
        if existing is None and check_near_duplicates:
            near = self.near_duplicates(candidate)

        if existing is None:
            self._write_candidate(candidate, insert=True)
            self.audit.record(
                action_class=ActionClass.write_local_record,
                decision="allowed",
                summary=f"created candidate {candidate.name!r}",
                subject_id=candidate.candidate_id,
                skill=self.governor.skill,
            )
            return UpsertResult(candidate, "created", dropped, near)

        merged = self._merge(existing, candidate)
        if merged.model_dump(mode="json") == existing.model_dump(mode="json"):
            return UpsertResult(existing, "unchanged", dropped, near)
        merged = merged.model_copy(update={"updated_at": utcnow()})
        self._write_candidate(merged, insert=False)
        self.audit.record(
            action_class=ActionClass.write_local_record,
            decision="allowed",
            summary=f"updated candidate {merged.name!r}",
            subject_id=merged.candidate_id,
            skill=self.governor.skill,
        )
        return UpsertResult(merged, "updated", dropped, near)

    @staticmethod
    def _merge(existing: Candidate, incoming: Candidate) -> Candidate:
        """Fill blanks, union the lists, keep the existing CRM status.

        An import never moves someone backwards through the funnel, and never
        overwrites a field the user has already corrected with a blank from a
        file.
        """
        update: dict = {}
        for field in ("professional_title", "company", "industry", "geography",
                      "company_size_band", "primary_icp_key", "notes",
                      "business_opportunity_score"):
            if getattr(existing, field) in (None, "") and getattr(incoming, field) not in (None, ""):
                update[field] = getattr(incoming, field)
        # A relevance score travels with its confidence or not at all.
        if (existing.relevance_score is None and incoming.relevance_score is not None
                and incoming.confidence is not Confidence.none):
            update["relevance_score"] = incoming.relevance_score
            update["confidence"] = incoming.confidence
        if existing.seniority.value == "unknown" and incoming.seniority.value != "unknown":
            update["seniority"] = incoming.seniority
        for field in ("secondary_icp_keys", "shared_context", "tags", "missing_fields"):
            combined = list(dict.fromkeys(list(getattr(existing, field)) +
                                          list(getattr(incoming, field))))
            if combined != list(getattr(existing, field)):
                update[field] = combined
        seen = {(s.kind, s.detail) for s in existing.sources}
        new_sources = [s for s in incoming.sources if (s.kind, s.detail) not in seen]
        if new_sources:
            update["sources"] = list(existing.sources) + new_sources
        seen_ev = {e.observed for e in existing.evidence}
        new_ev = [e for e in incoming.evidence if e.observed not in seen_ev]
        if new_ev:
            update["evidence"] = list(existing.evidence) + new_ev
        if incoming.last_verified and (
            existing.last_verified is None or incoming.last_verified > existing.last_verified
        ):
            update["last_verified"] = incoming.last_verified
        return existing.model_copy(update=update) if update else existing

    def _write_candidate(self, c: Candidate, *, insert: bool) -> None:
        row = (
            c.candidate_id, c.profile_url, c.name, c.company, c.industry,
            c.geography, c.seniority.value, c.primary_icp_key, c.crm_status.value,
            c.relevance_score, c.engagement_propensity.value,
            c.business_opportunity_score, c.confidence.value,
            c.last_verified.isoformat() if c.last_verified else None,
            c.created_at.isoformat(), c.updated_at.isoformat(),
            c.model_dump_json(),
        )
        if insert:
            self.db.execute(
                """
                INSERT INTO candidates
                    (candidate_id, profile_url, name, company, industry, geography,
                     seniority, primary_icp, crm_status, relevance, propensity,
                     opportunity, confidence, last_verified, created_at, updated_at,
                     payload)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                row,
            )
        else:
            self.db.execute(
                """
                UPDATE candidates SET profile_url=?, name=?, company=?, industry=?,
                    geography=?, seniority=?, primary_icp=?, crm_status=?,
                    relevance=?, propensity=?, opportunity=?, confidence=?,
                    last_verified=?, created_at=?, updated_at=?, payload=?
                WHERE candidate_id=?
                """,
                row[1:] + (c.candidate_id,),
            )
        self.db.commit()

    # --------------------------------------------------------------- read ---
    def get(self, candidate_id: str) -> Optional[Candidate]:
        row = self.db.query_one(
            "SELECT payload FROM candidates WHERE candidate_id = ?", (candidate_id,)
        )
        return Candidate.model_validate_json(row[0]) if row else None

    def by_url(self, profile_url: str) -> Optional[Candidate]:
        from .models import normalise_profile_url

        row = self.db.query_one(
            "SELECT payload FROM candidates WHERE profile_url = ?",
            (normalise_profile_url(profile_url),),
        )
        return Candidate.model_validate_json(row[0]) if row else None

    def count(self, *, status: Optional[CRMStatus] = None) -> int:
        if status:
            row = self.db.query_one(
                "SELECT COUNT(*) FROM candidates WHERE crm_status = ?", (status.value,)
            )
        else:
            row = self.db.query_one("SELECT COUNT(*) FROM candidates")
        return int(row[0]) if row else 0

    def filter(
        self,
        *,
        status: Optional[Iterable[CRMStatus]] = None,
        icp_key: Optional[str] = None,
        min_relevance: Optional[float] = None,
        priority: Optional[PriorityClass] = None,
        company: Optional[str] = None,
        geography: Optional[str] = None,
        tag: Optional[str] = None,
        order_by: Literal["relevance", "updated", "name"] = "relevance",
        limit: int = 200,
    ) -> list[Candidate]:
        """Segmentation. Scalar columns are indexed; tags filter after rehydrate."""
        sql = ["SELECT c.payload FROM candidates c"]
        params: list[object] = []
        if priority:
            sql.append("JOIN scores s ON s.candidate_id = c.candidate_id")
        sql.append("WHERE 1=1")
        if status:
            vals = [s.value for s in status]
            sql.append(f"AND c.crm_status IN ({','.join('?' * len(vals))})")
            params.extend(vals)
        if icp_key:
            sql.append("AND c.primary_icp = ?")
            params.append(icp_key)
        if min_relevance is not None:
            sql.append("AND c.relevance >= ?")
            params.append(min_relevance)
        if priority:
            sql.append("AND s.priority = ?")
            params.append(priority.value)
        if company:
            sql.append("AND lower(c.company) = ?")
            params.append(company.lower())
        if geography:
            sql.append("AND lower(c.geography) = ?")
            params.append(geography.lower())
        column = {"relevance": "c.relevance DESC", "updated": "c.updated_at DESC",
                  "name": "c.name ASC"}[order_by]
        sql.append(f"ORDER BY {column} LIMIT ?")
        params.append(int(limit) * (3 if tag else 1))
        out = [Candidate.model_validate_json(r[0])
               for r in self.db.query(" ".join(sql), params)]
        if tag:
            out = [c for c in out if tag in c.tags][:limit]
        return out

    def all_candidates(self, limit: int = 100_000) -> list[Candidate]:
        return [Candidate.model_validate_json(r[0]) for r in
                self.db.query("SELECT payload FROM candidates LIMIT ?", (limit,))]

    def near_duplicates(self, candidate: Candidate, *, scan_limit: int = 2000
                        ) -> list[DuplicateMatch]:
        """Possible duplicates of one candidate, for the user to resolve.

        Scans records with a similar name only, so this stays cheap as the
        store grows.
        """
        from .dedupe import normalise_company, normalise_name

        target = normalise_name(candidate.name)
        parts = target.split(" ") if target else []
        # Scan on the surname and on the employer, not the given name: a
        # misspelled first name ("Jonathan"/"Jonathon") is exactly the case a
        # near-duplicate scan exists to catch, and a given-name LIKE misses it.
        surname = parts[-1] if parts else ""
        company = normalise_company(candidate.company)
        clauses, params = [], []
        if surname:
            clauses.append("lower(name) LIKE ?")
            params.append(f"%{surname}%")
        if company:
            clauses.append("lower(company) LIKE ?")
            params.append(f"%{company}%")
        if not clauses:
            return []
        params.append(scan_limit)
        rows = self.db.query(
            f"SELECT payload FROM candidates WHERE {' OR '.join(clauses)} LIMIT ?",
            params,
        )
        out = []
        for r in rows:
            other = Candidate.model_validate_json(r[0])
            if other.candidate_id == candidate.candidate_id:
                continue
            m = compare(candidate, other)
            if m:
                out.append(m)
        return out

    # ------------------------------------------------------------- status ---
    def set_status(
        self,
        candidate_id: str,
        to_status: CRMStatus,
        *,
        confirmed_by_user: bool = False,
        note: Optional[str] = None,
    ) -> StatusChange:
        """Move a candidate through the funnel.

        Raises `CRMError` on an illegal transition and on a user-confirmed-only
        status set without confirmation. Both are refusals to record something
        that is not known to be true.
        """
        c = self.get(candidate_id)
        if c is None:
            raise CRMError(f"no candidate {candidate_id!r}")
        if to_status not in LEGAL_TRANSITIONS.get(c.crm_status, set()) and to_status != c.crm_status:
            legal = sorted(s.value for s in LEGAL_TRANSITIONS.get(c.crm_status, set()))
            raise CRMError(
                f"{c.name}: cannot go from {c.crm_status.value} to "
                f"{to_status.value}. Legal next: {legal}"
            )
        try:
            change = StatusChange(
                candidate_id=candidate_id,
                from_status=c.crm_status,
                to_status=to_status,
                confirmed_by_user=confirmed_by_user,
                note=note,
            )
        except ValueError as exc:
            raise CRMError(str(exc)) from exc

        self.db.execute(
            """
            INSERT INTO status_changes
                (candidate_id, from_status, to_status, confirmed, changed_at, payload)
            VALUES (?,?,?,?,?,?)
            """,
            (candidate_id, c.crm_status.value, to_status.value,
             1 if confirmed_by_user else 0, change.changed_at.isoformat(),
             change.model_dump_json()),
        )
        self._write_candidate(
            c.model_copy(update={"crm_status": to_status, "updated_at": utcnow()}),
            insert=False,
        )
        self.audit.record(
            action_class=ActionClass.write_local_record,
            decision="allowed",
            summary=(f"status {c.crm_status.value} -> {to_status.value} for "
                     f"{c.name!r}" + (" (user-confirmed)" if confirmed_by_user else "")),
            subject_id=candidate_id,
            skill=self.governor.skill,
        )
        return change

    def status_history(self, candidate_id: str) -> list[StatusChange]:
        rows = self.db.query(
            "SELECT payload FROM status_changes WHERE candidate_id = ? "
            "ORDER BY changed_at ASC", (candidate_id,)
        )
        return [StatusChange.model_validate_json(r[0]) for r in rows]

    def status_counts(self) -> dict[str, int]:
        rows = self.db.query(
            "SELECT crm_status, COUNT(*) FROM candidates GROUP BY crm_status"
        )
        return {r[0]: int(r[1]) for r in rows}

    # -------------------------------------------------------- interactions ---
    def add_event(self, event: RelationshipEvent) -> None:
        if self.get(event.candidate_id) is None:
            raise CRMError(f"no candidate {event.candidate_id!r}")
        self.db.execute(
            """
            INSERT INTO relationship_events
                (candidate_id, occurred_on, channel, direction, substantive, payload)
            VALUES (?,?,?,?,?,?)
            """,
            (event.candidate_id, event.occurred_on.isoformat(), event.channel.value,
             event.direction, 1 if event.substantive else 0, event.model_dump_json()),
        )
        self.db.commit()

    def events(self, candidate_id: str, *, limit: int = 200) -> list[RelationshipEvent]:
        rows = self.db.query(
            "SELECT payload FROM relationship_events WHERE candidate_id = ? "
            "ORDER BY occurred_on DESC LIMIT ?", (candidate_id, limit)
        )
        return [RelationshipEvent.model_validate_json(r[0]) for r in rows]

    def last_touch(self, candidate_id: str, *, outbound_only: bool = True
                   ) -> Optional[date]:
        sql = ("SELECT MAX(occurred_on) FROM relationship_events WHERE candidate_id = ?")
        params: list[object] = [candidate_id]
        if outbound_only:
            sql += " AND direction = ?"
            params.append("outbound")
        row = self.db.query_one(sql, params)
        return date.fromisoformat(row[0]) if row and row[0] else None

    def events_between(self, start: date, end: date) -> list[RelationshipEvent]:
        rows = self.db.query(
            "SELECT payload FROM relationship_events WHERE occurred_on >= ? "
            "AND occurred_on <= ?", (start.isoformat(), end.isoformat())
        )
        return [RelationshipEvent.model_validate_json(r[0]) for r in rows]

    # ------------------------------------------------- derived artefacts ---
    def save_score(self, score: CandidateScore) -> None:
        self.db.execute(
            """
            INSERT INTO scores (candidate_id, total, priority, confidence,
                                weights_profile, abstentions, scored_at, payload)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                total=excluded.total, priority=excluded.priority,
                confidence=excluded.confidence,
                weights_profile=excluded.weights_profile,
                abstentions=excluded.abstentions, scored_at=excluded.scored_at,
                payload=excluded.payload
            """,
            (score.candidate_id, score.total, score.priority.value,
             score.confidence.value, score.weights_profile, len(score.abstentions),
             score.scored_at.isoformat(), score.model_dump_json()),
        )
        c = self.get(score.candidate_id)
        if c is not None:
            # A total with confidence `none` is a number with no support behind
            # it. The score record keeps it, with its components and
            # abstentions, because that detail is the useful part. The
            # candidate's summary field stays empty, so that "unscored" and
            # "scored zero" do not look alike in a list.
            supported = score.confidence is not Confidence.none
            self._write_candidate(
                c.model_copy(update={
                    "relevance_score": score.total if supported else None,
                    "confidence": score.confidence,
                    "updated_at": utcnow(),
                }),
                insert=False,
            )
        self.db.commit()

    def get_score(self, candidate_id: str) -> Optional[CandidateScore]:
        row = self.db.query_one(
            "SELECT payload FROM scores WHERE candidate_id = ?", (candidate_id,)
        )
        return CandidateScore.model_validate_json(row[0]) if row else None

    def save_propensity(self, assessment: PropensityAssessment) -> None:
        self.db.execute(
            """
            INSERT INTO propensity (candidate_id, band, confidence, assessed_at, payload)
            VALUES (?,?,?,?,?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                band=excluded.band, confidence=excluded.confidence,
                assessed_at=excluded.assessed_at, payload=excluded.payload
            """,
            (assessment.candidate_id, assessment.band.value,
             assessment.confidence.value, assessment.assessed_at.isoformat(),
             assessment.model_dump_json()),
        )
        c = self.get(assessment.candidate_id)
        if c is not None:
            self._write_candidate(
                c.model_copy(update={"engagement_propensity": assessment.band,
                                     "updated_at": utcnow()}),
                insert=False,
            )
        self.db.commit()

    def get_propensity(self, candidate_id: str) -> Optional[PropensityAssessment]:
        row = self.db.query_one(
            "SELECT payload FROM propensity WHERE candidate_id = ?", (candidate_id,)
        )
        return PropensityAssessment.model_validate_json(row[0]) if row else None

    def save_recommendation(self, rec: ConnectionRecommendation) -> None:
        self.db.execute(
            """
            INSERT INTO recommendations (candidate_id, created_at, payload)
            VALUES (?,?,?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                created_at=excluded.created_at, payload=excluded.payload
            """,
            (rec.candidate_id, rec.created_at.isoformat(), rec.model_dump_json()),
        )
        self.db.commit()
        self.audit.record(
            action_class=ActionClass.draft_for_human,
            decision="allowed",
            summary=f"connection recommendation prepared for {rec.candidate_id}",
            subject_id=rec.candidate_id,
            skill=self.governor.skill,
        )

    def get_recommendation(self, candidate_id: str) -> Optional[ConnectionRecommendation]:
        row = self.db.query_one(
            "SELECT payload FROM recommendations WHERE candidate_id = ?", (candidate_id,)
        )
        return ConnectionRecommendation.model_validate_json(row[0]) if row else None

    def save_draft(self, draft: InvitationDraft) -> int:
        cur = self.db.execute(
            """
            INSERT INTO invitation_drafts
                (candidate_id, variant_label, approval_state, created_at, payload)
            VALUES (?,?,?,?,?)
            """,
            (draft.candidate_id, draft.variant_label, draft.approval_state,
             draft.created_at.isoformat(), draft.model_dump_json()),
        )
        self.db.commit()
        self.audit.record(
            action_class=ActionClass.draft_for_human,
            decision="allowed",
            summary=(f"invitation draft {draft.variant_label!r} prepared for "
                     f"{draft.candidate_id} — not sent"),
            subject_id=draft.candidate_id,
            skill=self.governor.skill,
        )
        return int(cur.lastrowid) if getattr(cur, "lastrowid", None) else -1

    def drafts(self, candidate_id: str) -> list[InvitationDraft]:
        rows = self.db.query(
            "SELECT payload FROM invitation_drafts WHERE candidate_id = ? "
            "ORDER BY draft_id ASC", (candidate_id,)
        )
        return [InvitationDraft.model_validate_json(r[0]) for r in rows]

    def save_opportunity(self, opp: BusinessOpportunity) -> None:
        self.db.execute(
            """
            INSERT INTO opportunities (opportunity_id, candidate_id, service_category,
                                       stage, confidence, confirmed, updated_at, payload)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(opportunity_id) DO UPDATE SET
                stage=excluded.stage, confidence=excluded.confidence,
                confirmed=excluded.confirmed, updated_at=excluded.updated_at,
                payload=excluded.payload
            """,
            (opp.opportunity_id, opp.candidate_id, opp.service_category,
             opp.stage.value, opp.confidence.value, 1 if opp.confirmed_by_user else 0,
             opp.updated_at.isoformat(), opp.model_dump_json()),
        )
        c = self.get(opp.candidate_id)
        if c is not None and opp.estimated_relevance is not None:
            self._write_candidate(
                c.model_copy(update={"business_opportunity_score": opp.estimated_relevance,
                                     "updated_at": utcnow()}),
                insert=False,
            )
        self.db.commit()

    def opportunities(self, *, candidate_id: Optional[str] = None,
                      stage: Optional[str] = None) -> list[BusinessOpportunity]:
        sql = ["SELECT payload FROM opportunities WHERE 1=1"]
        params: list[object] = []
        if candidate_id:
            sql.append("AND candidate_id = ?")
            params.append(candidate_id)
        if stage:
            sql.append("AND stage = ?")
            params.append(stage)
        rows = self.db.query(" ".join(sql), params)
        return [BusinessOpportunity.model_validate_json(r[0]) for r in rows]

    # ------------------------------------------------------ subject rights ---
    def subject_export(self, candidate_id: str, *, approved_by_user: bool = False) -> dict:
        """Everything held about one person.

        Gated on approval: an export leaves the machine, and the governor
        treats that as an action needing the user's go-ahead.
        """
        self.governor.check(
            ActionClass.export_user_data, subject_id=candidate_id,
            approved_by_user=approved_by_user,
        ).raise_if_refused()
        if not approved_by_user:
            raise SafetyRefusal(
                "a subject export needs your explicit go-ahead first",
                rule_id="requires_human_approval",
                action_class=ActionClass.export_user_data,
            )
        data = self.db.subject_rows(candidate_id)
        self.audit.record(
            action_class=ActionClass.export_user_data, decision="approved",
            summary=f"subject export produced for {candidate_id}",
            subject_id=candidate_id, actor="user", skill=self.governor.skill,
        )
        return {"candidate_id": candidate_id, "exported_at": utcnow().isoformat(),
                "tables": data}

    def forget(self, candidate_id: str, *, approved_by_user: bool = False) -> dict[str, int]:
        """Delete every record about one person.

        The audit line recording the deletion stays, by design: it holds no
        profile fields and it is the only proof the deletion happened.
        """
        self.governor.check(
            ActionClass.delete_user_data, subject_id=candidate_id,
            approved_by_user=approved_by_user,
        ).raise_if_refused()
        if not approved_by_user:
            raise SafetyRefusal(
                "deleting records needs your explicit go-ahead first",
                rule_id="requires_human_approval",
                action_class=ActionClass.delete_user_data,
            )
        counts = self.db.delete_subject(candidate_id)
        self.audit.record(
            action_class=ActionClass.delete_user_data, decision="approved",
            summary=(f"deleted all records for {candidate_id}: "
                     f"{ {k: v for k, v in counts.items() if v} }"),
            subject_id=candidate_id, actor="user", skill=self.governor.skill,
        )
        return counts

    def untouched_since(self, days: Optional[int] = None) -> list[Candidate]:
        """Records nobody has touched in a while, surfaced for review.

        Not deleted automatically: silently removing someone's own data is its
        own kind of surprise.
        """
        d = (days if days is not None
             else self.settings.safety.data_protection.review_untouched_after_days)
        cutoff = (utcnow() - timedelta(days=d)).isoformat()
        rows = self.db.query(
            "SELECT payload FROM candidates WHERE updated_at < ?", (cutoff,)
        )
        return [Candidate.model_validate_json(r[0]) for r in rows]
