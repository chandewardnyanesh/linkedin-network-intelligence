"""Do the documents and the code agree?

The bundle is mostly instructions an agent follows. Nothing else checks that a
skill citing `python -m lni score` is citing a command that exists, or that a
rule id quoted in prose is a rule the configuration actually loads. This does.

The convention is adopted from `tests/test_instruction_integrity.py` in
`sergebulaev/linkedin-skills` (MIT): handoff contracts must hold on both sides.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIRS = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())
SKILL_DOCS = sorted((ROOT / "skills").glob("*/SKILL.md"))
ROOT_DOC = ROOT / "SKILL.md"
ALL_DOCS = SKILL_DOCS + [ROOT_DOC]
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)

OWN_SKILLS = {p.parent.name for p in SKILL_DOCS}
#: Skills in the two upstream bundles. A document may reference these, but they
#: are not expected to exist here.
UPSTREAM_SKILLS = {
    "linkedin-post-writer", "linkedin-comment-drafter", "linkedin-reply-handler",
    "linkedin-humanizer", "linkedin-hook-extractor", "linkedin-content-planner",
    "linkedin-thread-monitor", "linkedin-engager-analytics",
    "linkedin-profile-optimizer", "linkedin-employee-advocacy",
    "linkedin-repurposer", "linkedin-interviewer", "linkedin-marketing",
    "page-profile-builder", "page-optimizer", "page-post-writer",
    "authority-article-writer", "page-content-calendar", "page-humanizer",
    "page-repurposer", "page-engagement-desk", "employee-amplification",
    "competitor-page-analyzer", "trend-radar", "page-performance-report",
    "page-asset-extractor",
}


def frontmatter(path: Path) -> dict:
    m = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    assert m, f"{path}: no frontmatter"
    return yaml.safe_load(m.group(1))


# ----------------------------------------------------- frontmatter ---

@pytest.mark.parametrize("path", ALL_DOCS, ids=lambda p: p.parent.name)
def test_frontmatter_parses_strictly(path):
    data = frontmatter(path)
    assert isinstance(data, dict)
    for key in ("name", "description"):
        assert isinstance(data.get(key), str) and data[key].strip(), key


@pytest.mark.parametrize("path", SKILL_DOCS, ids=lambda p: p.parent.name)
def test_name_matches_the_folder(path):
    assert frontmatter(path)["name"] == path.parent.name


@pytest.mark.parametrize("path", ALL_DOCS, ids=lambda p: p.parent.name)
def test_description_is_a_usable_trigger(path):
    d = frontmatter(path)["description"]
    assert 120 <= len(d) <= 1024, f"{len(d)} chars"
    assert "Use when" in d or "Use this" in d, "a description must say when to use it"


@pytest.mark.parametrize("path", SKILL_DOCS, ids=lambda p: p.parent.name)
def test_license_and_metadata_present(path):
    data = frontmatter(path)
    assert data.get("license") == "MIT"
    assert data.get("metadata", {}).get("bundle") == "linkedin-network-intelligence"


def test_the_manifest_promises_the_right_number_of_skills():
    import json

    manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    promised = int(re.match(r"\s*(\d+)", manifest["description"]).group(1))
    assert promised == len(SKILL_DOCS), (
        f"the manifest promises {promised} skills, {len(SKILL_DOCS)} exist")


# -------------------------------------------- required sections ---

REQUIRED_HEADINGS = ("When to use", "Output format", "Failure handling",
                     "Safety requirements", "Examples")


@pytest.mark.parametrize("path", SKILL_DOCS, ids=lambda p: p.parent.name)
def test_every_skill_documents_the_required_sections(path):
    text = path.read_text(encoding="utf-8")
    for heading in REQUIRED_HEADINGS:
        assert re.search(rf"^#+ .*{re.escape(heading)}", text, re.M | re.I), heading


@pytest.mark.parametrize("path", SKILL_DOCS, ids=lambda p: p.parent.name)
def test_every_skill_states_its_inputs(path):
    text = path.read_text(encoding="utf-8")
    assert re.search(r"^#+ .*(Required inputs|Input)", text, re.M | re.I)


@pytest.mark.parametrize("path", SKILL_DOCS, ids=lambda p: p.parent.name)
def test_every_skill_has_a_workflow_or_is_the_governor(path):
    text = path.read_text(encoding="utf-8")
    assert re.search(r"^#+ .*(Workflow|The twelve-step)", text, re.M | re.I)


# ------------------------------------------------ cross references ---

SKILL_REF = re.compile(r"`(linkedin-[a-z0-9-]+|page-[a-z0-9-]+|trend-radar|"
                       r"authority-article-writer|employee-amplification)`")


@pytest.mark.parametrize("path", ALL_DOCS, ids=lambda p: p.parent.name)
def test_referenced_skills_exist_here_or_upstream(path):
    text = path.read_text(encoding="utf-8")
    for name in set(SKILL_REF.findall(text)):
        assert name in OWN_SKILLS | UPSTREAM_SKILLS | {"linkedin-network-growth"}, (
            f"{path.parent.name} references unknown skill {name!r}")


RULE_REF = re.compile(r"`(no_[a-z_]+)`")


@pytest.mark.parametrize("path", ALL_DOCS, ids=lambda p: p.parent.name)
def test_every_cited_rule_id_is_a_loaded_rule(path, settings):
    ids = {r.id for r in settings.safety.prohibited}
    for cited in set(RULE_REF.findall(path.read_text(encoding="utf-8"))):
        assert cited in ids, f"{path.parent.name} cites unknown rule {cited!r}"


def test_every_loaded_rule_is_documented_somewhere(settings):
    corpus = "\n".join(p.read_text(encoding="utf-8") for p in ALL_DOCS)
    corpus += (ROOT / "references/precedence.md").read_text(encoding="utf-8")
    for rule in settings.safety.prohibited:
        assert rule.id in corpus, f"rule {rule.id!r} is enforced but never documented"


CLI_REF = re.compile(r"python -m lni ([a-z][a-z-]+)")


@pytest.mark.parametrize("path", ALL_DOCS, ids=lambda p: p.parent.name)
def test_every_cited_cli_command_exists(path):
    from lni.cli import build_parser

    parser = build_parser()
    known = set()
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices:
            known.update(k for k in action.choices if isinstance(k, str))
    for cited in set(CLI_REF.findall(path.read_text(encoding="utf-8"))):
        assert cited in known, f"{path.parent.name} cites unknown command {cited!r}"


MODULE_REF = re.compile(r"`lni/([a-z_]+)\.py`")
CONFIG_REF = re.compile(r"`config/([a-z_]+\.yaml)`")
DOC_REF = re.compile(r"`(docs/[A-Z_]+\.md|references/[a-z-]+\.md|ATTRIBUTION\.md)`")


@pytest.mark.parametrize("path", ALL_DOCS, ids=lambda p: p.parent.name)
def test_cited_files_exist(path):
    text = path.read_text(encoding="utf-8")
    for module in set(MODULE_REF.findall(text)):
        assert (ROOT / "lni" / f"{module}.py").is_file(), module
    for cfg in set(CONFIG_REF.findall(text)):
        assert (ROOT / "config" / cfg).is_file(), cfg
    for doc in set(DOC_REF.findall(text)):
        assert (ROOT / doc).is_file(), doc


def test_the_root_document_routes_to_every_skill():
    text = ROOT_DOC.read_text(encoding="utf-8")
    for name in OWN_SKILLS:
        assert name in text, f"the root document does not route to {name}"


# ------------------------------------------------ handoff contracts ---

def test_scoring_delegates_propensity_rather_than_duplicating_it():
    """Both sides must say so, and the code must actually do it."""
    scoring = (ROOT / "skills/linkedin-network-scoring/SKILL.md").read_text()
    propensity = (ROOT / "skills/linkedin-engagement-propensity/SKILL.md").read_text()
    assert "linkedin-engagement-propensity" in scoring
    assert "linkedin-network-scoring" in propensity
    code = (ROOT / "lni/scoring.py").read_text()
    assert "from .propensity import" in code
    assert "one engine" in scoring.lower() or "one engine" in propensity.lower()


def test_connection_strategy_and_relationship_manager_split_the_timeline():
    strategy = (ROOT / "skills/linkedin-connection-strategy/SKILL.md").read_text()
    manager = (ROOT / "skills/linkedin-relationship-manager/SKILL.md").read_text()
    assert "linkedin-relationship-manager" in strategy
    assert "linkedin-connection-strategy" in manager
    assert "first touch" in manager.lower()


def test_thread_level_work_is_routed_upstream_not_reimplemented():
    manager = (ROOT / "skills/linkedin-relationship-manager/SKILL.md").read_text()
    assert "linkedin-thread-monitor" in manager
    assert "reimplement" in manager.lower() or "rather than" in manager.lower()


def test_every_skill_that_writes_records_names_the_crm():
    for name in ("linkedin-network-discovery", "linkedin-lead-intelligence",
                 "linkedin-connection-strategy", "linkedin-relationship-manager",
                 "linkedin-network-growth-analyst"):
        text = (ROOT / "skills" / name / "SKILL.md").read_text()
        assert "linkedin-network-crm" in text, name


# --------------------------------------------- no personal data ships ---

PERSONAL_PATTERNS = [
    r"cybercore", r"nagpur", r"@cybercore\.in", r"dnyanesh@",
]
#: Files where the author's name is expected and correct.
AUTHORSHIP_ALLOWED = {"LICENSE", "ATTRIBUTION.md", "CHANGELOG.md", "README.md",
                      "plugin.json", "SECURITY.md", "CONTRIBUTING.md"}


#: Files that state the forbidden patterns in order to search for them, and so
#: would match themselves. This file and `scripts/check_no_secrets.py` run the
#: same scan from both sides, so each excludes the other. Anything added here
#: must be a scanner, not content.
SELF = Path(__file__).resolve()
PATTERN_DEFINING_FILES = {"scripts/check_no_secrets.py"}


def _package_files():
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.resolve() == SELF:
            continue
        if p.relative_to(ROOT).as_posix() in PATTERN_DEFINING_FILES:
            continue
        rel = p.relative_to(ROOT)
        if rel.parts[0] in {".git", "data", "__pycache__", ".pytest_cache"}:
            continue
        if p.suffix in {".db", ".pyc"}:
            continue
        yield p


@pytest.mark.parametrize("pattern", PERSONAL_PATTERNS)
def test_no_personal_or_business_data_ships_in_the_package(pattern):
    rx = re.compile(pattern, re.I)
    offenders = []
    for p in _package_files():
        if rx.search(p.read_text(encoding="utf-8", errors="replace")):
            offenders.append(str(p.relative_to(ROOT)))
    assert not offenders, f"{pattern!r} appears in {offenders}"


def test_the_shipped_configuration_has_no_filled_personal_fields():
    profile = yaml.safe_load((ROOT / "config/profile.yaml").read_text())["profile"]
    for key in ("display_name", "primary_objective", "profile_url", "headline",
                "industry", "geography", "notes"):
        assert profile[key] is None, f"config/profile.yaml ships a value for {key}"
    for key in ("secondary_objectives", "languages", "content_topics",
                "services_offered"):
        assert profile[key] == [], f"config/profile.yaml ships entries in {key}"


def test_no_api_credentials_anywhere():
    secretish = re.compile(
        r"(sk_live|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
        r"api[_-]?key\s*[:=]\s*[\"'][A-Za-z0-9]{16,}|li_at\s*=\s*[A-Za-z0-9])",
        re.I)
    offenders = [str(p.relative_to(ROOT)) for p in _package_files()
                 if secretish.search(p.read_text(encoding="utf-8", errors="replace"))]
    assert not offenders, offenders


def test_no_linkedin_affiliation_is_claimed():
    corpus = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                       for p in _package_files() if p.suffix == ".md")
    # Narrow on purpose: "official LinkedIn API" is a correct phrase and
    # appears in the data-source rules. What must never appear is a claim of
    # affiliation, endorsement or partnership.
    for claim in ("official LinkedIn partner", "endorsed by LinkedIn",
                  "in partnership with LinkedIn", "LinkedIn-approved",
                  "LinkedIn partner program member", "authorised by LinkedIn",
                  "a LinkedIn product"):
        assert claim.lower() not in corpus.lower(), claim
    root_text = ROOT_DOC.read_text(encoding="utf-8")
    assert "Not affiliated" in root_text


def test_no_scraper_or_sender_ships_in_the_code():
    """The absence of these is the bundle's main promise, so it is tested."""
    forbidden = re.compile(
        r"\b(playwright|selenium|puppeteer|webdriver|requests\.post|urllib\.request\.urlopen)\b")
    offenders = []
    for p in (ROOT / "lni").glob("*.py"):
        text = p.read_text(encoding="utf-8")
        # The safety module names these in refusal patterns, which is the point.
        if p.name == "safety.py":
            continue
        if forbidden.search(text):
            offenders.append(p.name)
    assert not offenders, f"network/automation calls in {offenders}"


def test_the_package_imports_no_http_client():
    import_rx = re.compile(r"^\s*(?:import|from)\s+(requests|httpx|aiohttp|urllib3)\b",
                           re.M)
    offenders = [p.name for p in (ROOT / "lni").glob("*.py")
                 if import_rx.search(p.read_text(encoding="utf-8"))]
    assert not offenders, f"HTTP client imported in {offenders}"
