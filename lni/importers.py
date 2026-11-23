"""Reading what the user supplies: CSVs, LinkedIn data exports, analytics exports.

Everything this bundle knows comes through here or through a skill writing a
record directly. There is no fetcher, no scraper and no browser driver, so this
module is the whole input surface — which makes it the right place for the
privacy filter and the provenance stamp.

Column names vary between LinkedIn's own exports and whatever a user built in a
spreadsheet, so headers are matched by alias rather than by exact string. A
column that matches nothing is reported, not guessed at.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence

from .config import Settings
from .models import (
    Candidate, ContentAnalytics, Evidence, Seniority, SourceKind,
    SourceProvenance, normalise_profile_url,
)
from . import provenance as prov

__all__ = ["ImportReport", "import_candidates_csv", "import_connections_export",
           "import_post_analytics", "sniff_columns", "COLUMN_ALIASES"]


#: Header aliases, lowercased and stripped of punctuation. Covers LinkedIn's
#: own export headers and the shapes people build by hand.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "full name", "fullname", "contact", "person"),
    "first_name": ("first name", "firstname", "given name"),
    "last_name": ("last name", "lastname", "surname", "family name"),
    "profile_url": ("profile url", "url", "linkedin", "linkedin url",
                    "linkedin profile", "profile", "public profile url"),
    "professional_title": ("title", "position", "job title", "headline", "role"),
    "company": ("company", "organisation", "organization", "employer",
                "current company", "company name"),
    "industry": ("industry", "sector", "vertical"),
    "geography": ("location", "geography", "country", "region", "city", "based in"),
    "seniority": ("seniority", "level", "grade"),
    "company_size_band": ("company size", "headcount", "size", "employees"),
    "notes": ("notes", "note", "comment", "context"),
    "tags": ("tags", "labels", "topics", "interests"),
    "connected_on": ("connected on", "connection date", "date connected"),
    # Analytics exports.
    "post_ref": ("post url", "post link", "permalink", "post", "post id", "url"),
    "published_on": ("date", "created date", "publish date", "published",
                     "post publish date"),
    "impressions": ("impressions", "views", "post views"),
    "members_reached": ("members reached", "unique views", "reach"),
    "reactions": ("reactions", "likes", "total reactions"),
    "comments": ("comments", "total comments"),
    "shares": ("shares", "reposts", "total shares"),
    "followers_gained": ("followers gained", "new followers", "follows"),
    "topics": ("topics", "topic", "theme", "pillar", "tags"),
    "format": ("format", "post type", "type"),
}

_SENIORITY_HINTS: tuple[tuple[tuple[str, ...], Seniority], ...] = (
    (("founder", "co-founder", "owner", "proprietor"), Seniority.founder_owner),
    (("chief", "ceo", "cto", "cfo", "coo", "cmo", "c-level"), Seniority.c_level),
    (("vp", "vice president", "svp", "evp"), Seniority.vp),
    (("director", "head of"), Seniority.director),
    (("manager", "lead manager"), Seniority.manager),
    (("lead", "principal", "staff"), Seniority.lead),
    (("senior",), Seniority.senior_ic),
    (("board", "investor", "partner at", "venture"), Seniority.board_investor),
    (("student", "intern", "graduate", "trainee"), Seniority.student_early_career),
)


@dataclass
class ImportReport:
    """What an import actually did. Returned instead of printed."""

    source_path: str
    rows_read: int = 0
    candidates: list[Candidate] = field(default_factory=list)
    posts: list[ContentAnalytics] = field(default_factory=list)
    skipped: list[tuple[int, str]] = field(default_factory=list)
    warnings: list[tuple[int, str]] = field(default_factory=list)
    unmapped_columns: list[str] = field(default_factory=list)
    dropped_fields: list[str] = field(default_factory=list)
    missing_fields_by_row: dict[int, list[str]] = field(default_factory=dict)

    def summary(self) -> str:
        bits = [f"{self.rows_read} row(s) read from {self.source_path}"]
        if self.candidates:
            bits.append(f"{len(self.candidates)} candidate(s) parsed")
        if self.posts:
            bits.append(f"{len(self.posts)} post(s) parsed")
        if self.skipped:
            bits.append(f"{len(self.skipped)} row(s) skipped")
        if self.warnings:
            bits.append(f"{len(self.warnings)} row(s) with a warning")
        if self.unmapped_columns:
            bits.append(f"columns ignored: {', '.join(self.unmapped_columns)}")
        if self.dropped_fields:
            bits.append(
                f"fields dropped by the privacy filter: "
                f"{', '.join(sorted(set(self.dropped_fields)))}"
            )
        return "; ".join(bits)


def _clean_header(h: str) -> str:
    return " ".join(
        "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in (h or "").lower()).split()
    )


def sniff_columns(headers: Sequence[str]) -> tuple[dict[str, str], list[str]]:
    """Map file headers onto model fields. Returns (mapping, unmapped headers)."""
    mapping: dict[str, str] = {}
    used: set[str] = set()
    cleaned = {h: _clean_header(h) for h in headers}
    for field_name, aliases in COLUMN_ALIASES.items():
        for header, clean in cleaned.items():
            if header in used:
                continue
            if clean in aliases:
                mapping[field_name] = header
                used.add(header)
                break
    unmapped = [h for h in headers if h not in used and (h or "").strip()]
    return mapping, unmapped


def _value(row: dict, mapping: dict[str, str], field_name: str) -> Optional[str]:
    header = mapping.get(field_name)
    if not header:
        return None
    v = (row.get(header) or "").strip()
    return v or None


def _parse_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d %b %Y", "%d %B %Y",
                "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d", "%b %d, %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_int(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    cleaned = raw.replace(",", "").replace(" ", "").strip()
    if not cleaned:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _infer_seniority(title: Optional[str], declared: Optional[str]) -> Seniority:
    if declared:
        try:
            return Seniority(declared.strip().lower().replace(" ", "_"))
        except ValueError:
            pass
    if not title:
        return Seniority.unknown
    low = title.lower()
    for hints, level in _SENIORITY_HINTS:
        if any(h in low for h in hints):
            return level
    return Seniority.unknown


def _open_rows(path: Path | str, *, text: Optional[str] = None
               ) -> tuple[list[dict], list[str]]:
    if text is not None:
        handle: Iterable[str] = io.StringIO(text)
    else:
        handle = Path(path).open("r", encoding="utf-8-sig", newline="")
    with handle if hasattr(handle, "__exit__") else io.StringIO(text or "") as fh:  # type: ignore[arg-type]
        reader = csv.DictReader(fh)
        rows = [dict(r) for r in reader]
        headers = list(reader.fieldnames or [])
    return rows, headers


def _skip_linkedin_preamble(path: Path) -> Optional[str]:
    """LinkedIn's Connections.csv ships three notes lines before the header.

    Returns the file text starting at the header row, or None when the file
    already starts with a header.
    """
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = raw.splitlines()
    for i, line in enumerate(lines[:10]):
        clean = _clean_header(line.split(",")[0] if line else "")
        if clean in ("first name", "name", "firstname"):
            return "\n".join(lines[i:]) if i else None
    return None


def import_candidates_csv(
    path: Path | str,
    settings: Settings,
    *,
    source: Optional[SourceProvenance] = None,
    default_icp: Optional[str] = None,
    text: Optional[str] = None,
) -> ImportReport:
    """Read a candidate CSV the user built or exported themselves.

    Rows with neither a profile URL nor a name are skipped rather than
    invented. Fields the privacy filter forbids are dropped before anything is
    constructed, and recorded in the report so the user can see what was left
    out.
    """
    p = Path(path)
    rows, headers = _open_rows(p, text=text)
    report = ImportReport(source_path=str(p))
    mapping, unmapped = sniff_columns(headers)
    report.unmapped_columns = unmapped
    report.rows_read = len(rows)

    never = {f.lower() for f in settings.privacy.never_store}
    allowed = set(settings.privacy.allowed_candidate_fields)
    for header in headers:
        clean = _clean_header(header).replace(" ", "_")
        if clean in never:
            report.dropped_fields.append(header)

    base_source = source or prov.user_csv(str(p))

    for i, row in enumerate(rows, start=2):  # row 1 is the header
        name = _value(row, mapping, "name")
        if not name:
            first = _value(row, mapping, "first_name") or ""
            last = _value(row, mapping, "last_name") or ""
            name = f"{first} {last}".strip() or None
        url = _value(row, mapping, "profile_url")
        if url:
            try:
                url = normalise_profile_url(url)
            except ValueError:
                # Not a skip: the row still has a person in it. The record
                # is kept with no URL, identity falls back to name+company,
                # and the user is told which row needs the URL corrected.
                report.warnings.append(
                    (i, f"unreadable profile URL {url!r}; record kept without one, "
                        f"identity falls back to name and company")
                )
                url = None
        if not name and not url:
            report.skipped.append((i, "no name and no profile URL"))
            continue
        if not name:
            # A URL with no name is still a record; the slug is not a name, so
            # the gap is recorded rather than filled from the URL.
            name = "(name not supplied)"

        title = _value(row, mapping, "professional_title")
        tags_raw = _value(row, mapping, "tags") or ""
        tags = [t.strip() for t in tags_raw.replace("|", ",").split(",") if t.strip()]

        row_source = base_source.model_copy(
            update={"detail": f"{base_source.detail} (row {i})"}
        )
        missing = [f for f in ("professional_title", "company", "industry", "geography")
                   if not _value(row, mapping, f)]
        try:
            c = Candidate.create(
                name=name,
                profile_url=url,
                company=_value(row, mapping, "company"),
                sources=[row_source],
                professional_title=title,
                industry=_value(row, mapping, "industry"),
                geography=_value(row, mapping, "geography"),
                seniority=_infer_seniority(title, _value(row, mapping, "seniority")),
                company_size_band=_value(row, mapping, "company_size_band"),
                primary_icp_key=default_icp,
                tags=tags if "tags" in allowed else [],
                notes=_value(row, mapping, "notes") if "notes" in allowed else None,
                missing_fields=missing,
                last_verified=date.today(),
            )
        except Exception as exc:
            report.skipped.append((i, f"row does not validate: {exc}"))
            continue
        report.candidates.append(c)
        if missing:
            report.missing_fields_by_row[i] = missing
    return report


def import_connections_export(
    path: Path | str,
    settings: Settings,
    *,
    default_icp: Optional[str] = None,
) -> ImportReport:
    """Read the user's own LinkedIn `Connections.csv` from a data export.

    This is the user's own data, downloaded by them from their own account. It
    is not a scrape, and it is the only bulk source of existing connections
    this bundle accepts.
    """
    p = Path(path)
    text = _skip_linkedin_preamble(p)
    report = import_candidates_csv(
        p, settings, source=prov.data_export(str(p)), default_icp=default_icp,
        text=text,
    )
    # Connection date is a fact about the relationship, not the person.
    return report


def import_post_analytics(
    path: Path | str,
    settings: Settings,
    *,
    topic_map: Optional[dict[str, Sequence[str]]] = None,
    covers: Optional[str] = None,
    text: Optional[str] = None,
) -> ImportReport:
    """Read the user's own post analytics export.

    `topic_map` lets the user label posts by topic, keyed on any substring of
    the post reference. Without it, posts carry no topics and the affinity
    matrix correctly reports that it cannot group them.
    """
    p = Path(path)
    rows, headers = _open_rows(p, text=text)
    report = ImportReport(source_path=str(p))
    mapping, unmapped = sniff_columns(headers)
    report.unmapped_columns = unmapped
    report.rows_read = len(rows)
    source = prov.analytics_export(str(p), covers=covers)

    for i, row in enumerate(rows, start=2):
        ref = _value(row, mapping, "post_ref")
        if not ref:
            report.skipped.append((i, "no post reference"))
            continue
        topics: list[str] = []
        raw_topics = _value(row, mapping, "topics")
        if raw_topics:
            topics = [t.strip() for t in raw_topics.replace("|", ",").split(",") if t.strip()]
        if topic_map:
            for needle, mapped in topic_map.items():
                if needle.lower() in ref.lower():
                    topics.extend(mapped)
        try:
            post = ContentAnalytics(
                post_ref=ref,
                published_on=_parse_date(_value(row, mapping, "published_on")),
                topics=list(dict.fromkeys(topics)),
                format=_value(row, mapping, "format"),
                impressions=_parse_int(_value(row, mapping, "impressions")),
                members_reached=_parse_int(_value(row, mapping, "members_reached")),
                reactions=_parse_int(_value(row, mapping, "reactions")),
                comments=_parse_int(_value(row, mapping, "comments")),
                shares=_parse_int(_value(row, mapping, "shares")),
                followers_gained=_parse_int(_value(row, mapping, "followers_gained")),
                source=source,
            )
        except Exception as exc:
            report.skipped.append((i, f"row does not validate: {exc}"))
            continue
        report.posts.append(post)
    return report
