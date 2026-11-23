"""The audit trail. Append-only, by construction.

Phase 2 asks the safety governor to "maintain an audit trail of recommendations
and approvals". This module is that trail. It offers `append`, `read` and
`prune_expired`, and no way to alter a line that has been written. `prune_expired`
exists because the retention period in `safety.yaml` has to be enforceable; it
deletes whole lines past their retention date and cannot rewrite one.

Everything written here is about what the *agent and the user* did. It holds no
profile fields, which is why `Database.delete_subject` leaves it alone: a
deletion request removes the person's data and keeps the record that the
deletion happened.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Literal, Optional

from .config import Settings
from .db import Database
from .models import ActionClass, AuditEntry, utcnow

__all__ = ["AuditLog"]


class AuditLog:
    def __init__(self, db: Database, settings: Settings):
        self._db = db
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return self._settings.safety.audit.enabled

    # ------------------------------------------------------------ write ---
    def append(self, entry: AuditEntry) -> int:
        """Write one line. Returns its id.

        Raises nothing when auditing is disabled, because it cannot be: the
        config layer refuses a configuration that turns it off.
        """
        a = self._settings.safety.audit
        if entry.decision == "refused" and not a.log_refusals:  # pragma: no cover
            raise RuntimeError("refusal logging cannot be disabled")
        if entry.decision in ("approved", "declined") and not a.log_approvals:
            return -1
        cur = self._db.execute(
            """
            INSERT INTO audit_log
                (occurred_at, actor, action_class, decision, skill, subject_id,
                 rule_cited, summary, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.occurred_at.isoformat(),
                entry.actor,
                entry.action_class.value,
                entry.decision,
                entry.skill,
                entry.subject_id,
                entry.rule_cited,
                entry.summary,
                entry.model_dump_json(),
            ),
        )
        self._db.commit()
        return int(cur.lastrowid) if getattr(cur, "lastrowid", None) else -1

    def record(
        self,
        *,
        action_class: ActionClass,
        decision: Literal["allowed", "refused", "requires_approval", "approved", "declined"],
        summary: str,
        actor: Literal["agent", "user", "system"] = "agent",
        skill: Optional[str] = None,
        subject_id: Optional[str] = None,
        rule_cited: Optional[str] = None,
    ) -> int:
        """Convenience wrapper around `append`."""
        return self.append(
            AuditEntry(
                actor=actor,
                action_class=action_class,
                decision=decision,
                skill=skill,
                subject_id=subject_id,
                summary=summary,
                rule_cited=rule_cited,
            )
        )

    # ------------------------------------------------------------- read ---
    def read(
        self,
        *,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        decision: Optional[str] = None,
        subject_id: Optional[str] = None,
        limit: int = 500,
    ) -> list[AuditEntry]:
        sql = ["SELECT payload FROM audit_log WHERE 1=1"]
        params: list[object] = []
        if since:
            sql.append("AND occurred_at >= ?")
            params.append(since.isoformat())
        if until:
            sql.append("AND occurred_at <= ?")
            params.append(until.isoformat())
        if decision:
            sql.append("AND decision = ?")
            params.append(decision)
        if subject_id:
            sql.append("AND subject_id = ?")
            params.append(subject_id)
        sql.append("ORDER BY occurred_at DESC, entry_id DESC LIMIT ?")
        params.append(int(limit))
        rows = self._db.query(" ".join(sql), params)
        return [AuditEntry.model_validate_json(r[0]) for r in rows]

    def refusals(self, limit: int = 100) -> list[AuditEntry]:
        return self.read(decision="refused", limit=limit)

    def count(self) -> int:
        row = self._db.query_one("SELECT COUNT(*) FROM audit_log")
        return int(row[0]) if row else 0

    # -------------------------------------------------------- retention ---
    def prune_expired(self, *, today: Optional[date] = None) -> int:
        """Delete lines past the configured retention. Returns the count removed."""
        days = self._settings.safety.audit.retain_days
        cutoff = datetime.combine(today or date.today(), datetime.min.time(),
                                  tzinfo=timezone.utc) - timedelta(days=days)
        cur = self._db.execute(
            "DELETE FROM audit_log WHERE occurred_at < ?", (cutoff.isoformat(),)
        )
        self._db.commit()
        return cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0

    # --------------------------------------------------------- reporting ---
    def summarise(self, entries: Optional[Iterable[AuditEntry]] = None) -> dict:
        items = list(entries) if entries is not None else self.read(limit=10_000)
        by_decision: dict[str, int] = {}
        by_rule: dict[str, int] = {}
        for e in items:
            by_decision[e.decision] = by_decision.get(e.decision, 0) + 1
            if e.rule_cited:
                by_rule[e.rule_cited] = by_rule.get(e.rule_cited, 0) + 1
        return {
            "lines": len(items),
            "by_decision": dict(sorted(by_decision.items())),
            "refusals_by_rule": dict(sorted(by_rule.items(), key=lambda kv: -kv[1])),
        }
