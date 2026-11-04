"""The node types of a spec and their fields: the one definition the edit command, the checker, the review page and
the reference are derived from (MODEL-44).

A spec is a tree of elements, and every other node lives in an element. Each type has its own schema below.
`spec schema` prints them, and references/schema.md is generated from them.
"""

from dataclasses import dataclass
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, ValidationError

METHODS = ("test", "analysis", "demonstration", "inspection")
TECHNIQUES = ("unit test", "integration test", "reasoning check", "manual", "roll-up")
# Names an element can't take: they're the prefixes of other node types, so an element called DR would number its
# requirements DR-1, DR-2, like decision records (MODEL-45).
RESERVED_ELEMENT_IDS = ("NEED", "DR")

Basis = Literal["derived", "added"]


def _field(description: str, default: Any = ..., *, required: bool = False, min_length: int | None = None) -> Any:
    """A field with its meaning. `required` marks a link the trace rules enforce, so the reference says it's needed."""
    return Field(default, description=description, min_length=min_length,
                 json_schema_extra={"required": True} if required else None)


def _legacy(description: str) -> Any:
    return Field(None, description=description, json_schema_extra={"legacy": True})


class Allow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule: str = _field("The wording rule's code, such as W011.")
    why: str = _field("Why the rule doesn't fit this item.")


