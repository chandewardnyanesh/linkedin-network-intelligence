"""Typed data models for the LinkedIn Network Intelligence bundle.

Every record that crosses a skill boundary or reaches storage is defined here.
Fourteen model families, matching the Phase-5 data architecture:

    1  UserProfile              8  InvitationDraft
    2  ICPDefinition            9  StatusChange (manually confirmed)
    3  AudienceSegment         10  RelationshipEvent
    4  Candidate               11  BusinessOpportunity
    5  CandidateScore          12  ContentAnalytics
    6  SourceProvenance        13  PeriodReport
    7  ConnectionRecommendation 14 AuditEntry

Three rules are enforced by the types rather than by documentation:

* An unverified claim cannot masquerade as evidence. `Evidence.observed` is
  mandatory, and `Evidence` carries its own source and confidence.
* A prediction cannot masquerade as an observation. Every assessment separates
  `observations` from `predictions`.
* A record cannot exist without provenance. `Candidate.sources` must be
  non-empty.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, ClassVar, Literal, Optional
from urllib.parse import urlparse, urlunparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

__all__ = [
    "Confidence", "SourceKind", "CRMStatus", "PriorityClass", "PropensityBand",
    "OpportunityStage", "Seniority", "TouchChannel", "ActionClass",
    "LEGAL_TRANSITIONS", "SCORE_COMPONENTS",
    "SourceProvenance", "Evidence", "UserProfile", "ICPDefinition",
    "AudienceSegment", "TopicAffinity", "Candidate", "ComponentScore",
    "CandidateScore", "PropensityAssessment", "ConnectionRecommendation",
    "InvitationDraft", "StatusChange", "RelationshipEvent",
    "BusinessOpportunity", "ContentAnalytics", "FunnelMetrics", "PeriodReport",
    "AuditEntry", "normalise_profile_url", "normalise_name", "normalise_company",
    "candidate_id_for", "utcnow",
]


def utcnow() -> datetime:
    """Timezone-aware UTC now. Naive datetimes are a source of silent bugs."""
    return datetime.now(timezone.utc)


# --------------------------------------------------------------- enums ---


class Confidence(str, Enum):
    """How much weight a claim can carry.

    `none` is not an absence of a value; it is an explicit statement that the
    claim has no support and must not be used as evidence.
    """

    none = "none"
    low = "low"
    medium = "medium"
    high = "high"

    @property
    def weight(self) -> float:
        return {"none": 0.0, "low": 0.34, "medium": 0.67, "high": 1.0}[self.value]

    @property
    def usable_as_evidence(self) -> bool:
        return self is not Confidence.none


class SourceKind(str, Enum):
    """Where a record or a claim came from.

    This enum is the data-source boundary made explicit. There is no member for
    a LinkedIn scrape or a browser-automation run, so a record sourced that way
    cannot be represented, let alone stored.
    """

    user_supplied_url = "user_supplied_url"
    user_supplied_csv = "user_supplied_csv"
    user_supplied_note = "user_supplied_note"
    linkedin_data_export = "linkedin_data_export"
    linkedin_analytics_export = "linkedin_analytics_export"
    official_api = "official_api"
    company_website = "company_website"
    professional_directory = "professional_directory"
    public_publication = "public_publication"
    conference_or_event = "conference_or_event"
    referral = "referral"
    upstream_skill_export = "upstream_skill_export"

    @property
    def requires_authorisation_note(self) -> bool:
        return self is SourceKind.official_api


class CRMStatus(str, Enum):
    discovered = "discovered"
    researching = "researching"
    qualified = "qualified"
    shortlisted = "shortlisted"
    invitation_prepared = "invitation_prepared"
    manually_invited = "manually_invited"
    accepted = "accepted"
    conversation_started = "conversation_started"
    engaged = "engaged"
    potential_lead = "potential_lead"
    qualified_opportunity = "qualified_opportunity"
    converted = "converted"
    archived = "archived"


#: Legal status transitions. Anything absent is rejected by `lni.crm`.
#: Every status may go to `archived`; `archived` may be revived to `researching`.
LEGAL_TRANSITIONS: dict[CRMStatus, set[CRMStatus]] = {
    CRMStatus.discovered: {CRMStatus.researching, CRMStatus.qualified, CRMStatus.archived},
    CRMStatus.researching: {CRMStatus.qualified, CRMStatus.discovered, CRMStatus.archived},
    CRMStatus.qualified: {CRMStatus.shortlisted, CRMStatus.researching, CRMStatus.archived},
    CRMStatus.shortlisted: {CRMStatus.invitation_prepared, CRMStatus.qualified, CRMStatus.archived},
    CRMStatus.invitation_prepared: {CRMStatus.manually_invited, CRMStatus.shortlisted, CRMStatus.archived},
    # No automatic path from invitation_prepared to accepted: acceptance is a
    # fact the user confirms, and an invitation must be recorded as sent first.
    CRMStatus.manually_invited: {CRMStatus.accepted, CRMStatus.archived},
    CRMStatus.accepted: {CRMStatus.conversation_started, CRMStatus.engaged, CRMStatus.archived},
    CRMStatus.conversation_started: {CRMStatus.engaged, CRMStatus.potential_lead, CRMStatus.archived},
    CRMStatus.engaged: {CRMStatus.potential_lead, CRMStatus.conversation_started, CRMStatus.archived},
    CRMStatus.potential_lead: {CRMStatus.qualified_opportunity, CRMStatus.engaged, CRMStatus.archived},
    CRMStatus.qualified_opportunity: {CRMStatus.converted, CRMStatus.engaged, CRMStatus.archived},
    CRMStatus.converted: {CRMStatus.engaged, CRMStatus.archived},
    CRMStatus.archived: {CRMStatus.researching},
}


class PriorityClass(str, Enum):
    priority_1 = "priority_1"
    priority_2 = "priority_2"
    priority_3 = "priority_3"
    monitor = "monitor"
    excluded = "excluded"


class PropensityBand(str, Enum):
    very_low = "very_low"
    low = "low"
    moderate = "moderate"
    high = "high"
    very_high = "very_high"
    insufficient_evidence = "insufficient_evidence"


class OpportunityStage(str, Enum):
    hypothesis = "hypothesis"
    signal_observed = "signal_observed"
    discussed = "discussed"
    qualified = "qualified"
    declined = "declined"
    won = "won"
    lost = "lost"


class Seniority(str, Enum):
    individual_contributor = "individual_contributor"
    senior_ic = "senior_ic"
    lead = "lead"
    manager = "manager"
    director = "director"
    vp = "vp"
    c_level = "c_level"
    founder_owner = "founder_owner"
    board_investor = "board_investor"
    student_early_career = "student_early_career"
    unknown = "unknown"


class TouchChannel(str, Enum):
    linkedin_comment = "linkedin_comment"
    linkedin_reaction = "linkedin_reaction"
    linkedin_dm = "linkedin_dm"
    linkedin_invitation = "linkedin_invitation"
    email = "email"
    call = "call"
    meeting = "meeting"
    event = "event"
    other = "other"


class ActionClass(str, Enum):
    """What a requested action would do. Used by `lni.safety`.

    `prohibited` members exist so that a refusal can be specific about what was
    refused, rather than returning a generic denial.
    """

    read_user_supplied = "read_user_supplied"
    read_public_page = "read_public_page"
    compute_local = "compute_local"
    write_local_record = "write_local_record"
    draft_for_human = "draft_for_human"
    export_user_data = "export_user_data"
    delete_user_data = "delete_user_data"
    # Prohibited classes below.
    scrape_linkedin = "scrape_linkedin"
    automate_browser = "automate_browser"
    send_invitation = "send_invitation"
    send_message = "send_message"
    automate_engagement = "automate_engagement"
    bypass_captcha = "bypass_captcha"
    evade_detection = "evade_detection"
    manufacture_engagement = "manufacture_engagement"
    unauthorised_api = "unauthorised_api"
    access_private_data = "access_private_data"


#: The six scoring components and their default point allocation.
SCORE_COMPONENTS: tuple[str, ...] = (
    "icp_relevance",
    "observable_activity",
    "engagement_signals",
    "topic_alignment",
    "professional_influence",
    "business_opportunity",
)


# ---------------------------------------------------- shared value types ---


class _Base(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=False,
        validate_assignment=True,
        str_strip_whitespace=True,
    )


class SourceProvenance(_Base):
    """Model 6. Where one fact or one record came from, and when it was checked.

    A record with no provenance is not storable; see `Candidate.sources`.
    """

    kind: SourceKind
    detail: str = Field(
        min_length=1,
        max_length=500,
        description="Human-readable origin: a filename, a URL, a directory "
        "name, 'pasted by user on 2026-11-23'. Specific enough to re-check.",
    )
    retrieved_at: datetime = Field(default_factory=utcnow)
    last_verified: Optional[date] = None
    authorisation_note: Optional[str] = Field(
        default=None,
        max_length=500,
        description="For official_api only: which authorised access was used.",
    )

    @model_validator(mode="after")
    def _api_needs_authorisation(self) -> "SourceProvenance":
        if self.kind.requires_authorisation_note and not self.authorisation_note:
            raise ValueError(
                "official_api provenance requires authorisation_note naming the "
                "authorised access in use"
            )
        return self

    @property
    def is_stale(self) -> bool:
        """True when the fact has never been verified or was verified long ago."""
        if self.last_verified is None:
            return True
        return (date.today() - self.last_verified).days > 180


class Evidence(_Base):
    """One supporting fact, with what was actually seen and how sure we are.

    `observed` is the raw, checkable thing. `interpretation` is what it is taken
    to mean, and is always optional — a piece of evidence with no interpretation
    is still evidence; an interpretation with no observation is not.
    """

    observed: str = Field(
        min_length=1,
        max_length=1000,
        description="The checkable fact. 'Commented on 3 of the last 8 posts', "
        "not 'is highly engaged'.",
    )
    interpretation: Optional[str] = Field(default=None, max_length=1000)
    source: SourceProvenance
    confidence: Confidence = Confidence.medium
    observed_on: Optional[date] = None

    @field_validator("observed")
    @classmethod
    def _not_a_prediction(cls, v: str) -> str:
        lowered = v.lower()
        for tell in ("will likely", "is likely to", "probably will", "i predict",
                     "expected to engage", "should engage"):
            if tell in lowered:
                raise ValueError(
                    f"`observed` must state what was seen, not what is predicted "
                    f"(found {tell!r}). Put predictions in the assessment's "
                    f"`predictions` field."
                )
        return v

    @property
    def usable(self) -> bool:
        return self.confidence.usable_as_evidence


# ------------------------------------------------------------- model 1 ---


class UserProfile(_Base):
    """Model 1. Who the account owner is and what they are trying to achieve.

    Every field is optional. The package ships no personal data, and a missing
    field makes a skill ask rather than invent — see `lni.config.missing_for`.
    """

    display_name: Optional[str] = None
    headline: Optional[str] = None
    profile_url: Optional[str] = None
    primary_objective: Optional[str] = Field(
        default=None,
        description="What the networking is for, in the user's own words.",
    )
    secondary_objectives: list[str] = Field(default_factory=list)
    industry: Optional[str] = None
    geography: Optional[str] = None
    languages: list[str] = Field(default_factory=list)
    content_topics: list[str] = Field(
        default_factory=list,
        description="Topics the user actually publishes about. Used for "
        "topic-alignment scoring; without it that component abstains.",
    )
    services_offered: list[str] = Field(default_factory=list)
    weekly_research_target: int = Field(default=100, ge=1, le=1000)
    weekly_invitation_capacity: Optional[int] = Field(
        default=None,
        ge=0,
        description="How many invitations the user is willing to send by hand "
        "in a week. Never a platform limit to optimise against; a personal "
        "capacity so the shortlist is not longer than the week.",
    )
    notes: Optional[str] = None

    @field_validator("profile_url")
    @classmethod
    def _normalise(cls, v: Optional[str]) -> Optional[str]:
        return normalise_profile_url(v) if v else v

    @property
    def is_configured(self) -> bool:
        return bool(self.primary_objective and (self.industry or self.content_topics))


# ------------------------------------------------------------- model 2 ---


class ICPDefinition(_Base):
    """Model 2. One Ideal Connection / Customer Profile.

    Several of these coexist. A candidate may match more than one; the match
    with the highest weighted fit becomes the primary classification and the
    rest are recorded as secondary.
    """

    key: str = Field(
        pattern=r"^[a-z][a-z0-9_]{1,48}$",
        description="Stable machine key, e.g. 'ai_technology_network'.",
    )
    label: str = Field(min_length=1, max_length=120)
    purpose: Literal[
        "professional_networking",
        "personal_brand_growth",
        "ai_technology_networking",
        "startup_ecosystem",
        "business_development",
        "agency_clients",
        "strategic_partnerships",
        "industry_specific",
    ]
    priority: int = Field(
        default=3, ge=1, le=5,
        description="1 is highest. Breaks ties when a candidate matches "
        "several ICPs with equal fit.",
    )
    active: bool = True

    job_titles: list[str] = Field(default_factory=list)
    title_exclusions: list[str] = Field(default_factory=list)
    seniority: list[Seniority] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    company_size_bands: list[
        Literal["1", "2-10", "11-50", "51-200", "201-500", "501-1000",
                "1001-5000", "5001-10000", "10001+"]
    ] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)
    professional_interests: list[str] = Field(default_factory=list)
    content_interests: list[str] = Field(default_factory=list)
    business_relevance: Optional[str] = Field(
        default=None,
        description="Why this ICP matters commercially or professionally. One "
        "or two sentences. An ICP that cannot answer this is a wish list.",
    )
    exclusion_criteria: list[str] = Field(
        default_factory=list,
        description="Disqualifiers stated as checkable conditions. This field "
        "does more work than any other: it is what keeps a discovery run from "
        "returning recruiters, resellers and bulk connectors.",
    )
    observable_engagement_signals: list[str] = Field(
        default_factory=list,
        description="Things a person in this ICP visibly does, each checkable "
        "from a source this bundle may use. 'Comments on technical posts with "
        "more than one sentence', not 'cares about quality'.",
    )
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _must_be_falsifiable(self) -> "ICPDefinition":
        if self.active and not any(
            [self.job_titles, self.seniority, self.industries,
             self.professional_interests, self.content_interests]
        ):
            raise ValueError(
                f"ICP {self.key!r} is active but defines no positive criteria. "
                "An ICP with only exclusions matches everyone who is not "
                "excluded, which is not a profile."
            )
        return self

    @property
    def is_falsifiable(self) -> bool:
        """An ICP you can test a candidate against without guessing."""
        return bool(self.observable_engagement_signals and self.exclusion_criteria)


# ------------------------------------------------------- models 3 and 3b ---


class AudienceSegment(_Base):
    """Model 3. A group within the user's existing audience."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,48}$")
    label: str = Field(min_length=1, max_length=120)
    description: Optional[str] = None
    matched_icp_keys: list[str] = Field(default_factory=list)
    size: Optional[int] = Field(default=None, ge=0)
    size_basis: Optional[str] = Field(
        default=None,
        description="What the size was counted from. Required when size is set.",
    )
    share_of_audience: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    quality: Literal["target", "adjacent", "irrelevant", "unknown"] = "unknown"
    engagement_rate: Optional[float] = Field(default=None, ge=0.0)
    evidence: list[Evidence] = Field(default_factory=list)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _size_needs_basis(self) -> "AudienceSegment":
        if self.size is not None and not self.size_basis:
            raise ValueError(
                "a segment size must say what it was counted from; an "
                "uncounted size is an estimate dressed as a measurement"
            )
        return self


