"""LinkedIn Network Intelligence — reusable Agent Skills for professional
network research, scoring and relationship management.

Not affiliated with, endorsed by, or connected to LinkedIn Corporation.

This package reads only what the user supplies or what is publicly available
through an authorised source. It contains no LinkedIn scraper, no browser
automation and no sender: every external action is drafted here and performed
by the human in LinkedIn's own interface. See `lni.safety` and `docs/SAFETY.md`.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = [
    "__version__", "load_config", "open_database", "NetworkCRM", "AuditLog",
    "SafetyGovernor",
]


def __getattr__(name: str):  # lazy, so `import lni` stays cheap
    if name == "load_config":
        from .config import load_config

        return load_config
    if name == "open_database":
        from .db import open_database

        return open_database
    if name == "NetworkCRM":
        from .crm import NetworkCRM

        return NetworkCRM
    if name == "AuditLog":
        from .audit import AuditLog

        return AuditLog
    if name == "SafetyGovernor":
        from .safety import SafetyGovernor

        return SafetyGovernor
    raise AttributeError(f"module 'lni' has no attribute {name!r}")
