"""Configuration: layering, validation, and what a skill still needs."""

from __future__ import annotations

from pathlib import Path

import pytest

from lni.config import (
    ConfigError, PACKAGE_ROOT, SKILL_REQUIREMENTS, load_config, missing_for,
)

EXAMPLES = sorted((PACKAGE_ROOT / "config/examples").glob("*.yaml"))


def test_ships_with_no_personal_data(settings):
    """The package must be installable by anyone with nothing of mine in it."""
    p = settings.profile
    assert p.display_name is None
    assert p.primary_objective is None
    assert p.profile_url is None
    assert p.content_topics == []
    assert p.services_offered == []
    assert settings.usable_service_categories == []


def test_works_with_no_personal_configuration(settings):
    """Sensible defaults: one usable ICP, a valid weighting, the full safety layer."""
    assert len(settings.active_icps) >= 1
    assert sum(settings.scoring.active_weights.values()) == pytest.approx(100.0)
    assert len(settings.safety.prohibited) == 11


def test_layer_order_puts_later_files_on_top():
    s = load_config(overrides={"workflow": {"shortlist_size": 7}})
    assert s.workflow.shortlist_size == 7


def test_icps_merge_by_key_rather_than_replacing_the_list(b2b_settings, settings):
    """A user overriding one ICP keeps the other templates."""
    assert len(b2b_settings.icps) >= len(settings.icps)
    keys = [i.key for i in b2b_settings.icps]
    assert "business_development" in keys and "personal_brand_growth" in keys
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.stem)
def test_every_example_configuration_loads(path):
    s = load_config(extra_files=[path])
    assert s.active_icps, f"{path.name} activates no ICP"
    assert sum(s.scoring.active_weights.values()) == pytest.approx(100.0)


def test_example_configurations_cover_the_promised_three():
    stems = {p.stem for p in EXAMPLES}
    assert {"personal-brand", "b2b-sales", "technology-professional"} <= stems


def test_non_commercial_example_yields_no_service_categories():
    s = load_config(extra_files=[PACKAGE_ROOT / "config/examples/technology-professional.yaml"])
    assert s.usable_service_categories == []
    assert s.scoring.active_weights["business_opportunity"] == 0


def test_b2b_example_weights_opportunity_heavily(b2b_settings):
    w = b2b_settings.scoring.active_weights
    assert w["business_opportunity"] == 30
    assert w["professional_influence"] <= 5


# ----------------------------------------------------------- validation ---

def test_weights_must_sum_to_one_hundred():
    bad = {"icp_relevance": 50, "observable_activity": 15, "engagement_signals": 20,
           "topic_alignment": 15, "professional_influence": 10,
           "business_opportunity": 15}
    with pytest.raises(ConfigError, match="sum to"):
        load_config(overrides={"scoring": {"profiles": {"default": {"weights": bad}}}})


def test_unknown_scoring_component_is_rejected():
    bad = {"vibes": 100}
    with pytest.raises(ConfigError, match="unknown scoring component|omits component"):
        load_config(overrides={"scoring": {"profiles": {"default": {"weights": bad}}}})


def test_priority_bands_must_descend_and_reach_zero():
    with pytest.raises(ConfigError, match="ordered from highest"):
        load_config(overrides={"scoring": {"priority_bands": [
            {"class": "priority_3", "min_total": 40},
            {"class": "priority_1", "min_total": 70},
            {"class": "monitor", "min_total": 0},
        ]}})
    with pytest.raises(ConfigError, match="min_total 0"):
        load_config(overrides={"scoring": {"priority_bands": [
            {"class": "priority_1", "min_total": 70},
            {"class": "monitor", "min_total": 10},
        ]}})


def test_a_reaction_cannot_outweigh_a_substantive_comment():
    with pytest.raises(ConfigError, match="not a relationship"):
        load_config(overrides={"scoring": {"engagement_signals": {
            "reaction_only": 1.0, "substantive_comment": 1.0}}})


def test_desired_audience_must_reference_a_defined_icp():
    with pytest.raises(ConfigError, match="unknown ICP"):
        load_config(overrides={"audience": {"desired_audience": [
            {"icp_key": "not_a_real_icp", "target_share": 0.5}]}})


def test_target_shares_cannot_exceed_the_whole_audience():
    with pytest.raises(ConfigError, match="target shares sum"):
        load_config(overrides={"audience": {"desired_audience": [
            {"icp_key": "professional_networking", "target_share": 0.8},
            {"icp_key": "personal_brand_growth", "target_share": 0.5}]}})


def test_duplicate_icp_keys_are_rejected():
    dupe = [
        {"key": "dupe_icp", "label": "A", "purpose": "professional_networking",
         "job_titles": ["x"]},
        {"key": "dupe_icp", "label": "B", "purpose": "professional_networking",
         "job_titles": ["y"]},
    ]
    with pytest.raises(ConfigError):
        load_config(overrides={"icps": dupe})


def test_postgres_backend_without_a_dsn_is_refused(monkeypatch):
    monkeypatch.delenv("LNI_POSTGRES_DSN", raising=False)
    with pytest.raises(ConfigError, match="postgres"):
        load_config(overrides={"storage": {"backend": "postgres"}})


def test_malformed_yaml_names_the_file(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("profile:\n  name: [unclosed\n")
    with pytest.raises(ConfigError, match="bad.yaml"):
        load_config(extra_files=[bad])


def test_a_top_level_list_is_rejected(tmp_path):
    bad = tmp_path / "list.yaml"
    bad.write_text("- one\n- two\n")
    with pytest.raises(ConfigError, match="must be a mapping"):
        load_config(extra_files=[bad])


# ------------------------------------------------- what a skill needs ---

def test_every_skill_directory_has_a_requirements_entry():
    skills = {p.parent.name for p in (PACKAGE_ROOT / "skills").glob("*/SKILL.md")}
    declared = set(SKILL_REQUIREMENTS) - {"linkedin-network-growth"}
    assert skills == declared, f"mismatch: {skills ^ declared}"


def test_missing_for_asks_rather_than_assuming(settings):
    gaps = missing_for(settings, "linkedin-network-discovery")
    paths = [p for p, _ in gaps]
    assert "profile.primary_objective" in paths
    for _path, question in gaps:
        assert question.strip().endswith("?") or len(question) > 30, question


def test_a_fully_configured_setup_blocks_nothing_essential(b2b_settings):
    for skill in ("linkedin-network-discovery", "linkedin-network-scoring",
                  "linkedin-lead-intelligence", "linkedin-connection-strategy"):
        assert missing_for(b2b_settings, skill) == [], skill


def test_unknown_skill_name_raises(settings):
    with pytest.raises(KeyError):
        missing_for(settings, "linkedin-not-a-skill")


def test_profile_research_target_wins_over_workflow_default():
    s = load_config(overrides={"profile": {"weekly_research_target": 40}})
    assert s.workflow.weekly_research_target == 40
