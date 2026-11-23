"""Content to audience attribution.

The question this answers: *which topics brought in people worth having?* —
not which post got the most impressions.

The honest-attribution discipline here is adapted from the monthly Page report
in `chandewardnyanesh/linkedin-company-page-skills` (`page-performance-report`,
MIT): every report states plainly what it cannot attribute. That section is
required output, not a disclaimer, and `limits_for` builds it from what the
data actually lacks rather than from a fixed paragraph.

Metrics are never estimated. A figure the export did not carry stays `None` and
is reported as unavailable with the reason.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Optional, Sequence

from .config import Settings
from .models import (
    AudienceSegment, Candidate, ContentAnalytics, CRMStatus, TopicAffinity,
)

__all__ = ["TopicRollup", "AffinityMatrix", "build_affinity", "audience_gap",
           "growth_series", "limits_for", "recommend_topics"]


@dataclass
class TopicRollup:
    """Everything known about one topic across the corpus."""

    topic: str
    posts: int = 0
    impressions: Optional[int] = None
    reactions: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    followers_gained: Optional[int] = None
    profile_views: Optional[int] = None
    business_outcomes: list[str] = field(default_factory=list)
    sufficient: bool = True

    @property
    def engagement_per_post(self) -> Optional[float]:
        parts = [v for v in (self.reactions, self.comments, self.shares) if v is not None]
        if not parts or not self.posts:
            return None
        return round(sum(parts) / self.posts, 2)

    @property
    def comments_per_post(self) -> Optional[float]:
        if self.comments is None or not self.posts:
            return None
        return round(self.comments / self.posts, 2)

    @property
    def followers_per_post(self) -> Optional[float]:
        if self.followers_gained is None or not self.posts:
            return None
        return round(self.followers_gained / self.posts, 2)


def _add(a: Optional[int], b: Optional[int]) -> Optional[int]:
    """Sum that keeps `None` meaning 'not carried by the source'.

    `None + 5` is 5, but a total built only from Nones stays None rather than
    becoming a confident zero.
    """
    if a is None and b is None:
        return None
    return (a or 0) + (b or 0)


@dataclass
class AffinityMatrix:
    """Topic rollups plus the per-segment cells, with its own limits attached."""

    rollups: dict[str, TopicRollup]
    cells: list[TopicAffinity]
    limits: list[str]
    posts_considered: int
    posts_without_topics: int

    def best_by(self, metric: str = "comments_per_post", *, min_posts: int = 1
                ) -> list[TopicRollup]:
        """Topics ordered by a metric, excluding those with too little data."""
        usable = [r for r in self.rollups.values()
                  if r.sufficient and r.posts >= min_posts
                  and getattr(r, metric, None) is not None]
        return sorted(usable, key=lambda r: -(getattr(r, metric) or 0))


def build_affinity(
    posts: Iterable[ContentAnalytics],
    settings: Settings,
    *,
    segments: Sequence[AudienceSegment] = (),
) -> AffinityMatrix:
    """Roll post analytics up by topic, and build the topic x segment matrix.

    A topic below `audience.min_posts_per_topic` is kept but marked
    insufficient, so the user sees it exists without it driving a decision off
    two data points.
    """
    items = list(posts)
    rollups: dict[str, TopicRollup] = {}
    untopiced = 0

    for p in items:
        if not p.topics:
            untopiced += 1
            continue
        for topic in p.topics:
            key = topic.strip()
            if not key:
                continue
            r = rollups.setdefault(key, TopicRollup(topic=key))
            r.posts += 1
            r.impressions = _add(r.impressions, p.impressions if p.impressions is not None
                                 else p.members_reached)
            r.reactions = _add(r.reactions, p.reactions)
            r.comments = _add(r.comments, p.comments)
            r.shares = _add(r.shares, p.shares)
            r.followers_gained = _add(r.followers_gained, p.followers_gained)
            r.profile_views = _add(r.profile_views, p.profile_views_attributed)
            r.business_outcomes.extend(p.business_outcomes)

    floor = settings.audience.min_posts_per_topic
    for r in rollups.values():
        r.sufficient = r.posts >= floor

    cells: list[TopicAffinity] = []
    for topic, r in rollups.items():
        cells.append(
            TopicAffinity(
                topic=topic, segment_key=None, posts_counted=r.posts,
                impressions=r.impressions, reactions=r.reactions,
                comments=r.comments, shares=r.shares,
                followers_gained=r.followers_gained,
                notes=None if r.sufficient else
                f"only {r.posts} post(s); below the {floor}-post floor",
            )
        )
        for seg in segments:
            if topic.lower() in {t.lower() for t in _segment_topics(seg)}:
                cells.append(
                    TopicAffinity(
                        topic=topic, segment_key=seg.key, posts_counted=r.posts,
                        target_audience_share=seg.share_of_audience,
                        notes=("segment association is declared in the audience "
                               "configuration, not measured per post"),
                    )
                )

    return AffinityMatrix(
        rollups=rollups, cells=cells,
        limits=limits_for(items, settings, segments=segments),
        posts_considered=len(items), posts_without_topics=untopiced,
    )


def _segment_topics(seg: AudienceSegment) -> list[str]:
    """Topics a segment is declared to care about, from its evidence lines."""
    out: list[str] = []
    for e in seg.evidence:
        if e.interpretation:
            out.append(e.interpretation)
    return out


def limits_for(posts: Sequence[ContentAnalytics], settings: Settings,
               *, segments: Sequence[AudienceSegment] = ()) -> list[str]:
    """What this data cannot attribute. Built from the gaps, not boilerplate."""
    out: list[str] = []
    if not posts:
        return ["No post analytics supplied, so nothing can be attributed at all."]

    missing_followers = sum(1 for p in posts if p.followers_gained is None)
    if missing_followers:
        out.append(
            f"{missing_followers} of {len(posts)} posts carry no follower figure, "
            f"so 'which topic grew the audience' is answerable only for the rest."
        )
    missing_views = sum(1 for p in posts if p.profile_views_attributed is None)
    if missing_views == len(posts):
        out.append(
            "No post carries attributed profile views. LinkedIn does not expose "
            "per-post profile views to most accounts, so the link between a "
            "specific post and a profile visit is not in this data."
        )
    outcomes = sum(len(p.business_outcomes) for p in posts)
    if not outcomes:
        out.append(
            "No business outcomes are recorded against any post. Engagement "
            "counts are all this can report; whether any of it produced a "
            "conversation is not in the data."
        )
    if not segments:
        out.append(
            "No audience segments are defined, so engagement cannot be compared "
            "by audience quality — only in total."
        )
    else:
        measured = [s for s in segments if s.size is not None]
        if not measured:
            out.append(
                "Audience segments are defined but none carries a counted size, "
                "so shares of the audience are not computed."
            )
    out.append(
        "Per-post engagement and follower change are correlated in time, not "
        "causally linked. A week with a conference talk in it moves both."
    )
    out.append(
        "Impressions are a delivery figure the platform reports about itself. "
        "They are not evidence that anyone read anything."
    )
    return out


def audience_gap(
    segments: Sequence[AudienceSegment],
    settings: Settings,
) -> dict:
    """Where the current audience sits against the audience the user wants."""
    desired = {d.icp_key: d for d in settings.audience_plan.desired_audience}
    if not desired:
        return {
            "status": "no target",
            "detail": ("audience.desired_audience is empty, so there is no gap to "
                       "measure. Which audience do you want more of?"),
            "gaps": [],
        }

    total = sum(s.size for s in segments if s.size is not None)
    gaps = []
    for icp_key, want in desired.items():
        matching = [s for s in segments if icp_key in s.matched_icp_keys]
        have_size = sum(s.size for s in matching if s.size is not None)
        have_share = (have_size / total) if total else None
        gap = None
        if want.target_share is not None and have_share is not None:
            gap = round(want.target_share - have_share, 4)
        gaps.append({
            "icp_key": icp_key,
            "why": want.why,
            "segments_matched": [s.key for s in matching],
            "current_size": have_size if matching else None,
            "current_share": round(have_share, 4) if have_share is not None else None,
            "target_share": want.target_share,
            "gap": gap,
            "basis": ("counted from segment sizes" if total else
                      "no counted segment sizes, so share is unavailable"),
        })
    unwanted = [{"label": u.label, "why": u.why}
                for u in settings.audience_plan.unwanted_audience]
    return {
        "status": "measured" if total else "target set, audience uncounted",
        "audience_counted": total or None,
        "gaps": sorted(gaps, key=lambda g: -(g["gap"] or 0)),
        "unwanted": unwanted,
    }


def growth_series(posts: Sequence[ContentAnalytics]) -> list[dict]:
    """Followers and engagement by month, where the data supports it."""
    buckets: dict[str, dict] = defaultdict(
        lambda: {"posts": 0, "followers_gained": None, "engagement": None}
    )
    for p in posts:
        if not p.published_on:
            continue
        key = p.published_on.strftime("%Y-%m")
        b = buckets[key]
        b["posts"] += 1
        b["followers_gained"] = _add(b["followers_gained"], p.followers_gained)
        b["engagement"] = _add(b["engagement"], p.engagement_total)
    return [{"month": k, **v} for k, v in sorted(buckets.items())]


def recommend_topics(
    matrix: AffinityMatrix,
    settings: Settings,
    *,
    gap: Optional[dict] = None,
) -> list[dict]:
    """Which topics to write more of, and why — with the caveat on each.

    Ranked on comments per post rather than impressions: a comment is a person
    choosing to be identified with the topic, which is what brings the right
    audience in. Impressions are delivery.
    """
    floor = settings.audience.min_posts_per_topic
    ranked = matrix.best_by("comments_per_post", min_posts=floor)
    out: list[dict] = []
    for r in ranked[:6]:
        out.append({
            "topic": r.topic,
            "posts": r.posts,
            "comments_per_post": r.comments_per_post,
            "followers_per_post": r.followers_per_post,
            "basis": (f"{r.posts} posts, {r.comments or 0} comments, "
                      f"{r.followers_gained if r.followers_gained is not None else 'follower change unavailable'}"),
            "caveat": ("ranked on comments per post, not impressions. Whether "
                       "those commenters are the audience you want depends on "
                       "who they are, which this metric does not know."),
        })
    thin = [r.topic for r in matrix.rollups.values() if not r.sufficient]
    if thin:
        out.append({
            "topic": None,
            "note": (f"{len(thin)} topic(s) have fewer than {floor} posts and are "
                     f"not ranked: {', '.join(sorted(thin)[:6])}. Not evidence "
                     f"they do not work — evidence there is not enough to tell."),
        })
    if gap and gap.get("gaps"):
        biggest = gap["gaps"][0]
        if biggest.get("gap") and biggest["gap"] > 0:
            out.append({
                "topic": None,
                "note": (f"The largest audience gap is {biggest['icp_key']} "
                         f"({biggest['gap']:+.0%} against target). None of the "
                         f"topics above is ranked by whether it reaches that "
                         f"group; pick from the ICP's content_interests for that."),
            })
    return out
