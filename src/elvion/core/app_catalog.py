"""Initial app identity allowlist; no platform APIs are imported here."""
from types import MappingProxyType

CALCULATOR_BUNDLE_ID = "com.apple.calculator"
APP_ALIASES = MappingProxyType({"máy tính": CALCULATOR_BUNDLE_ID, "calculator": CALCULATOR_BUNDLE_ID})
ALLOWED_APP_IDS = frozenset(APP_ALIASES.values())
