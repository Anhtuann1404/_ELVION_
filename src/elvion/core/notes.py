"""Explicit account and dedicated-folder scope for real Apple Notes operations."""
from dataclasses import dataclass

from elvion.core.contracts import ContractError, require_text

NOTES_APP_ID = "com.apple.Notes"
NOTES_FOLDER = "ELVION"


def valid_title(value: object) -> bool:
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= 256
            and not any(ord(char) < 32 or ord(char) == 127 for char in value))


@dataclass(frozen=True, kw_only=True)
class NotesScope:
    account: str

    def __post_init__(self) -> None:
        require_text(self.account, "account")
        if not valid_title(self.account) or self.account != self.account.strip():
            raise ContractError("account must be trimmed text without control characters (max 256)")

    @property
    def target(self) -> dict:
        return {"app": NOTES_APP_ID, "account": self.account, "folder": NOTES_FOLDER}
