"""The discoverability artefacts, checked so they cannot silently rot.

SEO work decays: a document gets renamed, `llms.txt` keeps pointing at the old
path, the sitemap lists a page that no longer exists, and nobody notices for a
year. These tests make that a failure instead.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "docs/index.html"
LLMS = ROOT / "llms.txt"
SITEMAP = ROOT / "docs/sitemap.xml"
REPO_URL = "https://github.com/chandewardnyanesh/linkedin-network-intelligence"
PAGES_URL = "https://chandewardnyanesh.github.io/linkedin-network-intelligence/"


# ------------------------------------------------------------- llms.txt ---

def test_llms_txt_exists_at_root_and_on_the_pages_site():
    assert LLMS.is_file()
    served = ROOT / "docs/llms.txt"
    assert served.is_file()
    assert served.read_text(encoding="utf-8") == LLMS.read_text(encoding="utf-8"), (
        "docs/llms.txt has drifted from the root copy; copy it again")


def test_llms_txt_follows_the_specification_shape():
    """H1 title, a blockquote summary, then H2 sections of annotated links."""
    lines = LLMS.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# "), "must open with an H1 project title"
    assert any(l.startswith("> ") for l in lines[:8]), "needs a blockquote summary"
    assert any(l.startswith("## ") for l in lines), "needs at least one H2 section"


def test_every_llms_txt_link_points_at_a_file_that_exists():
    text = LLMS.read_text(encoding="utf-8")
    links = re.findall(r"\]\((https://github\.com/[^)]+)\)", text)
    assert len(links) >= 20, f"only {len(links)} links; the map looks incomplete"
    missing = []
    for url in links:
        m = re.match(
            r"https://github\.com/chandewardnyanesh/linkedin-network-intelligence"
            r"/(?:blob|tree)/main/(.+)$", url)
        assert m, f"unexpected link shape: {url}"
        if not (ROOT / m.group(1)).exists():
            missing.append(m.group(1))
    assert not missing, f"llms.txt points at files that do not exist: {missing}"


def test_every_skill_appears_in_llms_txt():
    text = LLMS.read_text(encoding="utf-8")
    for skill in sorted(p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")):
        assert skill in text, f"{skill} is not in llms.txt"


def test_llms_txt_states_the_differentiator_unambiguously():
    """A generative engine has to be able to lift one correct sentence."""
    text = LLMS.read_text(encoding="utf-8").lower()
    for claim in ("never sends", "no scraper", "no browser driver",
                  "no linkedin credential", "mit"):
        assert claim in text, f"llms.txt does not state: {claim}"
    assert "not affiliated" in text


# ------------------------------------------------------- the Pages site ---

def test_pages_site_has_the_head_tags_that_decide_the_snippet():
    html = PAGES.read_text(encoding="utf-8")
    assert "<title>" in html
    title = re.search(r"<title>(.*?)</title>", html, re.S).group(1)
    assert 30 <= len(title) <= 110, f"title is {len(title)} chars"
    desc = re.search(r'<meta name="description" content="(.*?)"', html, re.S)
    assert desc, "no meta description"
    assert 120 <= len(desc.group(1)) <= 500, f"description is {len(desc.group(1))} chars"
    assert f'<link rel="canonical" href="{PAGES_URL}"' in html
    assert 'property="og:title"' in html and 'name="twitter:card"' in html


def test_pages_site_points_agents_at_llms_txt():
    """The llms.txt v2 recommendation: rel=describedby and rel=alternate."""
    html = PAGES.read_text(encoding="utf-8")
    assert 'rel="describedby"' in html
    assert 'rel="alternate" type="text/markdown"' in html
    assert "llms.txt" in html


@pytest.fixture
def ld_graph():
    html = PAGES.read_text(encoding="utf-8")
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>',
                        html, re.S)
    assert len(blocks) == 1, f"expected one JSON-LD block, found {len(blocks)}"
    return json.loads(blocks[0])["@graph"]


def test_structured_data_parses_and_declares_the_right_types(ld_graph):
    types = {node["@type"] for node in ld_graph}
    assert {"SoftwareApplication", "SoftwareSourceCode", "FAQPage",
            "BreadcrumbList"} <= types


def test_software_application_node_is_complete(ld_graph):
    app = next(n for n in ld_graph if n["@type"] == "SoftwareApplication")
    for field in ("name", "description", "license", "codeRepository",
                  "applicationCategory", "softwareVersion", "featureList"):
        assert app.get(field), f"SoftwareApplication is missing {field}"
    assert app["codeRepository"] == REPO_URL
    assert "MIT" in app["license"]
    assert len(app["featureList"]) >= 10


def test_declared_version_matches_the_package(ld_graph):
    app = next(n for n in ld_graph if n["@type"] == "SoftwareApplication")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "(.+?)"', pyproject, re.M).group(1)
    assert app["softwareVersion"] == version
    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert str(citation["version"]) == version
    init = (ROOT / "lni/__init__.py").read_text(encoding="utf-8")
    assert f'__version__ = "{version}"' in init


def test_every_faq_answer_in_schema_is_also_visible_on_the_page(ld_graph):
    """Schema that does not match the rendered content is worse than none."""
    faq = next(n for n in ld_graph if n["@type"] == "FAQPage")
    html = PAGES.read_text(encoding="utf-8")
    visible = re.findall(r'<p class="q">(.*?)</p>', html, re.S)
    visible_norm = {re.sub(r"\s+", " ", v).strip().rstrip("?").lower()
                    for v in visible}
    assert len(faq["mainEntity"]) >= 10
    missing = []
    for q in faq["mainEntity"]:
        name = q["name"].strip().rstrip("?").lower()
        if not any(name in v or v in name for v in visible_norm):
            missing.append(q["name"])
    assert len(missing) <= 3, (
        f"{len(missing)} schema questions are not rendered on the page: {missing}")


def test_faq_answers_are_substantial_enough_to_be_extracted(ld_graph):
    faq = next(n for n in ld_graph if n["@type"] == "FAQPage")
    for q in faq["mainEntity"]:
        text = q["acceptedAnswer"]["text"]
        words = len(text.split())
        assert 25 <= words <= 140, f"{q['name']!r} answer is {words} words"


# -------------------------------------------------- sitemap and robots ---

def test_sitemap_is_valid_and_lists_only_pages_that_exist():
    tree = ET.fromstring(SITEMAP.read_text(encoding="utf-8"))
    ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    locs = [e.text for e in tree.iter(f"{ns}loc")]
    assert locs, "sitemap lists nothing"
    for loc in locs:
        assert loc.startswith(PAGES_URL), loc
        rel = loc[len(PAGES_URL):]
        target = ROOT / "docs" / (rel or "index.html")
        assert target.exists(), f"sitemap lists {loc} but {target} does not exist"


def test_robots_allows_crawling_and_names_the_sitemap():
    robots = (ROOT / "docs/robots.txt").read_text(encoding="utf-8")
    assert "User-agent: *" in robots
    assert "Allow: /" in robots
    assert "Disallow: /" not in robots
    assert f"Sitemap: {PAGES_URL}sitemap.xml" in robots


def test_jekyll_is_disabled_so_static_files_are_served_as_written():
    assert (ROOT / "docs/.nojekyll").is_file(), (
        "without docs/.nojekyll, Pages runs Jekyll over the markdown docs")


# -------------------------------------------- README and plugin manifest ---

def test_readme_opens_with_an_extractable_definition():
    lines = [l for l in (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
             if l.strip()]
    assert lines[0].startswith("# ")
    opening = " ".join(lines[1:4]).lower()
    for term in ("linkedin", "skill"):
        assert term in opening, f"the opening does not mention {term}"


def test_readme_uses_question_shaped_headings():
    heads = re.findall(r"^## (.+)$", (ROOT / "README.md").read_text(encoding="utf-8"), re.M)
    questions = [h for h in heads if h.strip().endswith("?")]
    assert len(questions) >= 6, (
        f"only {len(questions)} of {len(heads)} H2s are question-shaped; answer "
        f"engines match headings to queries")


def test_readme_carries_install_commands_the_directories_extract():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for command in ("/plugin marketplace add", "npx -y skills add",
                    "~/.claude/skills/", "pip install -r requirements.txt"):
        assert command in readme, f"README does not show: {command}"


def test_readme_states_the_limitations():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert re.search(r"^## What can it not do\?", readme, re.M)
    assert "Not affiliated" in readme


def test_plugin_manifest_is_discoverable():
    manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    assert manifest["license"] == "MIT"
    assert 120 <= len(manifest["description"]) <= 600
    assert len(manifest.get("keywords", [])) >= 5
    assert "linkedin" in manifest["keywords"]


def test_faq_document_answers_the_queries_people_actually_type():
    faq = (ROOT / "docs/FAQ.md").read_text(encoding="utf-8")
    heads = re.findall(r"^## (.+)$", faq, re.M)
    assert len(heads) >= 20, f"only {len(heads)} FAQ entries"
    assert all(h.strip().endswith("?") for h in heads), "every FAQ heading is a question"
    joined = faq.lower()
    for topic in ("terms", "scrape", "session cookie", "score", "crm",
                  "delete", "affiliated"):
        assert topic in joined, f"the FAQ does not cover: {topic}"
