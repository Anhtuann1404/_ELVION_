"""Small, explicit Vietnamese command grammar without a language model."""
import re
import unicodedata

from elvion.core.app_catalog import APP_ALIASES
from elvion.core.contracts import ActionIntent, TaskRequest


class UnsupportedCommand(ValueError):
    pass


def plan(request: TaskRequest) -> ActionIntent:
    text = unicodedata.normalize("NFC", request.utterance).strip()
    open_match = re.fullmatch(r"mở\s+(.+)", text, flags=re.IGNORECASE)
    if open_match:
        alias = " ".join(open_match.group(1).casefold().split())
        bundle_id = APP_ALIASES.get(alias)
        if bundle_id is None:
            raise UnsupportedCommand("App is not in the initial allowlist")
        return ActionIntent(task_id=request.task_id, capability="app.open", target={"app": bundle_id},
                            arguments={}, postcondition={"kind": "app_running", "bundle_id": bundle_id})
    match = re.fullmatch(r"tạo\s+ghi\s+chú\s+(.+)", text, flags=re.IGNORECASE)
    if match is None or not match.group(1).strip():
        raise UnsupportedCommand("Use: Tạo ghi chú <tiêu đề>")
    title = match.group(1).strip()
    return ActionIntent(
        task_id=request.task_id, capability="note.create", target={"app": "FakeNotes"},
        arguments={"title": title}, postcondition={"kind": "note_exists", "title": title},
    )
