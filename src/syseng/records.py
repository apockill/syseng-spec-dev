"""Schemas for the records a person's intent leaves on the spec: intent records and locks (DR-55, DR-64).

Each record is structured metadata, not prose: who, when, in what context, what was said, and the
content it was given for. Pydantic validates each field's presence and format, and the checker
turns validation errors into findings (A006 for intent records, A010 for locks), so a malformed
record is reported with every other unfinished thing in one run (CHECK-1).
"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

PERSON = re.compile(r"^[^<>]*\S <[^<>@\s]+@[^<>@\s]+>$")  # Name <email>, as version control writes it
WHEN = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$")     # a date, and the time when it's known
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?")      # an ISO timestamp, or a date where no time was kept
FINGERPRINT = re.compile(r"^[0-9a-f]{12}$")
CHANNELS = ("terminal", "chat", "menu", "page")  # a restatement is intent, not a lock (DR-62)


def _person(value: str) -> str:
    if not PERSON.match(value or ""):
        raise ValueError("must be a person as `Name <email>`")
    return value


class IntentDraft(BaseModel):
    """What an agent writes in `spec edit`: the CLI fills in `by`, `when` and `fingerprint` when they're left out."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    basis: Literal["stated", "guided"]
    context: str
    said: str
    by: str | None = None
    when: str | None = None

    @field_validator("context", "said")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("must say something")
        return value

    @field_validator("by")
    @classmethod
    def _by(cls, value):
        return value if value is None else _person(value)

    @field_validator("when")
    @classmethod
    def _when(cls, value):
        if value is not None and not WHEN.match(value):
            raise ValueError("must be YYYY-MM-DD, or YYYY-MM-DD HH:MM when the time is known")
        return value


class IntentRecord(IntentDraft):
    """An intent record as stored on an item (MODEL-36, MODEL-37)."""
    by: str
    when: str
    fingerprint: str

    @field_validator("fingerprint")
    @classmethod
    def _fingerprint(cls, value: str) -> str:
        if not FINGERPRINT.match(value or ""):
            raise ValueError("must be the item's 12-character fingerprint, which `spec edit` fills in")
        return value


class Lock(BaseModel):
    """A lock a person put on an item, as stored in locks.yaml (MODEL-34, MODEL-35)."""
    model_config = ConfigDict(extra="forbid")

    id: str
    fingerprint: str
    locked_at: str
    by: str
    via: Literal["terminal", "chat", "menu", "page"]
    batch: int | None = None
    said: str | None = None          # a summary an agent adds; locks recorded mechanically have none
    note: str | None = None
    after: list[str] | None = None   # resolved decisions that involved the item (CLI-12)
    text: str | None = None          # the content locked, for a reader of the file
    migrated_from: str | None = None  # the fingerprint before a migration carried the lock over (DR-29, DR-63)
    released: bool | None = None      # an unlock: the person took their lock off (SYS-46); history stays append-only
    review: str | None = None         # the review page it came from

    @field_validator("locked_at")
    @classmethod
    def _stamp(cls, value: str) -> str:
        if not STAMP.match(value or ""):
            raise ValueError("must be an ISO date and time, such as 2026-10-21T13:04-07:00")
        return value

    @field_validator("by")
    @classmethod
    def _by(cls, value: str) -> str:
        return _person(value)


class FeedbackItem(BaseModel):
    """What a person did to one item on the review page (SYS-46)."""
    model_config = ConfigDict(extra="forbid")
    id: str
    fingerprint: str = ""
    lock: bool | None = None
    alteration: Literal["keep", "roll back"] | None = None
    comment: str | None = None
    wording: str | None = None      # the text the person would rather the item had (REVIEW-30)
    intent: list["IntentFix"] = []


class IntentFix(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record: int
    action: Literal["remove", "correct"]
    correction: str | None = None
    when: str | None = None   # the record's own time and person, so a reordered list can't misdirect the fix
    by: str | None = None


FeedbackItem.model_rebuild()


class FeedbackDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    change: str
    id: str
    fingerprint: str = ""
    choose: int | None = None
    comment: str | None = None


class FeedbackBlock(BaseModel):
    """The block the review page copies (SYS-51): who gave it, on which version, and what they did."""
    model_config = ConfigDict(extra="forbid")
    review: str
    by: str
    repository: str = ""
    revision: str = ""
    dirty: bool = False
    generated: str = ""
    items: list[FeedbackItem] = []
    decisions: list[FeedbackDecision] = []
    general: str | None = None

    @field_validator("by")
    @classmethod
    def _by(cls, value: str) -> str:
        return _person(value)


def problems(model: type[BaseModel], data) -> list[str]:
    """Each way `data` fails the schema, in words an agent can act on."""
    try:
        model.model_validate(data)
    except ValidationError as e:
        out = []
        for err in e.errors():
            field = ".".join(str(p) for p in err["loc"]) or "record"
            if err["type"] == "missing":
                out.append(f"`{field}` is missing")
            elif err["type"] == "extra_forbidden":
                out.append(f"`{field}` isn't a field of this record")
            elif err["type"] == "literal_error":
                out.append(f"`{field}` must be one of {err['ctx']['expected']}")
            else:
                out.append(f"`{field}` {str(err['msg']).removeprefix('Value error, ')}")
        return out
    return []