class TopicAffinity(_Base):
    """Topic x segment engagement, the cell of the topic affinity matrix."""

    topic: str = Field(min_length=1, max_length=120)
    segment_key: Optional[str] = None
    posts_counted: int = Field(ge=0)
    impressions: Optional[int] = Field(default=None, ge=0)
    reactions: Optional[int] = Field(default=None, ge=0)
    comments: Optional[int] = Field(default=None, ge=0)
    shares: Optional[int] = Field(default=None, ge=0)
    followers_gained: Optional[int] = Field(default=None, ge=0)
    substantive_comments: Optional[int] = Field(
        default=None, ge=0,
        description="Comments longer than a reaction phrase. Counted only when "
        "the source carries comment text; otherwise None, never zero.",
    )
    target_audience_share: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _no_rate_without_denominator(self) -> "TopicAffinity":
        if self.posts_counted == 0 and any(
            v is not None for v in (self.impressions, self.reactions, self.comments)
        ):
            raise ValueError(
                "metrics recorded against zero posts; set posts_counted or drop "
                "the metrics"
            )
        return self

    @property
    def engagement_per_post(self) -> Optional[float]:
        if not self.posts_counted:
            return None
        parts = [v for v in (self.reactions, self.comments, self.shares) if v is not None]
        if not parts:
            return None
        return sum(parts) / self.posts_counted


