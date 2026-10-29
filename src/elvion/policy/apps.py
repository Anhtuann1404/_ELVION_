"""Only the exact allowlisted app.open action may reach the real macOS adapter."""
from elvion.core.app_catalog import ALLOWED_APP_IDS
from elvion.core.contracts import ActionIntent
from elvion.policy.rules import CapabilityPolicy


class AppPolicy(CapabilityPolicy):
    version = "macos-app-v1"

    def allows(self, intent: ActionIntent, grants: frozenset[str]) -> bool:
        bundle_id = intent.target.get("app")
        return (intent.capability == "app.open" and "app.open" in grants
                and bundle_id in ALLOWED_APP_IDS and intent.target == {"app": bundle_id}
                and intent.arguments == {} and intent.preconditions == () and intent.risk == "low"
                and intent.postcondition == {"kind": "app_running", "bundle_id": bundle_id})
