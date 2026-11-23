#!/usr/bin/env python3
"""Command line entry point: `python -m lni <command>`.

The skills call these commands rather than reimplementing logic in prose, so
that a rule exists in exactly one place. Every command that writes, exports or
deletes needs `--approve`, which stands in for the user's go-ahead when a
skill is driving the CLI on their behalf.

    python -m lni config-check
    python -m lni init
    python -m lni safety-check "automate the invites"
    python -m lni import-candidates people.csv --icp business_development
    python -m lni import-analytics posts.csv
    python -m lni score --all
    python -m lni shortlist
    python -m lni status <candidate_id> shortlisted
    python -m lni report --period weekly
    python -m lni audit --limit 20
    python -m lni export --approve -o out.csv
    python -m lni forget <candidate_id> --approve
    python -m lni missing <skill-name>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

from .audit import AuditLog
from .config import ConfigError, SKILL_REQUIREMENTS, load_config, missing_for
from .crm import CRMError, NetworkCRM
from .db import open_database
from .models import ActionClass, CRMStatus, PriorityClass
from pydantic import ValidationError

from .safety import SafetyGovernor, SafetyRefusal


def _bootstrap(args) -> tuple:
    settings = load_config(config_dir=args.config_dir,
                           extra_files=args.extra_config or None)
    db = open_database(settings, path_override=args.db)
    audit = AuditLog(db, settings)
    gov = SafetyGovernor(settings, audit, skill=args.skill)
    crm = NetworkCRM(db, settings, audit, gov)
    return settings, db, audit, gov, crm


# ------------------------------------------------------------- commands ---


def cmd_config_check(args) -> int:
    try:
        settings = load_config(config_dir=args.config_dir,
                               extra_files=args.extra_config or None)
    except ConfigError as exc:
        print(f"Configuration problem:\n{exc}", file=sys.stderr)
        return 1
    print(f"Configuration loads. Layers: {len(settings.loaded_from)}")
    for p in settings.loaded_from:
        print(f"  {p}")
    print(f"\nScoring profile: {settings.scoring.active_profile}")
    for comp, w in settings.scoring.active_weights.items():
        print(f"  {comp:24s} {w:5.1f}")
    print(f"\nActive ICPs: {len(settings.active_icps)}")
    for icp in settings.active_icps:
        flag = "falsifiable" if icp.is_falsifiable else "NO exclusions or signals yet"
        print(f"  {icp.key:28s} priority {icp.priority}  [{flag}]")
    print(f"\nService categories usable: {len(settings.usable_service_categories)}")
    print(f"Safety rules loaded: {len(settings.safety.prohibited)}")
    print(f"Storage: {settings.storage.backend}")
    gaps = {s: missing_for(settings, s) for s in SKILL_REQUIREMENTS}
    blocked = {k: v for k, v in gaps.items() if v}
    if blocked:
        print("\nSkills that will ask you for something first:")
        for skill, items in blocked.items():
            print(f"  {skill}")
            for path, _q in items:
                print(f"      needs {path}")
    else:
        print("\nEvery skill has what it needs.")
    return 0


def cmd_missing(args) -> int:
    settings = load_config(config_dir=args.config_dir,
                           extra_files=args.extra_config or None)
    try:
        items = missing_for(settings, args.skill_name)
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return 2
    if not items:
        print(f"{args.skill_name}: ready")
        return 0
    print(f"{args.skill_name} needs {len(items)} thing(s). Ask, do not assume:\n")
    for path, question in items:
        print(f"- {path}\n    {question}\n")
    return 0


def cmd_init(args) -> int:
    settings, db, *_ = _bootstrap(args)
    print(f"Store ready at schema version {db.schema_version} "
          f"({settings.storage.backend}).")
    return 0


def cmd_safety_check(args) -> int:
    settings, _db, _audit, gov, _crm = _bootstrap(args)
    decision = gov.guard(" ".join(args.text))
    print(f"outcome: {decision.outcome}")
    if decision.rule_id:
        print(f"rule: {decision.rule_id}")
    if decision.message:
        print()
        print(decision.message)
    return 0 if decision.allowed else 3


def cmd_import_candidates(args) -> int:
    settings, _db, _audit, gov, crm = _bootstrap(args)
    from .importers import import_candidates_csv

    report = import_candidates_csv(args.path, settings, default_icp=args.icp)
    print(report.summary())
    created = updated = unchanged = 0
    dupes = []
    for c in report.candidates:
        res = crm.upsert(c)
        created += res.action == "created"
        updated += res.action == "updated"
        unchanged += res.action == "unchanged"
        dupes.extend(res.possible_duplicates)
    print(f"created {created}, updated {updated}, unchanged {unchanged}")
    for w in report.warnings:
        print(f"  warning row {w[0]}: {w[1]}")
    for s in report.skipped:
        print(f"  skipped row {s[0]}: {s[1]}")
    near = [d for d in dupes if not d.auto_mergeable]
    if near:
        print(f"\n{len(near)} possible duplicate(s) for you to resolve — not merged:")
        for d in near[:20]:
            print(f"  {d.left_id} ~ {d.right_id} [{d.kind} {d.score}] {d.reason}")
    return 0


def cmd_import_connections(args) -> int:
    settings, _db, _audit, _gov, crm = _bootstrap(args)
    from .importers import import_connections_export

    report = import_connections_export(args.path, settings, default_icp=args.icp)
    print(report.summary())
    for c in report.candidates:
        crm.upsert(c)
    print(f"{len(report.candidates)} record(s) written")
    return 0


def cmd_import_analytics(args) -> int:
    settings, db, *_ = _bootstrap(args)
    from .importers import import_post_analytics

    report = import_post_analytics(args.path, settings)
    print(report.summary())
    for post in report.posts:
        db.execute(
            """
            INSERT INTO content_analytics
                (post_ref, published_on, impressions, reactions, comments, shares, payload)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(post_ref) DO UPDATE SET
                published_on=excluded.published_on, impressions=excluded.impressions,
                reactions=excluded.reactions, comments=excluded.comments,
                shares=excluded.shares, payload=excluded.payload
            """,
            (post.post_ref,
             post.published_on.isoformat() if post.published_on else None,
             post.impressions, post.reactions, post.comments, post.shares,
             post.model_dump_json()),
        )
    db.commit()
    print(f"{len(report.posts)} post(s) stored")
    return 0


def cmd_score(args) -> int:
    settings, _db, _audit, _gov, crm = _bootstrap(args)
    from .scoring import ScoringInput, rank, score_candidate

    targets = (crm.all_candidates() if args.all
               else [c for c in (crm.get(cid) for cid in args.ids) if c])
    if not targets:
        print("nothing to score", file=sys.stderr)
        return 1
    scores = []
    for c in targets:
        inp = ScoringInput(candidate=c, icps=settings.active_icps)
        score, propensity = score_candidate(inp, settings)
        crm.save_score(score)
        crm.save_propensity(propensity)
        scores.append((c, score))
    print(f"{len(scores)} candidate(s) scored with profile "
          f"{settings.scoring.active_profile!r}\n")
    for c, s in sorted(scores, key=lambda x: -x[1].total):
        ab = f" [{len(s.abstentions)} abstained]" if s.abstentions else ""
        print(f"  {s.total:6.2f}  {s.priority.value:11s} {s.confidence.value:7s} "
              f"{c.name}{ab}")
    print("\nNote: components with no inputs abstain and score zero. A low total "
          "on many abstentions describes the record, not the person.")
    return 0


def cmd_shortlist(args) -> int:
    settings, _db, _audit, _gov, crm = _bootstrap(args)
    size = args.size or settings.workflow.shortlist_size
    cap = settings.profile.weekly_invitation_capacity
    rows = crm.filter(status=[CRMStatus.qualified, CRMStatus.shortlisted],
                      order_by="relevance", limit=size)
    print(f"Shortlist ({len(rows)} of a possible {size}):\n")
    for c in rows:
        score = crm.get_score(c.candidate_id)
        pr = score.priority.value if score else "unscored"
        print(f"  [{pr:11s}] {c.name} — {c.professional_title or 'title unknown'} "
              f"@ {c.company or 'company unknown'}")
        print(f"      {c.profile_url or '(no profile URL on record)'}")
        if score:
            print(f"      next: {score.recommended_next_action[:110]}")
    if cap and len(rows) > cap:
        print(f"\nYou said your own weekly capacity is {cap}. The top {cap} are "
              f"the ones to work through; the rest keep.")
    print("\nNothing here has been sent. Invitations are yours to send in LinkedIn.")
    return 0


def cmd_status(args) -> int:
    _settings, _db, _audit, _gov, crm = _bootstrap(args)
    try:
        change = crm.set_status(args.candidate_id, CRMStatus(args.to_status),
                                confirmed_by_user=args.confirmed, note=args.note)
    except (CRMError, ValueError) as exc:
        print(f"Not recorded: {exc}", file=sys.stderr)
        return 1
    print(f"{args.candidate_id}: {change.from_status.value if change.from_status else '-'} "
          f"-> {change.to_status.value}"
          + (" (your confirmation recorded)" if args.confirmed else ""))
    return 0


def cmd_report(args) -> int:
    settings, db, _audit, _gov, crm = _bootstrap(args)
    from .models import ContentAnalytics
    from .reporting import build_report

    content = [ContentAnalytics.model_validate_json(r[0])
               for r in db.query("SELECT payload FROM content_analytics")]
    report = build_report(crm, settings, period=args.period, content=content)
    if args.json:
        print(report.model_dump_json(indent=2))
        return 0
    m = report.metrics
    print(f"# {report.period.title()} report {report.period_start} to {report.period_end}\n")
    print("## Funnel")
    for field_name, value in m.model_dump().items():
        if field_name in ("unavailable", "candidates_by_icp"):
            continue
        shown = "unavailable" if value is None else value
        print(f"  {field_name:42s} {shown}")
    if m.candidates_by_icp:
        print("\n## By ICP")
        for k, v in m.candidates_by_icp.items():
            print(f"  {k:30s} {v}")
    if m.unavailable:
        print("\n## Unavailable, and why")
        for k, reason in m.unavailable.items():
            print(f"  {k}:\n      {reason}")
    print("\n## Audience quality")
    for n in report.audience_quality_notes:
        print(f"  - {n}")
    print("\n## Recommended")
    for n in report.recommended_improvements:
        print(f"  - {n}")
    print("\n## What this cannot attribute")
    for n in report.attribution_limits:
        print(f"  - {n}")
    db.execute(
        """
        INSERT INTO reports (report_id, period, period_start, period_end,
                             generated_at, payload)
        VALUES (?,?,?,?,?,?)
        ON CONFLICT(report_id) DO UPDATE SET
            generated_at=excluded.generated_at, payload=excluded.payload
        """,
        (report.report_id, report.period, report.period_start.isoformat(),
         report.period_end.isoformat(), report.generated_at.isoformat(),
         report.model_dump_json()),
    )
    db.commit()
    return 0


def cmd_audit(args) -> int:
    _settings, _db, audit, _gov, _crm = _bootstrap(args)
    entries = audit.read(limit=args.limit,
                         decision=args.decision, subject_id=args.subject)
    if args.summary:
        print(json.dumps(audit.summarise(), indent=2))
        return 0
    print(f"{len(entries)} line(s), newest first:\n")
    for e in entries:
        rule = f" [{e.rule_cited}]" if e.rule_cited else ""
        print(f"{e.occurred_at.isoformat(timespec='seconds')} {e.actor:6s} "
              f"{e.decision:17s}{rule} {e.summary[:90]}")
    return 0


def cmd_export(args) -> int:
    _settings, _db, _audit, _gov, crm = _bootstrap(args)
    from .exporters import candidates_to_csv

    try:
        text = candidates_to_csv(crm, crm.all_candidates(), path=args.out,
                                 approved_by_user=args.approve)
    except SafetyRefusal as exc:
        print(f"Not exported: {exc}", file=sys.stderr)
        return 3
    if args.out:
        print(f"written to {args.out}")
    else:
        print(text)
    return 0


def cmd_forget(args) -> int:
    _settings, _db, _audit, _gov, crm = _bootstrap(args)
    try:
        counts = crm.forget(args.candidate_id, approved_by_user=args.approve)
    except SafetyRefusal as exc:
        print(f"Not deleted: {exc}", file=sys.stderr)
        return 3
    removed = {k: v for k, v in counts.items() if v}
    print(f"deleted: {removed or 'nothing found'}")
    print("The audit line recording this deletion is kept. It holds no profile "
          "fields and it is the only proof the deletion happened.")
    return 0


def cmd_subject_export(args) -> int:
    _settings, _db, _audit, _gov, crm = _bootstrap(args)
    from .exporters import subject_export_json

    try:
        text = subject_export_json(crm, args.candidate_id, path=args.out,
                                   approved_by_user=args.approve)
    except SafetyRefusal as exc:
        print(f"Not exported: {exc}", file=sys.stderr)
        return 3
    print(text if not args.out else f"written to {args.out}")
    return 0


# ---------------------------------------------------------------- parser ---


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lni",
        description="LinkedIn Network Intelligence. Not affiliated with LinkedIn. "
                    "Drafts and records; never sends.",
    )
    p.add_argument("--config-dir", default=None)
    p.add_argument("--extra-config", action="append", default=[])
    p.add_argument("--db", default=None, help="override the store path")
    p.add_argument("--skill", default="cli", help="skill name for the audit trail")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("config-check").set_defaults(func=cmd_config_check)
    sub.add_parser("init").set_defaults(func=cmd_init)

    m = sub.add_parser("missing", help="what a skill still needs from the user")
    m.add_argument("skill_name")
    m.set_defaults(func=cmd_missing)

    sc = sub.add_parser("safety-check", help="classify a request before acting on it")
    sc.add_argument("text", nargs="+")
    sc.set_defaults(func=cmd_safety_check)

    ic = sub.add_parser("import-candidates")
    ic.add_argument("path")
    ic.add_argument("--icp", default=None)
    ic.set_defaults(func=cmd_import_candidates)

    icx = sub.add_parser("import-connections",
                         help="the user's own LinkedIn Connections.csv")
    icx.add_argument("path")
    icx.add_argument("--icp", default=None)
    icx.set_defaults(func=cmd_import_connections)

    ia = sub.add_parser("import-analytics")
    ia.add_argument("path")
    ia.set_defaults(func=cmd_import_analytics)

    s = sub.add_parser("score")
    s.add_argument("ids", nargs="*")
    s.add_argument("--all", action="store_true")
    s.set_defaults(func=cmd_score)

    sl = sub.add_parser("shortlist")
    sl.add_argument("--size", type=int, default=None)
    sl.set_defaults(func=cmd_shortlist)

    st = sub.add_parser("status")
    st.add_argument("candidate_id")
    st.add_argument("to_status", choices=[s.value for s in CRMStatus])
    st.add_argument("--confirmed", action="store_true",
                    help="the user confirmed this happened on LinkedIn")
    st.add_argument("--note", default=None)
    st.set_defaults(func=cmd_status)

    r = sub.add_parser("report")
    r.add_argument("--period", choices=["weekly", "monthly"], default=None)
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_report)

    a = sub.add_parser("audit")
    a.add_argument("--limit", type=int, default=50)
    a.add_argument("--decision", default=None)
    a.add_argument("--subject", default=None)
    a.add_argument("--summary", action="store_true")
    a.set_defaults(func=cmd_audit)

    e = sub.add_parser("export")
    e.add_argument("-o", "--out", default=None)
    e.add_argument("--approve", action="store_true")
    e.set_defaults(func=cmd_export)

    f = sub.add_parser("forget")
    f.add_argument("candidate_id")
    f.add_argument("--approve", action="store_true")
    f.set_defaults(func=cmd_forget)

    se = sub.add_parser("subject-export")
    se.add_argument("candidate_id")
    se.add_argument("-o", "--out", default=None)
    se.add_argument("--approve", action="store_true")
    se.set_defaults(func=cmd_subject_export)

    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ConfigError as exc:
        print(f"Configuration problem:\n{exc}", file=sys.stderr)
        return 1
    except SafetyRefusal as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except CRMError as exc:
        print(f"Not done: {exc}", file=sys.stderr)
        return 1
    except ValidationError as exc:
        # A record in the store no longer satisfies its own model. Say which
        # invariant failed rather than printing a stack trace at the user.
        first = exc.errors()[0] if exc.errors() else {}
        print(
            "A stored record does not satisfy its model, so it was not loaded:\n"
            f"  {first.get('msg', exc)}\n"
            "This is a bug, not a configuration problem. The store is unchanged.",
            file=sys.stderr,
        )
        return 4
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":
    sys.exit(main())
