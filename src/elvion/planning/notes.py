"""Only create/find by exact title within an explicitly selected Notes scope."""
import re
import unicodedata

from elvion.core.contracts import ActionIntent, TaskRequest
from elvion.core.notes import NotesScope, valid_title
from elvion.planning.rules import UnsupportedCommand


def plan_notes(request: TaskRequest, *, scope: NotesScope) -> ActionIntent:
    text = unicodedata.normalize("NFC", request.utterance).strip()
    match = re.fullmatch(r"(tạo|tìm)\s+ghi\s+chú\s+(.+)", text, flags=re.IGNORECASE)
    if match is None or not valid_title(match.group(2).strip()):
        raise UnsupportedCommand("Use Tạo/Tìm ghi chú <single-line title, max 256 characters>")
    title = match.group(2).strip()
    creating = match.group(1).casefold() == "tạo"
    return ActionIntent(task_id=request.task_id,
                        capability="note.create" if creating else "note.find",
                        target=scope.target, arguments={"title": title},
                        postcondition={"kind": "note_exists" if creating else "note_found", "title": title})
