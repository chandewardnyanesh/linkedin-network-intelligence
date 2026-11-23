"""Storage. SQLite by default, PostgreSQL behind the same interface.

Design note, because it is a deliberate choice rather than a shortcut: each
table carries **indexed scalar columns for the things we filter and sort on,
plus a `payload` column holding the full validated model as JSON.** Pydantic
stays the single definition of every record's shape, so a schema change is a
model change and cannot drift from what the code validates. The scalar columns
exist because `WHERE crm_status = ? AND relevance_score > ?` has to be a query,
not a full-table rehydrate.

What this store deliberately does not have: an `UPDATE` or `DELETE` on
`audit_log`. The audit trail is append-only, and `lni.audit` exposes no method
that would change a written line.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Literal, Optional, Sequence

from .config import Settings

__all__ = ["Database", "open_database", "SCHEMA_VERSION", "DatabaseError"]

SCHEMA_VERSION = 1


class DatabaseError(RuntimeError):
    pass


#: `?` placeholders throughout; translated for PostgreSQL's `%s` on the way out.
_SCHEMA: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS candidates (
        candidate_id   TEXT PRIMARY KEY,
        profile_url    TEXT,
        name           TEXT NOT NULL,
        company        TEXT,
        industry       TEXT,
        geography      TEXT,
        seniority      TEXT,
        primary_icp    TEXT,
        crm_status     TEXT NOT NULL,
        relevance      REAL,
        propensity     TEXT,
        opportunity    REAL,
        confidence     TEXT NOT NULL,
        last_verified  TEXT,
        created_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL,
        payload        TEXT NOT NULL
    )
    """,
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_cand_url ON candidates(profile_url)",
    "CREATE INDEX IF NOT EXISTS idx_cand_status ON candidates(crm_status)",
    "CREATE INDEX IF NOT EXISTS idx_cand_icp ON candidates(primary_icp)",
    "CREATE INDEX IF NOT EXISTS idx_cand_rel ON candidates(relevance)",
    "CREATE INDEX IF NOT EXISTS idx_cand_name_company ON candidates(name, company)",
    """
    CREATE TABLE IF NOT EXISTS scores (
        candidate_id    TEXT PRIMARY KEY,
        total           REAL NOT NULL,
        priority        TEXT NOT NULL,
        confidence      TEXT NOT NULL,
        weights_profile TEXT NOT NULL,
        abstentions     INTEGER NOT NULL,
        scored_at       TEXT NOT NULL,
        payload         TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_score_priority ON scores(priority)",
    "CREATE INDEX IF NOT EXISTS idx_score_total ON scores(total)",
    """
    CREATE TABLE IF NOT EXISTS propensity (
        candidate_id TEXT PRIMARY KEY,
        band         TEXT NOT NULL,
        confidence   TEXT NOT NULL,
        assessed_at  TEXT NOT NULL,
        payload      TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS recommendations (
        candidate_id TEXT PRIMARY KEY,
        created_at   TEXT NOT NULL,
        payload      TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS invitation_drafts (
        draft_id       INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id   TEXT NOT NULL,
        variant_label  TEXT NOT NULL,
        approval_state TEXT NOT NULL,
        created_at     TEXT NOT NULL,
        payload        TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_draft_cand ON invitation_drafts(candidate_id)",
    """
    CREATE TABLE IF NOT EXISTS status_changes (
        change_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id TEXT NOT NULL,
        from_status  TEXT,
        to_status    TEXT NOT NULL,
        confirmed    INTEGER NOT NULL,
        changed_at   TEXT NOT NULL,
        payload      TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_status_cand ON status_changes(candidate_id)",
    "CREATE INDEX IF NOT EXISTS idx_status_at ON status_changes(changed_at)",
    """
    CREATE TABLE IF NOT EXISTS relationship_events (
        event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id TEXT NOT NULL,
        occurred_on  TEXT NOT NULL,
        channel      TEXT NOT NULL,
        direction    TEXT NOT NULL,
        substantive  INTEGER NOT NULL,
        payload      TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_event_cand ON relationship_events(candidate_id)",
    "CREATE INDEX IF NOT EXISTS idx_event_date ON relationship_events(occurred_on)",
    """
    CREATE TABLE IF NOT EXISTS opportunities (
        opportunity_id   TEXT PRIMARY KEY,
        candidate_id     TEXT NOT NULL,
        service_category TEXT NOT NULL,
        stage            TEXT NOT NULL,
        confidence       TEXT NOT NULL,
        confirmed        INTEGER NOT NULL,
        updated_at       TEXT NOT NULL,
        payload          TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_opp_cand ON opportunities(candidate_id)",
    "CREATE INDEX IF NOT EXISTS idx_opp_stage ON opportunities(stage)",
    """
    CREATE TABLE IF NOT EXISTS content_analytics (
        post_ref     TEXT PRIMARY KEY,
        published_on TEXT,
        impressions  INTEGER,
        reactions    INTEGER,
        comments     INTEGER,
        shares       INTEGER,
        payload      TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_content_date ON content_analytics(published_on)",
    """
    CREATE TABLE IF NOT EXISTS audience_segments (
        segment_key TEXT PRIMARY KEY,
        label       TEXT NOT NULL,
        quality     TEXT NOT NULL,
        payload     TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS topic_affinity (
        topic       TEXT NOT NULL,
        segment_key TEXT,
        payload     TEXT NOT NULL,
        PRIMARY KEY (topic, segment_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reports (
        report_id    TEXT PRIMARY KEY,
        period       TEXT NOT NULL,
        period_start TEXT NOT NULL,
        period_end   TEXT NOT NULL,
        generated_at TEXT NOT NULL,
        payload      TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_log (
        entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
        occurred_at  TEXT NOT NULL,
        actor        TEXT NOT NULL,
        action_class TEXT NOT NULL,
        decision     TEXT NOT NULL,
        skill        TEXT,
        subject_id   TEXT,
        rule_cited   TEXT,
        summary      TEXT NOT NULL,
        payload      TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_audit_at ON audit_log(occurred_at)",
    "CREATE INDEX IF NOT EXISTS idx_audit_decision ON audit_log(decision)",
    "CREATE INDEX IF NOT EXISTS idx_audit_subject ON audit_log(subject_id)",
)

#: Tables holding data about a person, for subject export and deletion. Order
#: matters for deletion: children before the candidate row.
SUBJECT_TABLES: tuple[tuple[str, str], ...] = (
    ("relationship_events", "candidate_id"),
    ("status_changes", "candidate_id"),
    ("invitation_drafts", "candidate_id"),
    ("recommendations", "candidate_id"),
    ("propensity", "candidate_id"),
    ("scores", "candidate_id"),
    ("opportunities", "candidate_id"),
    ("candidates", "candidate_id"),
)


class Database:
    """A thin connection wrapper with one paramstyle and explicit transactions."""

    def __init__(self, conn: Any, backend: Literal["sqlite", "postgres"]):
        self._conn = conn
        self.backend = backend

    # ---------------------------------------------------------- helpers ---
    def _sql(self, sql: str) -> str:
        if self.backend == "postgres":
            sql = sql.replace("?", "%s")
            sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        return sql

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        cur = self._conn.cursor()
        cur.execute(self._sql(sql), tuple(params))
        return cur

    def executemany(self, sql: str, rows: Sequence[Sequence[Any]]) -> None:
        cur = self._conn.cursor()
        cur.executemany(self._sql(sql), [tuple(r) for r in rows])

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[tuple]:
        return list(self.execute(sql, params).fetchall())

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> Optional[tuple]:
        rows = self.execute(sql, params).fetchmany(1)
        return rows[0] if rows else None

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator["Database"]:
        try:
            yield self
            self.commit()
        except Exception:
            self.rollback()
            raise

    # ----------------------------------------------------------- schema ---
    def migrate(self) -> int:
        """Create or upgrade the schema. Returns the version now in place."""
        for stmt in _SCHEMA:
            self.execute(stmt)
        row = self.query_one("SELECT value FROM meta WHERE key = ?", ("schema_version",))
        if row is None:
            self.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?)",
                ("schema_version", str(SCHEMA_VERSION)),
            )
            current = SCHEMA_VERSION
        else:
            current = int(row[0])
            if current > SCHEMA_VERSION:
                raise DatabaseError(
                    f"the store is at schema version {current}; this build "
                    f"understands {SCHEMA_VERSION}. Upgrade the package rather "
                    f"than letting an older build write to a newer store."
                )
            if current < SCHEMA_VERSION:
                # Forward migrations go here as the schema grows. Version 1 is
                # the first, so there is nothing to replay yet.
                self.execute(
                    "UPDATE meta SET value = ? WHERE key = ?",
                    (str(SCHEMA_VERSION), "schema_version"),
                )
                current = SCHEMA_VERSION
        self.commit()
        return current

    @property
    def schema_version(self) -> int:
        row = self.query_one("SELECT value FROM meta WHERE key = ?", ("schema_version",))
        return int(row[0]) if row else 0

    # ------------------------------------------------- subject rights ---
    def subject_rows(self, candidate_id: str) -> dict[str, list[dict]]:
        """Everything the store holds about one person, for a subject export."""
        out: dict[str, list[dict]] = {}
        for table, col in SUBJECT_TABLES:
            rows = self.query(
                f"SELECT payload FROM {table} WHERE {col} = ?", (candidate_id,)
            )
            if rows:
                out[table] = [json.loads(r[0]) for r in rows]
        return out

    def delete_subject(self, candidate_id: str) -> dict[str, int]:
        """Remove every record about one person. Returns rows deleted per table.

        The audit trail is not touched: it records that a deletion happened,
        which is the point of having one, and it holds no profile fields.
        """
        counts: dict[str, int] = {}
        with self.transaction():
            for table, col in SUBJECT_TABLES:
                cur = self.execute(f"DELETE FROM {table} WHERE {col} = ?", (candidate_id,))
                counts[table] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        return counts


def open_database(settings: Settings, *, path_override: Optional[str] = None) -> Database:
    """Open and migrate the configured store."""
    if settings.storage.backend == "postgres":
        dsn = settings.storage.postgres_dsn
        if not dsn:
            raise DatabaseError(
                f"postgres backend selected but ${settings.storage.postgres_dsn_env} "
                f"is empty"
            )
        try:
            import psycopg  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise DatabaseError(
                "the postgres backend needs `psycopg`: pip install "
                "'psycopg[binary]>=3.1'. The sqlite backend needs nothing."
            ) from exc
        db = Database(psycopg.connect(dsn), "postgres")
    else:
        raw = path_override or settings.storage.sqlite_path
        if raw == ":memory:":
            conn = sqlite3.connect(":memory:")
        else:
            p = Path(raw)
            if not p.is_absolute():
                p = Path.cwd() / p
            p.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(p)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        db = Database(conn, "sqlite")
    db.migrate()
    return db
