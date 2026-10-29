"""Scoped Notes permissions; every real note creation requires explicit approval."""
from elvion.core.contracts import ActionIntent
from elvion.core.notes import NotesScope, valid_title
from elvion.policy.rules import CapabilityPolicy


class NotesPolicy(CapabilityPolicy):
    version = "macos-notes-v1"

    def __init__(self, scope: NotesScope, *, require_confirmation: bool = False):
        super().__init__(require_confirmation=require_confirmation)
        self.scope = scope

    def allows(self, intent: ActionIntent, grants: frozenset[str]) -> bool:
        expected = {"note.create": "note_exists", "note.find": "note_found"}.get(intent.capability)
        return (expected is not None and intent.capability in grants
                and intent.target == self.scope.target and intent.preconditions == ()
                and intent.risk == "low" and set(intent.arguments) == {"title"}
                and valid_title(intent.arguments.get("title"))
                and intent.postcondition == {"kind": expected, "title": intent.arguments["title"]})

    def requires_confirmation(self, intent: ActionIntent) -> bool:
        return intent.capability == "note.create" or super().requires_confirmation(intent)

    def confirmation_effects(self, intent: ActionIntent) -> tuple[str, ...]:
        if intent.capability == "note.create":
            return ("Create a note in the selected account", "Create ELVION folder in that account if missing")
        return ("Read matching note metadata only in the selected account / ELVION folder",)
