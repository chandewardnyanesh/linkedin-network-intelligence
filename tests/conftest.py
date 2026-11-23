"""Shared fixtures. Every test runs against an in-memory store and the shipped
configuration, so nothing a test does can touch a real one."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lni.audit import AuditLog  # noqa: E402
from lni.config import load_config  # noqa: E402
from lni.crm import NetworkCRM  # noqa: E402
from lni.db import open_database  # noqa: E402
from lni.models import Candidate, Seniority  # noqa: E402
from lni.safety import SafetyGovernor  # noqa: E402
from lni import provenance as prov  # noqa: E402


@pytest.fixture
def settings():
    return load_config(config_dir=ROOT / "config")


@pytest.fixture
def b2b_settings():
    return load_config(config_dir=ROOT / "config",
                       extra_files=[ROOT / "config/examples/b2b-sales.yaml"])


@pytest.fixture
def db(settings):
    database = open_database(settings, path_override=":memory:")
    yield database
    database.close()


@pytest.fixture
def audit(db, settings):
    return AuditLog(db, settings)


@pytest.fixture
def governor(settings, audit):
    return SafetyGovernor(settings, audit, skill="test")


@pytest.fixture
def crm(db, settings, audit, governor):
    return NetworkCRM(db, settings, audit, governor)


@pytest.fixture
def b2b_crm(b2b_settings):
    database = open_database(b2b_settings, path_override=":memory:")
    a = AuditLog(database, b2b_settings)
    g = SafetyGovernor(b2b_settings, a, skill="test")
    yield NetworkCRM(database, b2b_settings, a, g)
    database.close()


@pytest.fixture
def today():
    return date.today()


def make_candidate(name: str, **kwargs) -> Candidate:
    """A valid candidate with a derived id and real provenance."""
    slug = name.lower().replace(" ", "-").replace(".", "")
    url = kwargs.pop("profile_url", f"https://linkedin.com/in/{slug}")
    sources = kwargs.pop("sources", None)
    if sources is None:
        sources = [prov.user_url(url)] if url else [prov.user_note(f"told me about {name}")]
    return Candidate.create(name=name, profile_url=url, sources=sources, **kwargs)


@pytest.fixture
def candidate_factory():
    return make_candidate


@pytest.fixture
def strong_candidate():
    return make_candidate(
        "Dana Whitfield",
        company="Northfield Foods",
        professional_title="VP Operations",
        industry="Food and beverage manufacturing",
        geography="United States",
        seniority=Seniority.vp,
        company_size_band="201-500",
        tags=["inventory accuracy", "demand planning"],
        last_verified=date.today(),
    )