class _Node(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = _field("Assigned by the toolkit, except for elements.")
    intent: list[dict] = _field("Records of what a person said about it (see intent records).", [])
    # the older format, still read; `spec check` reports it (A009) and `spec migrate` removes it
    origin: Any = _legacy("Older format: who asked for it.")
    source: Any = _legacy("Older format: the person's words.")
    quotes: Any = _legacy("Older format: verbatim quotes.")


class _Statement(_Node):
    text: str = _field("The statement itself.")
    basis: Basis | None = _field("Where it came from when no person asked for it: derived or added.", None)
    why: str | None = _field("The reason, when it carries a basis instead of a person's intent.", None)
    allow: list[Allow] = _field("Wording rules that don't fit this item, each with the reason.", [])


class _Requirement(_Statement):
    allocation_note: str | None = _field("How it's split across elements.", None)
    verification_deferred: str | None = _field("Why it can't be verified yet; silences the to-do.", None)
    derived: Any = _legacy("Older format: derived mark.")
    refines: Any = _legacy("Older format: refined item.")
    reworded: Any = _legacy("Older format: rewording note.")


class Need(_Statement):
    """An outcome the engineer wants, in their terms. Lives in the root element only."""
    context: str | None = _field("Background and scenarios of use.", None)


class SystemRequirement(_Requirement):
    """What the whole system shall do. Lives in the root element, and serves needs."""
    kind: Literal["system"] = _field("Set by the toolkit.", "system")
    serves: list[str] = _field("The needs it exists for.", [], required=True)


class Constraint(_Requirement):
    """A rule every part of the system follows. Lives in the root element; serving a need is optional."""
    kind: Literal["constraint"] = _field("Set by the toolkit.", "constraint")
    serves: list[str] = _field("Needs it serves, if any.", [])


class Requirement(_Requirement):
    """What one part of the system shall do. Lives in any element but the root, and refines one requirement of its
    element's parent."""
    traces_to: str | None = _field("The ID of the parent element's requirement it refines.", None, required=True)


class VerificationItem(_Node):
    """How one or more requirements are checked. Lives in any element."""
    verifies: list[str] = _field("The requirements it checks.", min_length=1)
    method: Literal[METHODS] = _field("How it's verified.")
    technique: Literal[TECHNIQUES] = _field("What does the checking; a roll-up passes when every child does.")
    description: str = _field("What the check does, in words a reader can follow without the code.")
    tests: dict[str, list[str]] = _field("Per implementation, the identifiers its results report.", {})


class DecisionRecord(_Node):
    """A design decision and its reasons. Filed under the first element it names."""
    title: str = _field("A short name for the decision.")
    decided_by: Literal["engineer", "agent"] = _field("Who made the choice.")
    elements: list[str] = _field("The elements it applies to; the first is where it's filed.", min_length=1)
    context: str = _field("What prompted it.")
    decision: str = _field("What was decided.")
    requirements: str | list[str] | None = _field("The requirements it's about, by ID.", None)
    alternatives: str | None = _field("What else was considered, and why not.", None)
    consequences: str | None = _field("What follows from it.", None)
    status: str | None = _field("For example, replaced by another decision.", None)
    recorded: str | None = _field("When, where the date matters.", None)
    basis: Basis | None = _field("Where it came from when no person decided it.", None)


class Element(_Node):
    """A part of the system. Elements form the tree every other node lives in."""
    id: str = _field("Chosen when it's added, in capitals, such as STORAGE; its nodes' IDs start with it.")
    title: str = _field("A short name.")
    purpose: str = _field("One sentence on what this part is for.")
    parent: str | None = _field("The element it's part of; only the root has none.", None)
    depends_on: list[str] = _field("Elements it reuses, which aren't its parent.", [])
    related_code: dict[str, list[str]] = _field("Per implementation, the code this element is.", {})
    note: str | None = _field("Free text.", None)


@dataclass(frozen=True)
class NodeType:
    kind: str           # the name the files and the code use
    label: str          # what people read
    model: type[BaseModel]
    id_pattern: str
    where: str


TYPES = {t.kind: t for t in (
    NodeType("element", "element", Element, "a name, such as CHECK", "the tree of the system"),
    NodeType("need", "need", Need, "NEED-n", "the root element only"),
    NodeType("system", "system requirement", SystemRequirement, "ROOT-n", "the root element only"),
    NodeType("constraint", "constraint", Constraint, "ROOT-n", "the root element only, beside system requirements"),
    NodeType("requirement", "requirement", Requirement, "ELEMENT-n", "any element but the root"),
    NodeType("vi", "verification item", VerificationItem, "ELEMENT-Vn", "any element"),
    NodeType("decision", "decision record", DecisionRecord, "DR-n", "the first element it names"),
)}


def label(kind: str) -> str:
    return TYPES[kind].label if kind in TYPES else kind


def describe(kind: str) -> str:
    return (TYPES[kind].model.__doc__ or "").split("\n\n")[0].replace("\n    ", " ").strip() if kind in TYPES else ""


def fields(kind: str) -> set[str]:
    """The fields an edit may set: everything but the ID, which the toolkit assigns."""
    return set(TYPES[kind].model.model_fields) - {"id"}


def current_fields(kind: str) -> list[tuple[str, Any]]:
    """The fields of the current format, in order, for the reference."""
    return [(name, f) for name, f in TYPES[kind].model.model_fields.items()
            if not (f.json_schema_extra or {}).get("legacy")]


def problems(kind: str, data: dict) -> list[str]:
    """What's wrong with a node's fields, each as a short phrase: "has no `text`", "has method 'x'; use one of …"."""
    model = TYPES[kind].model
    try:
        model.model_validate({"id": "?", **data})
    except ValidationError as e:
        out = []
        for err in e.errors():
            where = ".".join(str(p) for p in err["loc"])
            name = str(err["loc"][0]) if err["loc"] else ""
            field = model.model_fields.get(name)
            if err["type"] == "missing":
                out.append(f"has no `{where}`")
            elif err["type"] == "extra_forbidden":
                out.append(f"has a field the {label(kind)} type doesn't have: `{where}`")
            elif err["type"] == "literal_error":
                allowed = ", ".join(str(a) for a in field.annotation.__args__) if field else ""
                out.append(f"has {where} {err.get('input')!r}; use one of {allowed}")
            elif err["type"] == "too_short":
                out.append(f"has an empty `{where}`")
            else:
                out.append(f"`{where}` {err['msg'][0].lower()}{err['msg'][1:]}")
        return out
    return []


def json_schema() -> dict:
    return {kind: t.model.model_json_schema() for kind, t in TYPES.items()}


def _type_name(annotation) -> str:
    """A field's type in words: text, a list of IDs, one of a few values."""
    origin, args = get_origin(annotation), get_args(annotation)
    if origin is Literal:
        words = [str(a) for a in args]
        return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " or " + words[-1]
    if origin in (Union, UnionType):
        return " or ".join(_type_name(a) for a in args if a is not type(None))
    if origin is list:
        inner = args[0] if args else Any
        return "list of {rule, why}" if inner is Allow else "list of records" if inner is dict else "list of IDs"
    if origin is dict:
        return "per implementation, a list"
    return {str: "text", Any: "any"}.get(annotation, getattr(annotation, "__name__", str(annotation)))


def _ordered(kind: str) -> list[tuple[str, Any]]:
    """The statement first, then its links and details, and the records last."""
    names = current_fields(kind)
    last = [n for n in names if n[0] in ("intent",)]
    first = [n for n in names if n[0] in ("id", "text", "title")]
    return first + [n for n in names if n not in first and n not in last] + last


def reference() -> str:
    """The node types and their fields, in Markdown, for references/schema.md."""
    lines = []
    for kind, t in TYPES.items():
        lines += [f"### {t.label[0].upper()}{t.label[1:]}", "", describe(kind), "",
                  f"ID: {t.id_pattern}. Lives in: {t.where}. Add it with `- add: {kind}`.", "",
                  "| Field | Type | Required | Meaning |", "|---|---|---|---|"]
        for name, f in _ordered(kind):
            if name == "id" and kind != "element":
                continue
            required = f.is_required() or bool((f.json_schema_extra or {}).get("required"))
            lines.append(f"| `{name}` | {_type_name(f.annotation)} | {'yes' if required else 'no'} | {f.description} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
