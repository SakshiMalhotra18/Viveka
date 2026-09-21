"""
VIVEKA Phase 7: Demo Agent Package.

Provides bundled demo AI customer support agent, fake tools, and vulnerability scenarios.
"""

from __future__ import annotations

from viveka.demo.agent import DemoAgent, run_demo_agent
from viveka.demo.tools import DemoToolStore, create_demo_tools
from viveka.demo.vocabulary import VulnerabilityScenario

__all__ = [
    "DemoAgent",
    "DemoToolStore",
    "VulnerabilityScenario",
    "create_demo_tools",
    "run_demo_agent",
]