# ------------------------------------------------------------- model 4 ---

_URL_RE = re.compile(r"^https?://", re.I)


_COMPANY_SUFFIXES = frozenset({
    "ltd", "limited", "llc", "inc", "incorporated", "plc", "gmbh", "bv", "nv",
    "sa", "ag", "pte", "pvt", "private", "co", "company", "corp", "corporation",
    "llp", "lp", "oy", "ab", "as", "sas", "srl", "spa", "kk", "pty", "group",
    "holdings", "technologies", "solutions", "services", "international",
})
_NAME_TITLES = frozenset({"mr", "mrs", "ms", "miss", "dr", "prof", "sir", "madam", "mx"})
_NAME_POSTNOMINALS = frozenset({
    "jr", "sr", "ii", "iii", "iv", "phd", "mba", "msc", "bsc", "ba", "ma",
    "cpa", "pmp", "cfa", "md", "esq", "eng", "ca",
})
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def _fold(text: str) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _WS_RE.sub(" ", _PUNCT_RE.sub(" ", stripped.lower())).strip()


def normalise_name(name: str) -> str:
    """A comparable form of a person's name.

    Drops honorifics and post-nominals, folds accents, keeps word order. Word
    order is kept deliberately: reordering would make "Hassan Ali" and "Ali
    Hassan" identical, and they are often two people.

    >>> normalise_name("Dr. Jose Alvarez-Perez, PhD")
    'jose alvarez perez'
    """
    words = [w for w in _fold(name).split() if w]
    words = [w for w in words
             if w not in _NAME_TITLES and w not in _NAME_POSTNOMINALS]
    return " ".join(words)


