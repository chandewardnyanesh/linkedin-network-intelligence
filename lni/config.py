"""Configuration loading, merging and validation.

The package ships no personal data. `config/default.yaml` holds behaviour;
`config/profile.yaml` and friends hold the blanks only a user can fill. A skill
that needs a blank calls `missing_for` and asks a question. Nothing in this
module invents a value.

Layer order, lowest precedence first:

    1. config/default.yaml                       (behaviour, no personal data)
    2. config/{profile,audience,icps,
               business_services,scoring,safety}.yaml
    3. every *.yaml in $LNI_CONFIG_DIR, alphabetically
    4. an explicit `overrides` mapping passed to `load_config`

Mappings merge key by key. Lists replace wholesale, except `icps`, which merges
by `key` so a user can redefine one ICP without restating the other seven.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, ClassVar, Iterable, Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import Confidence, ICPDefinition, PriorityClass, SourceKind, UserProfile

__all__ = [
    "Settings", "StorageSettings", "WorkflowSettings", "RelationshipSettings",
    "AudienceSettings", "ReportingSettings", "ProvenanceSettings",
    "PrivacySettings", "OutputSettings", "ScoringSettings", "ScoringProfile",
    "PriorityBand", "SafetySettings", "ProhibitedRule", "ServiceCategory",
    "BusinessServicesSettings", "AudiencePlan", "DesiredAudience",
    "load_config", "missing_for", "SKILL_REQUIREMENTS", "PACKAGE_ROOT",
    "ConfigError",
]

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_DIR = PACKAGE_ROOT / "config"

_SECTION_FILES = (
    "default.yaml",
    "profile.yaml",
    "audience.yaml",
    "icps.yaml",
    "business_services.yaml",
    "scoring.yaml",
    "safety.yaml",
)


class ConfigError(ValueError):
    """Raised when configuration is present but wrong.

    Distinct from configuration being *absent*, which is normal and is reported
    by `missing_for` rather than raised.
    """


# ------------------------------------------------------------- merging ---


def _deep_merge(base: Any, over: Any, *, path: str = "") -> Any:
    """Merge `over` onto `base`. Mappings merge; lists replace; `icps` merges by key."""
    if isinstance(base, dict) and isinstance(over, dict):
        out = dict(base)
        for k, v in over.items():
            sub = f"{path}.{k}" if path else k
            out[k] = _deep_merge(base.get(k), v, path=sub) if k in base else copy.deepcopy(v)
        return out
    if path.endswith("icps") and isinstance(base, list) and isinstance(over, list):
        return _merge_keyed(base, over, "key")
    if path.endswith("categories") and isinstance(base, list) and isinstance(over, list):
        return _merge_keyed(base, over, "key")
    return copy.deepcopy(over)


def _merge_keyed(base: list, over: list, key: str) -> list:
    """Merge two lists of mappings on `key`, preserving base order then appending."""
    index = {}
    out: list = []
    for item in base:
        if isinstance(item, dict) and key in item:
            index[item[key]] = len(out)
        out.append(copy.deepcopy(item))
    for item in over:
        if isinstance(item, dict) and key in item and item[key] in index:
            pos = index[item[key]]
            out[pos] = _deep_merge(out[pos], item)
        else:
            out.append(copy.deepcopy(item))
    return out


def _read_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: YAML does not parse ({str(exc).splitlines()[0]})") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping, got {type(data).__name__}")
    return data


# ------------------------------------------------------------ sections ---


class _Sec(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class StorageSettings(_Sec):
    backend: Literal["sqlite", "postgres"] = "sqlite"
    sqlite_path: str = "./data/network.db"
    postgres_dsn_env: str = "LNI_POSTGRES_DSN"
    data_dir: str = "./data"

    @property
    def postgres_dsn(self) -> Optional[str]:
        """Read from the environment only. A DSN in a file is a DSN in git."""
        return os.getenv(self.postgres_dsn_env) or None

    @model_validator(mode="after")
    def _postgres_needs_dsn(self) -> "StorageSettings":
        if self.backend == "postgres" and not self.postgres_dsn:
            raise ConfigError(
                f"storage.backend is 'postgres' but ${self.postgres_dsn_env} is "
                f"not set; export the DSN or use the sqlite backend"
            )
        return self


class WorkflowSettings(_Sec):
    weekly_research_target: int = Field(default=100, ge=1, le=1000)
    one_time_research_target: int = Field(default=25, ge=1, le=1000)
    shortlist_size: int = Field(default=25, ge=1, le=500)
    reshortlist_cooldown_days: int = Field(default=60, ge=0)
    invitation_capacity_is_the_users_own: bool = True

    @field_validator("invitation_capacity_is_the_users_own")
    @classmethod
    def _not_negotiable(cls, v: bool) -> bool:
        if not v:
            raise ConfigError(
                "workflow.invitation_capacity_is_the_users_own cannot be set "
                "false. The bundle does not model, pace or optimise against "
                "platform limits; see safety.yaml -> no_detection_evasion."
            )
        return v


class RelationshipSettings(_Sec):
    min_days_between_outbound_touches: int = Field(default=21, ge=0)
    follow_up_window_days: tuple[int, int] = (7, 45)
    dormant_after_days: int = Field(default=120, ge=1)
    max_follow_ups_without_reply: int = Field(default=2, ge=0)

    @model_validator(mode="after")
    def _window_ordered(self) -> "RelationshipSettings":
        lo, hi = self.follow_up_window_days
        if lo > hi:
            raise ConfigError(f"follow_up_window_days {lo} > {hi}")
        return self


class AudienceSettings(_Sec):
    min_posts_per_topic: int = Field(default=3, ge=1)
    min_segment_share_for_recommendation: float = Field(default=0.05, ge=0.0, le=1.0)


class ReportingSettings(_Sec):
    default_period: Literal["weekly", "monthly"] = "weekly"
    estimate_missing_metrics: bool = False
    include_attribution_limits: bool = True

    @field_validator("estimate_missing_metrics")
    @classmethod
    def _never_estimate(cls, v: bool) -> bool:
        if v:
            raise ConfigError(
                "reporting.estimate_missing_metrics cannot be enabled. A metric "
                "that cannot be sourced is reported as `unavailable` with the "
                "reason. An estimated metric in a performance report is a "
                "fabricated one."
            )
        return v


class ProvenanceSettings(_Sec):
    stale_after_days: int = Field(default=180, ge=1)
    require_source_on_every_record: bool = True

    @field_validator("require_source_on_every_record")
    @classmethod
    def _required(cls, v: bool) -> bool:
        if not v:
            raise ConfigError(
                "provenance.require_source_on_every_record cannot be set false; "
                "a record with no source cannot be re-checked or corrected"
            )
        return v


class PrivacySettings(_Sec):
    allowed_candidate_fields: list[str] = Field(default_factory=list)
    never_store: list[str] = Field(default_factory=list)
    retain_days: int = Field(default=365, ge=1)
    support_subject_export: bool = True
    support_subject_deletion: bool = True

    @model_validator(mode="after")
    def _rights_are_not_optional(self) -> "PrivacySettings":
        if not (self.support_subject_export and self.support_subject_deletion):
            raise ConfigError(
                "privacy.support_subject_export and support_subject_deletion "
                "cannot be disabled; a store of records about other people must "
                "be able to produce and remove what it holds about one of them"
            )
        return self


class OutputSettings(_Sec):
    separate_observations_from_predictions: bool = True
    show_confidence: bool = True
    show_evidence: bool = True
    max_evidence_shown_per_candidate: int = Field(default=5, ge=1)

    @field_validator("separate_observations_from_predictions")
    @classmethod
    def _always(cls, v: bool) -> bool:
        if not v:
            raise ConfigError(
                "output.separate_observations_from_predictions cannot be set "
                "false; a prediction printed as an observation is the failure "
                "this bundle exists to avoid"
            )
        return v


class ScoringProfile(_Sec):
    description: Optional[str] = None
    weights: dict[str, float]

    @model_validator(mode="after")
    def _components_and_total(self) -> "ScoringProfile":
        from .models import SCORE_COMPONENTS

        unknown = set(self.weights) - set(SCORE_COMPONENTS)
        if unknown:
            raise ConfigError(f"unknown scoring component(s): {sorted(unknown)}")
        missing = set(SCORE_COMPONENTS) - set(self.weights)
        if missing:
            raise ConfigError(f"scoring profile omits component(s): {sorted(missing)}")
        if any(v < 0 for v in self.weights.values()):
            raise ConfigError("scoring weights cannot be negative")
        total = round(sum(self.weights.values()), 6)
        if abs(total - 100.0) > 0.001:
            raise ConfigError(
                f"scoring weights sum to {total}, not 100. The framework is a "
                f"100-point scale; rescale rather than letting totals from two "
                f"profiles look comparable when they are not."
            )
        return self


class PriorityBand(_Sec):
    band_class: PriorityClass = Field(alias="class")
    min_total: float = Field(ge=0.0, le=100.0)
    min_confidence: Confidence = Confidence.none

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class InfluenceSettings(_Sec):
    follower_subscore_cap: float = Field(default=0.3, ge=0.0, le=0.5)
    signals: list[str] = Field(default_factory=list)

    @field_validator("follower_subscore_cap")
    @classmethod
    def _capped(cls, v: float) -> float:
        if v > 0.5:
            raise ConfigError(
                "professional_influence.follower_subscore_cap above 0.5 would "
                "make audience size the dominant influence signal; it is not "
                "one. See CAPABILITY_GAP_ANALYSIS.md section 5."
            )
        return v


class EngagementSignalWeights(_Sec):
    substantive_comment: float = 1.0
    reply_to_user: float = 0.9
    repeat_engagement: float = 0.8
    share_with_commentary: float = 0.7
    short_comment: float = 0.3
    reaction_only: float = 0.1
    recency_window_days: int = Field(default=180, ge=1)

    @model_validator(mode="after")
    def _comment_beats_reaction(self) -> "EngagementSignalWeights":
        if self.reaction_only >= self.substantive_comment:
            raise ConfigError(
                "a reaction cannot be weighted at or above a substantive "
                "comment; a like is not a relationship"
            )
        return self


class ActivitySettings(_Sec):
    recency_window_days: int = Field(default=90, ge=1)
    signals: list[str] = Field(default_factory=list)


class TopicAlignmentSettings(_Sec):
    match_mode: Literal["overlap", "exact"] = "overlap"
    min_overlap_for_points: int = Field(default=1, ge=1)


class ScoringSettings(_Sec):
    active_profile: str = "default"
    profiles: dict[str, ScoringProfile]
    priority_bands: list[PriorityBand]
    max_abstentions_before_low_confidence: int = Field(default=2, ge=0, le=6)
    professional_influence: InfluenceSettings = Field(default_factory=InfluenceSettings)
    engagement_signals: EngagementSignalWeights = Field(default_factory=EngagementSignalWeights)
    observable_activity: ActivitySettings = Field(default_factory=ActivitySettings)
    topic_alignment: TopicAlignmentSettings = Field(default_factory=TopicAlignmentSettings)

    @model_validator(mode="after")
    def _coherent(self) -> "ScoringSettings":
        if self.active_profile not in self.profiles:
            raise ConfigError(
                f"scoring.active_profile {self.active_profile!r} is not among "
                f"{sorted(self.profiles)}"
            )
        if not self.priority_bands:
            raise ConfigError("scoring.priority_bands is empty")
        totals = [b.min_total for b in self.priority_bands]
        if totals != sorted(totals, reverse=True):
            raise ConfigError(
                "scoring.priority_bands must be ordered from highest min_total "
                "down; they are evaluated top to bottom and the first match wins"
            )
        if totals[-1] != 0.0:
            raise ConfigError(
                "the lowest priority band must have min_total 0 so every scored "
                "candidate lands in exactly one band"
            )
        return self

    @property
    def active_weights(self) -> dict[str, float]:
        return dict(self.profiles[self.active_profile].weights)


class ProhibitedRule(_Sec):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,60}$")
    rule: str = Field(min_length=1)
    detail: Optional[str] = None


class PlatformTerms(_Sec):
    agreement: str
    user_must_review: bool = True


class PlatformRestrictionPolicy(_Sec):
    on_warning_or_restriction: Literal["stop_and_alert"] = "stop_and_alert"
    detail: Optional[str] = None
    resume_requires_user_statement: bool = True

    @field_validator("on_warning_or_restriction")
    @classmethod
    def _only_stop(cls, v: str) -> str:
        if v != "stop_and_alert":
            raise ConfigError(
                "safety.platform_restrictions.on_warning_or_restriction has one "
                "legal value, 'stop_and_alert'. Anything else is a workaround."
            )
        return v


class AuditSettings(_Sec):
    enabled: bool = True
    log_recommendations: bool = True
    log_approvals: bool = True
    log_refusals: bool = True
    log_imports_and_exports: bool = True
    retain_days: int = Field(default=730, ge=1)

    @model_validator(mode="after")
    def _refusals_always_logged(self) -> "AuditSettings":
        if not self.enabled or not self.log_refusals:
            raise ConfigError(
                "safety.audit must stay enabled with log_refusals true; an "
                "unrecorded refusal cannot be reviewed, and turning the record "
                "off is the first step of working around the rule"
            )
        return self


class DataProtectionSettings(_Sec):
    minimise_collection: bool = True
    purpose_limitation: Optional[str] = None
    subject_export: bool = True
    subject_deletion: bool = True
    review_untouched_after_days: int = Field(default=365, ge=1)


class SafetySettings(_Sec):
    platform_terms: PlatformTerms
    prohibited: list[ProhibitedRule]
    requires_human_approval: list[str] = Field(default_factory=list)
    authorised_sources: list[SourceKind] = Field(default_factory=list)
    platform_restrictions: PlatformRestrictionPolicy
    audit: AuditSettings = Field(default_factory=AuditSettings)
    data_protection: DataProtectionSettings = Field(default_factory=DataProtectionSettings)

    #: Rule ids that must be present. Removing one from safety.yaml is itself
    #: a configuration error rather than a permitted local relaxation.
    REQUIRED_RULE_IDS: ClassVar[tuple[str, ...]] = (
        "no_automated_invitations", "no_automated_messaging", "no_scraping",
        "no_browser_automation", "no_captcha_bypass", "no_detection_evasion",
        "no_engagement_manipulation", "no_unauthorised_api", "no_private_data",
        "no_fabrication", "no_targeting_private_individuals",
    )

    @model_validator(mode="after")
    def _complete(self) -> "SafetySettings":
        ids = {r.id for r in self.prohibited}
        if len(ids) != len(self.prohibited):
            raise ConfigError("duplicate rule id in safety.prohibited")
        missing = [r for r in self.REQUIRED_RULE_IDS if r not in ids]
        if missing:
            raise ConfigError(
                f"safety.prohibited is missing required rule(s): {missing}. "
                f"These are not local preferences; a configuration that drops "
                f"one does not load."
            )
        return self

    def rule(self, rule_id: str) -> ProhibitedRule:
        for r in self.prohibited:
            if r.id == rule_id:
                return r
        raise KeyError(rule_id)


class ServiceCategory(_Sec):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,48}$")
    label: str = Field(min_length=1)
    description: Optional[str] = None
    observable_signals: list[str] = Field(default_factory=list)
    disqualifiers: list[str] = Field(default_factory=list)
    discovery_questions: list[str] = Field(default_factory=list)

    @property
    def is_usable(self) -> bool:
        """A category with no observable signals cannot classify anything."""
        return bool(self.observable_signals)


class BusinessServicesSettings(_Sec):
    categories: list[ServiceCategory] = Field(default_factory=list)
    max_confidence_without_user_confirmation: Confidence = Confidence.medium

    @field_validator("max_confidence_without_user_confirmation")
    @classmethod
    def _never_high(cls, v: Confidence) -> Confidence:
        if v is Confidence.high:
            raise ConfigError(
                "business_services.max_confidence_without_user_confirmation "
                "cannot be 'high'. High confidence in purchasing intent without "
                "the user confirming a conversation is a fabricated claim."
            )
        return v


class DesiredAudience(_Sec):
    icp_key: str
    target_share: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    why: Optional[str] = None


class UnwantedAudience(_Sec):
    label: str
    why: Optional[str] = None


class AudienceExport(_Sec):
    path: str
    kind: SourceKind = SourceKind.linkedin_analytics_export
    covers: Optional[str] = None


class AudiencePlan(_Sec):
    current_segments: list[dict] = Field(default_factory=list)
    desired_audience: list[DesiredAudience] = Field(default_factory=list)
    unwanted_audience: list[UnwantedAudience] = Field(default_factory=list)
    exports: list[AudienceExport] = Field(default_factory=list)


# ------------------------------------------------------------ settings ---


class Settings(_Sec):
    """The whole validated configuration."""

    version: int = 1
    storage: StorageSettings = Field(default_factory=StorageSettings)
    workflow: WorkflowSettings = Field(default_factory=WorkflowSettings)
    relationships: RelationshipSettings = Field(default_factory=RelationshipSettings)
    audience: AudienceSettings = Field(default_factory=AudienceSettings)
    reporting: ReportingSettings = Field(default_factory=ReportingSettings)
    provenance: ProvenanceSettings = Field(default_factory=ProvenanceSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
    output: OutputSettings = Field(default_factory=OutputSettings)

    profile: UserProfile = Field(default_factory=UserProfile)
    icps: list[ICPDefinition] = Field(default_factory=list)
    audience_plan: AudiencePlan = Field(default_factory=AudiencePlan)
    business_services: BusinessServicesSettings = Field(
        default_factory=BusinessServicesSettings
    )
    scoring: ScoringSettings
    safety: SafetySettings

    #: Where the layers came from, for diagnosis.
    loaded_from: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _cross_section(self) -> "Settings":
        keys = [i.key for i in self.icps]
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            raise ConfigError(f"duplicate ICP key(s): {sorted(dupes)}")
        for d in self.audience_plan.desired_audience:
            if d.icp_key not in keys:
                raise ConfigError(
                    f"audience.desired_audience references unknown ICP "
                    f"{d.icp_key!r}; defined: {sorted(keys)}"
                )
        shares = [d.target_share for d in self.audience_plan.desired_audience
                  if d.target_share is not None]
        if shares and sum(shares) > 1.0001:
            raise ConfigError(
                f"audience.desired_audience target shares sum to {sum(shares):.2f}"
            )
        if self.profile.weekly_research_target != self.workflow.weekly_research_target:
            # profile.yaml is the user's voice; let it win and keep them in step.
            self.workflow.weekly_research_target = self.profile.weekly_research_target
        return self

    @property
    def active_icps(self) -> list[ICPDefinition]:
        return [i for i in self.icps if i.active]

    @property
    def usable_service_categories(self) -> list[ServiceCategory]:
        return [c for c in self.business_services.categories if c.is_usable]

    def icp(self, key: str) -> ICPDefinition:
        for i in self.icps:
            if i.key == key:
                return i
        raise KeyError(key)


# ------------------------------------------------------------- loading ---


def _config_layers(config_dir: Optional[Path]) -> list[Path]:
    base = config_dir or DEFAULT_CONFIG_DIR
    layers = [base / name for name in _SECTION_FILES]
    env_dir = os.getenv("LNI_CONFIG_DIR")
    if env_dir:
        extra = Path(env_dir).expanduser()
        if extra.is_dir():
            layers.extend(sorted(extra.glob("*.yaml")))
    return layers


def _flatten(raw: dict) -> dict:
    """Lift the per-file top-level keys into the `Settings` shape."""
    out = dict(raw)
    # profile.yaml and audience.yaml nest under their own key.
    if isinstance(out.get("profile"), dict):
        pass  # already the right shape for Settings.profile
    audience = out.get("audience")
    if isinstance(audience, dict) and any(
        k in audience for k in ("current_segments", "desired_audience",
                                "unwanted_audience", "exports")
    ):
        plan = {k: audience.pop(k) for k in
                ("current_segments", "desired_audience", "unwanted_audience", "exports")
                if k in audience}
        out["audience_plan"] = _deep_merge(out.get("audience_plan", {}), plan)
        if not audience:
            out.pop("audience")
    return out


def load_config(
    config_dir: Optional[Path | str] = None,
    overrides: Optional[dict] = None,
    *,
    extra_files: Optional[Iterable[Path | str]] = None,
) -> Settings:
    """Load, merge and validate the configuration.

    Raises `ConfigError` when configuration is present and wrong. Absent
    personal configuration is not an error: use `missing_for` to find out what
    a skill still needs, and ask the user for it.
    """
    merged: dict = {}
    seen: list[str] = []
    layers = _config_layers(Path(config_dir) if config_dir else None)
    if extra_files:
        layers.extend(Path(p) for p in extra_files)
    for path in layers:
        data = _read_yaml(path)
        if data:
            merged = _deep_merge(merged, data)
            seen.append(str(path))
    if overrides:
        merged = _deep_merge(merged, overrides)
        seen.append("<overrides>")
    merged = _flatten(merged)
    merged["loaded_from"] = seen
    try:
        return Settings.model_validate(merged)
    except ConfigError:
        raise
    except Exception as exc:  # pydantic ValidationError and friends
        raise ConfigError(f"configuration does not validate:\n{exc}") from exc


# ------------------------------------------- what a skill still needs ---

#: Config paths each skill needs before it can do its job properly. A path
#: here that resolves to None, an empty list or an empty string is something
#: the skill must ASK for. It is never filled with a guess.
SKILL_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "linkedin-audience-intelligence": (
        "profile.content_topics", "audience_plan.exports",
        "audience_plan.desired_audience",
    ),
    "linkedin-icp-builder": ("profile.primary_objective",),
    "linkedin-network-discovery": ("icps.active", "profile.primary_objective"),
    "linkedin-engagement-propensity": ("profile.content_topics", "icps.signals"),
    "linkedin-network-scoring": ("icps.active",),
    "linkedin-connection-strategy": ("profile.display_name", "profile.primary_objective"),
    "linkedin-network-crm": (),
    "linkedin-lead-intelligence": (
        "business_services.categories", "profile.services_offered",
    ),
    "linkedin-content-audience-attribution": (
        "audience_plan.exports", "profile.content_topics",
    ),
    "linkedin-relationship-manager": (),
    "linkedin-network-growth-analyst": ("icps.active",),
    "linkedin-policy-safety-governor": (),
    "linkedin-network-growth": (
        "profile.primary_objective", "icps.active",
    ),
}

#: Plain-language question for each requirement, so a skill asks the same way
#: every time instead of improvising.
_QUESTIONS: dict[str, str] = {
    "profile.display_name": "What name should invitation drafts be written in?",
    "profile.primary_objective": (
        "What is the networking for? One sentence — it decides which ICPs "
        "matter and what a good candidate looks like."
    ),
    "profile.content_topics": (
        "Which topics do you actually publish about? Without them the "
        "topic-alignment component of the score abstains."
    ),
    "profile.services_offered": (
        "What do you offer, if anything? Leave it empty if the networking is "
        "not commercial — lead intelligence will then correctly report nothing."
    ),
    "icps.active": (
        "No ICP is both active and specific yet. Which audience are we looking "
        "for? `linkedin-icp-builder` turns an answer into a definition."
    ),
    "icps.signals": (
        "Your active ICPs have no observable engagement signals. What does "
        "someone in this audience visibly do? Without signals the engagement "
        "components abstain."
    ),
    "business_services.categories": (
        "Which service categories should a lead be classified against? Each "
        "needs observable signals, or it cannot classify anything."
    ),
    "audience_plan.exports": (
        "Do you have a LinkedIn analytics or post export to work from? Export "
        "it from your own analytics page and give me the path."
    ),
    "audience_plan.desired_audience": (
        "Which audience do you want more of? The gap between that and your "
        "current audience is the whole output."
    ),
}


def _resolve(settings: Settings, path: str) -> Any:
    if path == "icps.active":
        return [i for i in settings.icps if i.active and i.is_falsifiable] or None
    if path == "icps.signals":
        return [i for i in settings.active_icps if i.observable_engagement_signals] or None
    if path == "business_services.categories":
        return settings.usable_service_categories or None
    node: Any = settings
    for part in path.split("."):
        node = getattr(node, part, None)
        if node is None:
            return None
    if isinstance(node, (list, dict, str)) and not node:
        return None
    return node


def missing_for(settings: Settings, skill: str) -> list[tuple[str, str]]:
    """What `skill` still needs, as (config path, question to ask) pairs.

    Empty means the skill can run. Non-empty means it should ask, in the order
    returned, rather than proceeding on an assumption.
    """
    if skill not in SKILL_REQUIREMENTS:
        raise KeyError(f"unknown skill {skill!r}; known: {sorted(SKILL_REQUIREMENTS)}")
    out: list[tuple[str, str]] = []
    for path in SKILL_REQUIREMENTS[skill]:
        if _resolve(settings, path) is None:
            out.append((path, _QUESTIONS.get(path, f"Please provide {path}.")))
    return out
