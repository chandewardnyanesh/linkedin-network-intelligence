"""Duplicate detection.

Two people arrive from two files and have to become one record. The hard part
is not the exact match; it is deciding when two near-matches are the same
person without silently merging two different ones.

The policy here: **exact identity merges automatically, near identity is
reported for the user to decide.** A wrong automatic merge destroys a record
and is invisible afterwards, which is worse than a duplicate the user can see.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Iterable, Literal, Optional, Sequence

from .models import Candidate, normalise_profile_url

__all__ = ["DuplicateMatch", "normalise_name", "normalise_company",
           "compare", "find_duplicates", "group_exact"]

# Normalisation lives in `lni.models`, because `candidate_id_for` needs the
# same functions and two copies of a normaliser is two different identities.
from .models import _fold, normalise_company, normalise_name  # noqa: E402


@dataclass(frozen=True)
class DuplicateMatch:
    """Two records that may be the same person."""

    left_id: str
    right_id: str
    kind: Literal["exact_url", "exact_name_company", "probable", "possible"]
    score: float
    reason: str

    @property
    def auto_mergeable(self) -> bool:
        """Only exact identity merges without asking."""
        return self.kind in ("exact_url", "exact_name_company")


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def compare(left: Candidate, right: Candidate) -> Optional[DuplicateMatch]:
    """Judge two candidates. None means they look like different people."""
    if left.candidate_id == right.candidate_id:
        # The id is derived, so an equal id means an equal identity basis.
        # Report which basis it was, since that is what a reviewer needs.
        by_url = bool(left.profile_url and right.profile_url)
        return DuplicateMatch(
            left.candidate_id, right.candidate_id,
            "exact_url" if by_url else "exact_name_company", 1.0,
            "same profile URL" if by_url else "same normalised name and company",
        )

    lu = normalise_profile_url(left.profile_url) if left.profile_url else None
    ru = normalise_profile_url(right.profile_url) if right.profile_url else None
    if lu and ru:
        if lu == ru:
            return DuplicateMatch(
                left.candidate_id, right.candidate_id, "exact_url", 1.0,
                f"same profile URL ({lu})",
            )
        # Two different profile URLs are two different accounts. A person may
        # hold two, but merging them would lose one, so this is never a match.
        return None

    ln, rn = normalise_name(left.name), normalise_name(right.name)
    lc, rc = normalise_company(left.company), normalise_company(right.company)

    if ln and ln == rn and lc and lc == rc:
        return DuplicateMatch(
            left.candidate_id, right.candidate_id, "exact_name_company", 1.0,
            f"same name and company ({ln} / {lc})",
        )

    name_sim = _ratio(ln, rn)
    if name_sim < 0.84:
        return None

    comp_sim = _ratio(lc, rc) if (lc and rc) else 0.0
    title_sim = _ratio(_fold(left.professional_title or ""),
                       _fold(right.professional_title or ""))

    if lc and rc and comp_sim >= 0.9:
        return DuplicateMatch(
            left.candidate_id, right.candidate_id, "probable",
            round((name_sim + comp_sim) / 2, 3),
            f"near-identical name ({name_sim:.2f}) at the same company",
        )
    if ln == rn and (not lc or not rc):
        return DuplicateMatch(
            left.candidate_id, right.candidate_id, "possible", round(name_sim, 3),
            "identical name, company missing on one side",
        )
    if name_sim >= 0.92 and title_sim >= 0.8:
        return DuplicateMatch(
            left.candidate_id, right.candidate_id, "possible",
            round((name_sim + title_sim) / 2, 3),
            f"similar name ({name_sim:.2f}) and similar title",
        )
    return None


def group_exact(candidates: Sequence[Candidate]) -> dict[str, list[Candidate]]:
    """Group by exact identity key, which is what the id already encodes."""
    out: dict[str, list[Candidate]] = {}
    for c in candidates:
        out.setdefault(c.candidate_id, []).append(c)
    return out


def find_duplicates(candidates: Iterable[Candidate]) -> list[DuplicateMatch]:
    """All duplicate pairs in a batch, exact first.

    O(n^2) on the near-match pass, which is the right trade at the batch sizes
    this bundle works in (a weekly run is 100 records). The exact pass is
    hashed, so a large import of already-known people stays cheap.
    """
    items = list(candidates)
    matches: list[DuplicateMatch] = []

    # Exact pass, hashed.
    by_id: dict[str, Candidate] = {}
    remaining: list[Candidate] = []
    for c in items:
        if c.candidate_id in by_id:
            matches.append(
                DuplicateMatch(by_id[c.candidate_id].candidate_id, c.candidate_id,
                               "exact_url" if c.profile_url else "exact_name_company",
                               1.0, "same identity key")
            )
        else:
            by_id[c.candidate_id] = c
            remaining.append(c)

    # Near pass, pairwise over the deduplicated set.
    for i, left in enumerate(remaining):
        for right in remaining[i + 1:]:
            m = compare(left, right)
            if m:
                # Auto-mergeable pairs are reported as well as merged: a caller
                # deciding whether to merge needs to see them.
                matches.append(m)
    order = {"exact_url": 0, "exact_name_company": 1, "probable": 2, "possible": 3}
    return sorted(matches, key=lambda m: (order[m.kind], -m.score))