def normalise_company(company: Optional[str]) -> str:
    """A comparable form of a company name, with legal suffixes removed.

    >>> normalise_company("Acme Technologies Pvt. Ltd.")
    'acme'
    """
    if not company:
        return ""
    words = [w for w in _fold(company).split()
             if w and w not in _COMPANY_SUFFIXES]
    return " ".join(words)


def normalise_profile_url(url: str) -> str:
    """Canonical form of a LinkedIn profile URL, for identity and dedupe.

    Lowercases host and path, strips `www.` and locale subdomains, drops query
    strings, fragments and trailing slashes. A bare slug or `linkedin.com/in/x`
    without a scheme is accepted and completed.

    >>> normalise_profile_url("https://IN.linkedin.com/in/Some-Person/?trk=x")
    'https://linkedin.com/in/some-person'
    >>> normalise_profile_url("linkedin.com/in/abc/")
    'https://linkedin.com/in/abc'
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError("empty profile URL")
    if not _URL_RE.match(raw):
        raw = "https://" + raw.lstrip("/")
    parts = urlparse(raw)
    host = (parts.netloc or "").lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    # Locale subdomains: in.linkedin.com, de.linkedin.com, ...
    if host.endswith(".linkedin.com") and host.count(".") == 2:
        host = "linkedin.com"
    path = (parts.path or "").rstrip("/").lower()
    if not path:
        raise ValueError(f"profile URL has no path: {url!r}")
    return urlunparse(("https", host, path, "", "", ""))


def candidate_id_for(profile_url: Optional[str], name: str,
                     company: Optional[str] = None) -> str:
    """Deterministic internal id.

    Derived from the normalised profile URL when there is one, so the same
    person imported from two files gets one id. Falls back to name+company,
    which is weaker and is why `Candidate.identity_basis` records which was
    used.
    """
    if profile_url:
        basis = normalise_profile_url(profile_url)
    else:
        # Normalised, so that "Acme Ltd" and "Acme" are the same employer and
        # the same person imported from two files gets one id.
        basis = f"{normalise_name(name)}|{normalise_company(company)}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"cand_{digest}"


class Candidate(_Base):
    """Model 4. One professional under consideration.

    Carries every field the Phase-5 candidate record requires. Scores and
    propensity are references to their own models rather than loose numbers, so
    a score can never appear without its evidence.
    """

    candidate_id: str = Field(pattern=r"^cand_[0-9a-f]{16}$")
    name: str = Field(min_length=1, max_length=200)
    profile_url: Optional[str] = None
    identity_basis: Literal["profile_url", "name_company"] = "profile_url"

    professional_title: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    geography: Optional[str] = None
    seniority: Seniority = Seniority.unknown
    company_size_band: Optional[str] = None

    primary_icp_key: Optional[str] = None
    secondary_icp_keys: list[str] = Field(default_factory=list)

    relevance_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    engagement_propensity: PropensityBand = PropensityBand.insufficient_evidence
    business_opportunity_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    confidence: Confidence = Confidence.none

    evidence: list[Evidence] = Field(default_factory=list)
    sources: list[SourceProvenance] = Field(min_length=1)
    last_verified: Optional[date] = None

    crm_status: CRMStatus = CRMStatus.discovered
    shared_context: list[str] = Field(
        default_factory=list,
        description="Checkable common ground: a group, an event, a mutual "
        "contact the user named, a publication both commented on.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Fields a skill looked for and did not find. Recorded so "
        "that a gap is visible rather than silently filled.",
    )
    tags: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @field_validator("profile_url")
    @classmethod
    def _normalise_url(cls, v: Optional[str]) -> Optional[str]:
        return normalise_profile_url(v) if v else v

    @model_validator(mode="after")
    def _identity_consistency(self) -> "Candidate":
        expected = candidate_id_for(self.profile_url, self.name, self.company)
        if self.candidate_id != expected:
            raise ValueError(
                f"candidate_id {self.candidate_id!r} does not match its identity "
                f"basis (expected {expected!r}); build records with "
                f"`Candidate.create` so ids stay derivable"
            )
        if self.profile_url is None and self.identity_basis == "profile_url":
            raise ValueError(
                "identity_basis is 'profile_url' but no profile_url is set"
            )
        if self.confidence is Confidence.none and self.relevance_score is not None:
            raise ValueError(
                "a relevance score with confidence 'none' is a number with no "
                "support; score the candidate or leave the score unset"
            )
        return self

    @classmethod
    def create(cls, *, name: str, sources: list[SourceProvenance],
               profile_url: Optional[str] = None, company: Optional[str] = None,
               **kwargs: Any) -> "Candidate":
        """Build a candidate with a derived id and a correct identity basis."""
        return cls(
            candidate_id=candidate_id_for(profile_url, name, company),
            name=name,
            profile_url=profile_url,
            company=company,
            identity_basis="profile_url" if profile_url else "name_company",
            sources=sources,
            **kwargs,
        )

    @property
    def usable_evidence(self) -> list[Evidence]:
        return [e for e in self.evidence if e.usable]

    @property
    def needs_verification(self) -> bool:
        return self.last_verified is None or all(s.is_stale for s in self.sources)


# ------------------------------------------------------- models 5 and 5b ---


class ComponentScore(_Base):
    """One component of the 100-point framework."""

    component: Literal[
        "icp_relevance", "observable_activity", "engagement_signals",
        "topic_alignment", "professional_influence", "business_opportunity",
    ]
    points: float = Field(ge=0.0)
    max_points: float = Field(gt=0.0)
    confidence: Confidence
    evidence: list[Evidence] = Field(default_factory=list)
    abstained: bool = Field(
        default=False,
        description="True when the inputs this component needs were absent. An "
        "abstaining component scores 0 and says so, instead of scoring a "
        "midpoint and pretending to know.",
    )
    rationale: Optional[str] = Field(default=None, max_length=600)

    @model_validator(mode="after")
    def _within_bounds(self) -> "ComponentScore":
        if self.points > self.max_points:
            raise ValueError(
                f"{self.component}: {self.points} exceeds max {self.max_points}"
            )
        if self.abstained and self.points:
            raise ValueError(f"{self.component}: abstained but scored {self.points}")
        if not self.abstained and self.points > 0 and not self.evidence:
            raise ValueError(
                f"{self.component}: scored {self.points} with no evidence; "
                "every point must be traceable to something observed"
            )
        return self


class CandidateScore(_Base):
    """Model 5. The aggregate score and everything behind it."""

    candidate_id: str = Field(pattern=r"^cand_[0-9a-f]{16}$")
    total: float = Field(ge=0.0, le=100.0)
    max_total: float = Field(default=100.0, gt=0.0)
    components: list[ComponentScore] = Field(min_length=1)
    priority: PriorityClass
    confidence: Confidence
    recommended_next_action: str = Field(min_length=1, max_length=400)
    excluded_by: Optional[str] = Field(
        default=None,
        description="The exclusion criterion that disqualified the candidate, "
        "verbatim from the ICP. Set only when priority is 'excluded'.",
    )
    weights_profile: str = Field(
        default="default",
        description="Which scoring profile produced this, so two scores from "
        "different weightings are never compared as if they were the same.",
    )
    scored_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _consistent(self) -> "CandidateScore":
        seen = [c.component for c in self.components]
        if len(seen) != len(set(seen)):
            raise ValueError("duplicate component in score")
        computed = round(sum(c.points for c in self.components), 4)
        if abs(computed - round(self.total, 4)) > 0.01:
            raise ValueError(
                f"total {self.total} does not equal the sum of components {computed}"
            )
        if self.priority is PriorityClass.excluded and not self.excluded_by:
            raise ValueError("priority 'excluded' requires excluded_by")
        if self.excluded_by and self.priority is not PriorityClass.excluded:
            raise ValueError("excluded_by set on a non-excluded score")
        return self

    @property
    def abstentions(self) -> list[str]:
        return [c.component for c in self.components if c.abstained]


class PropensityAssessment(_Base):
    """Engagement propensity, with observations and predictions kept apart."""

    candidate_id: str = Field(pattern=r"^cand_[0-9a-f]{16}$")
    band: PropensityBand
    raw_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    observations: list[Evidence] = Field(
        default_factory=list,
        description="What was actually seen. May be empty; then the band is "
        "`insufficient_evidence`.",
    )
    predictions: list[str] = Field(
        default_factory=list,
        description="What is expected to follow. Plain strings, never dressed "
        "as evidence, never stored as fact.",
    )
    confidence: Confidence = Confidence.none
    recommended_approach: Optional[str] = Field(default=None, max_length=800)
    assessed_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _honest_band(self) -> "PropensityAssessment":
        usable = [o for o in self.observations if o.usable]
        if not usable and self.band is not PropensityBand.insufficient_evidence:
            raise ValueError(
                f"band {self.band.value!r} claimed with no usable observation; "
                "use 'insufficient_evidence'"
            )
        if not usable and self.confidence is not Confidence.none:
            raise ValueError("confidence above 'none' with no usable observation")
        return self


# ------------------------------------------------------- models 7 and 8 ---


class ConnectionRecommendation(_Base):
    """Model 7. Why to connect, and what to talk about."""

    candidate_id: str = Field(pattern=r"^cand_[0-9a-f]{16}$")
    rationale: str = Field(
        min_length=1, max_length=1000,
        description="A legitimate, specific reason grounded in shared context.",
    )
    shared_context: list[str] = Field(default_factory=list)
    recommended_conversation_topic: Optional[str] = Field(default=None, max_length=400)
    profile_context: list[str] = Field(
        default_factory=list,
        description="The facts about the person a human should read before "
        "reaching out, each traceable to a source.",
    )
    follow_up_approach: Optional[str] = Field(default=None, max_length=800)
    relationship_first: bool = Field(
        default=True,
        description="Always true in generated output. Present so that a "
        "pitch-first recommendation is representable only by deliberately "
        "setting it false, which the skills never do.",
    )
    created_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _needs_real_grounding(self) -> "ConnectionRecommendation":
        if not self.shared_context and not self.profile_context:
            raise ValueError(
                "a recommendation with neither shared context nor profile "
                "context is a generic request; gather context or skip the "
                "candidate"
            )
        return self


class InvitationDraft(_Base):
    """Model 8. A connection note, for a human to send by hand.

    There is no `send` on this model and no sender anywhere in the package.
    """

    candidate_id: str = Field(pattern=r"^cand_[0-9a-f]{16}$")
    variant_label: str = Field(min_length=1, max_length=60)
    body: str = Field(min_length=1)
    char_count: int = Field(ge=1)
    char_limit: int = Field(
        default=300, gt=0,
        description="LinkedIn's connection-note limit at time of writing. "
        "Configurable because platform limits change and a stale constant in "
        "code is worse than a value the user can correct.",
    )
    tone: Optional[str] = Field(default=None, max_length=60)
    includes_pitch: bool = False
    approval_state: Literal["draft", "approved_by_user", "sent_by_user", "discarded"] = "draft"
    created_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _check(self) -> "InvitationDraft":
        if self.char_count != len(self.body):
            raise ValueError(
                f"char_count {self.char_count} does not match body length "
                f"{len(self.body)}"
            )
        if self.char_count > self.char_limit:
            raise ValueError(
                f"invitation is {self.char_count} chars, over the {self.char_limit} "
                f"limit; shorten it rather than letting the user discover the "
                f"truncation in LinkedIn"
            )
        if self.includes_pitch:
            raise ValueError(
                "a first-touch invitation does not carry a pitch; put the offer "
                "in a later conversation"
            )
        return self


# ------------------------------------------------------ models 9 and 10 ---


class StatusChange(_Base):
    """Model 9. A CRM status transition the user confirmed.

    `confirmed_by_user` is mandatory and has no default. A transition that
    represents something happening on LinkedIn cannot be recorded without the
    user saying it happened.
    """

    candidate_id: str = Field(pattern=r"^cand_[0-9a-f]{16}$")
    from_status: Optional[CRMStatus]
    to_status: CRMStatus
    confirmed_by_user: bool
    changed_at: datetime = Field(default_factory=utcnow)
    note: Optional[str] = Field(default=None, max_length=600)

    #: Statuses that assert a LinkedIn-side fact only the user can confirm.
    USER_CONFIRMED_ONLY: ClassVar[frozenset[CRMStatus]] = frozenset(
        {
            CRMStatus.manually_invited,
            CRMStatus.accepted,
            CRMStatus.conversation_started,
            CRMStatus.converted,
        }
    )

    @model_validator(mode="after")
    def _legal(self) -> "StatusChange":
        if self.from_status is not None:
            allowed = LEGAL_TRANSITIONS.get(self.from_status, set())
            if self.to_status not in allowed and self.to_status is not self.from_status:
                raise ValueError(
                    f"illegal transition {self.from_status.value} -> "
                    f"{self.to_status.value}; legal: "
                    f"{sorted(s.value for s in allowed)}"
                )
        if self.to_status in self.USER_CONFIRMED_ONLY and not self.confirmed_by_user:
            raise ValueError(
                f"status {self.to_status.value!r} asserts something that "
                f"happened on LinkedIn; it may only be set from the user's own "
                f"confirmation"
            )
        return self


class RelationshipEvent(_Base):
    """Model 10. One interaction, for history and anti-repetition."""

    candidate_id: str = Field(pattern=r"^cand_[0-9a-f]{16}$")
    occurred_on: date
    channel: TouchChannel
    direction: Literal["outbound", "inbound", "mutual"]
    summary: str = Field(min_length=1, max_length=1000)
    initiated_by_user: bool = True
    substantive: bool = Field(
        default=False,
        description="A real exchange rather than a reaction. Counted in "
        "`meaningful_interactions`; a like is not one.",
    )
    source: Optional[SourceProvenance] = None
    created_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _not_future(self) -> "RelationshipEvent":
        if self.occurred_on > date.today():
            raise ValueError("an interaction cannot be recorded in the future")
        return self


# ------------------------------------------------------------ model 11 ---


class BusinessOpportunity(_Base):
    """Model 11. A commercial hypothesis with named evidence.

    Purchasing intent is never inferred. `stage` starts at `hypothesis`, and
    only the user's own confirmation moves it past `signal_observed`.
    """

    opportunity_id: str = Field(pattern=r"^opp_[0-9a-f]{12}$")
    candidate_id: str = Field(pattern=r"^cand_[0-9a-f]{16}$")
    service_category: str = Field(min_length=1, max_length=80)
    hypothesis: str = Field(
        min_length=1, max_length=1000,
        description="What the user might be able to help with, phrased as a "
        "hypothesis. 'They may be running manual order entry', not 'they need "
        "automation'.",
    )
    stage: OpportunityStage = OpportunityStage.hypothesis
    signals: list[Evidence] = Field(
        default_factory=list,
        description="Observable, public signals. Never an inference about "
        "budget, contracts or internal systems.",
    )
    discovery_questions: list[str] = Field(default_factory=list)
    estimated_relevance: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    confidence: Confidence = Confidence.low
    confirmed_by_user: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @classmethod
    def make_id(cls, candidate_id: str, service_category: str) -> str:
        digest = hashlib.sha256(
            f"{candidate_id}|{service_category.lower()}".encode("utf-8")
        ).hexdigest()[:12]
        return f"opp_{digest}"

    @model_validator(mode="after")
    def _evidence_discipline(self) -> "BusinessOpportunity":
        beyond_hypothesis = self.stage not in (
            OpportunityStage.hypothesis, OpportunityStage.declined
        )
        if beyond_hypothesis and not any(s.usable for s in self.signals):
            raise ValueError(
                f"stage {self.stage.value!r} requires at least one usable "
                f"signal; a hypothesis with no evidence stays at 'hypothesis'"
            )
        if self.stage in (
            OpportunityStage.discussed, OpportunityStage.qualified,
            OpportunityStage.won, OpportunityStage.lost,
        ) and not self.confirmed_by_user:
            raise ValueError(
                f"stage {self.stage.value!r} reports a real conversation; it "
                f"may only be set from the user's confirmation"
            )
        return self


# ------------------------------------------------------------ model 12 ---


class ContentAnalytics(_Base):
    """Model 12. One post's performance, as the user's own export reports it.

    Every metric is optional and `None` means "the export did not carry it".
    Nothing here is ever back-filled with an estimate.
    """

    post_ref: str = Field(
        min_length=1, max_length=300,
        description="The user's own identifier for the post: a URL, an export "
        "row id, or a date plus first words.",
    )
    published_on: Optional[date] = None
    topics: list[str] = Field(default_factory=list)
    format: Optional[str] = None
    impressions: Optional[int] = Field(default=None, ge=0)
    members_reached: Optional[int] = Field(default=None, ge=0)
    reactions: Optional[int] = Field(default=None, ge=0)
    comments: Optional[int] = Field(default=None, ge=0)
    shares: Optional[int] = Field(default=None, ge=0)
    profile_views_attributed: Optional[int] = Field(default=None, ge=0)
    followers_gained: Optional[int] = Field(default=None, ge=0)
    connections_gained: Optional[int] = Field(default=None, ge=0)
    business_outcomes: list[str] = Field(
        default_factory=list,
        description="Outcomes the user confirms, e.g. 'one discovery call "
        "booked'. Kept apart from engagement counts on purpose: a post with "
        "40,000 impressions and no outcome is not a successful post.",
    )
    source: SourceProvenance
    notes: Optional[str] = None

    @property
    def engagement_total(self) -> Optional[int]:
        parts = [v for v in (self.reactions, self.comments, self.shares) if v is not None]
        return sum(parts) if parts else None

    @property
    def engagement_rate(self) -> Optional[float]:
        base = self.impressions if self.impressions else self.members_reached
        total = self.engagement_total
        if not base or total is None:
            return None
        return total / base


# ------------------------------------------------------ models 13 and 14 ---


class FunnelMetrics(_Base):
    """The funnel, with `None` for anything the data cannot support.

    Phase 2: never invent unavailable metrics. Hence `Optional` everywhere and
    `unavailable` carrying the reason.
    """

    profiles_researched: Optional[int] = Field(default=None, ge=0)
    qualified_candidates: Optional[int] = Field(default=None, ge=0)
    candidates_by_icp: dict[str, int] = Field(default_factory=dict)
    invitations_manually_sent: Optional[int] = Field(default=None, ge=0)
    invitations_accepted: Optional[int] = Field(default=None, ge=0)
    acceptance_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    relevant_connections_gained: Optional[int] = Field(default=None, ge=0)
    meaningful_interactions: Optional[int] = Field(default=None, ge=0)
    content_engagement_from_new_connections: Optional[int] = Field(default=None, ge=0)
    profile_visits: Optional[int] = Field(default=None, ge=0)
    followers_gained: Optional[int] = Field(default=None, ge=0)
    qualified_leads: Optional[int] = Field(default=None, ge=0)
    discovery_meetings: Optional[int] = Field(default=None, ge=0)
    business_opportunities: Optional[int] = Field(default=None, ge=0)
    unavailable: dict[str, str] = Field(
        default_factory=dict,
        description="metric name -> why it could not be computed. A reader "
        "should never have to guess whether a blank means zero.",
    )

    @model_validator(mode="after")
    def _rate_is_derived(self) -> "FunnelMetrics":
        sent, accepted = self.invitations_manually_sent, self.invitations_accepted
        if accepted is not None and sent is not None and accepted > sent:
            raise ValueError(
                f"{accepted} acceptances against {sent} invitations sent"
            )
        if self.acceptance_rate is not None and not sent:
            raise ValueError(
                "acceptance_rate with no invitations sent; leave it None and "
                "record the reason in `unavailable`"
            )
        return self


class PeriodReport(_Base):
    """Model 13. A weekly or monthly report."""

    report_id: str = Field(min_length=1, max_length=80)
    period: Literal["weekly", "monthly"]
    period_start: date
    period_end: date
    metrics: FunnelMetrics
    icp_performance: dict[str, FunnelMetrics] = Field(default_factory=dict)
    audience_quality_notes: list[str] = Field(default_factory=list)
    recommended_improvements: list[str] = Field(default_factory=list)
    attribution_limits: list[str] = Field(
        default_factory=list,
        description="What this report cannot attribute, stated plainly. A "
        "required section, not a disclaimer.",
    )
    generated_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _ordered(self) -> "PeriodReport":
        if self.period_end < self.period_start:
            raise ValueError("period_end precedes period_start")
        return self


class AuditEntry(_Base):
    """Model 14. One line of the audit trail.

    Written for every recommendation produced, every approval recorded and
    every refusal issued. Append-only; `lni.audit` offers no update or delete.
    """

    entry_id: Optional[int] = None
    occurred_at: datetime = Field(default_factory=utcnow)
    actor: Literal["agent", "user", "system"]
    action_class: ActionClass
    decision: Literal["allowed", "refused", "requires_approval", "approved", "declined"]
    skill: Optional[str] = Field(default=None, max_length=80)
    subject_id: Optional[str] = Field(
        default=None, max_length=80,
        description="candidate_id, opportunity_id or report_id this concerns.",
    )
    summary: str = Field(min_length=1, max_length=1000)
    rule_cited: Optional[str] = Field(
        default=None, max_length=200,
        description="For a refusal: which rule in safety.yaml was applied.",
    )

    @model_validator(mode="after")
    def _refusal_cites_a_rule(self) -> "AuditEntry":
        if self.decision == "refused" and not self.rule_cited:
            raise ValueError(
                "a refusal must cite the rule it applied, so the user can see "
                "what was refused and why"
            )
        return self
