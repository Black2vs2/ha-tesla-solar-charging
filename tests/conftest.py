"""Shared test fixtures — mock homeassistant modules for import."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock all homeassistant modules before any tesla_solar_charging imports
for mod in [
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.components",
    "homeassistant.components.sensor",
    "homeassistant.components.switch",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.event",
    "homeassistant.helpers.selector",
    "homeassistant.helpers.storage",
    "homeassistant.helpers.sun",
    "homeassistant.helpers.update_coordinator",
]:
    sys.modules.setdefault(mod, MagicMock())

# Also mock voluptuous and aiohttp since they may not be installed
sys.modules.setdefault("voluptuous", MagicMock())
sys.modules.setdefault("aiohttp", MagicMock())

# Add custom_components to path
sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components"))
