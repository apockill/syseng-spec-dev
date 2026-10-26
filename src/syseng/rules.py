"""The rules the checker enforces, with the explanations its findings teach (CHECK-16).

Wording rules are the mechanically checkable subset of INCOSE's Guide to Writing
Requirements (rule numbers in `ref`), plus a loose reading of EARS sentence shapes (DR-30).
Every rule has an anchor in the skill's rules page, which explains it at length.
"""

import re
from dataclasses import dataclass
from pathlib import Path

RULES_PAGE = Path(__file__).resolve().parent / "skill" / "references" / "rules.md"
# Where `spec init` installs the skill, and with it the rules page.
INSTALLED_RULES_PAGES = (".claude/skills/syseng/references/rules.md", ".agents/skills/syseng/references/rules.md")


def rules_doc_for(spec_root: Path) -> str:
    """Where findings link (DR-43): the toolkit's own page when it lives in this repository, else
    the copy `spec init` installed, else the page inside the installed package."""
    repo = spec_root.resolve().parent
    try:
        return str(RULES_PAGE.relative_to(repo))
    except ValueError:
        pass
    for rel in INSTALLED_RULES_PAGES:
        if (repo / rel).exists():
            return rel
    return str(RULES_PAGE)


@dataclass(frozen=True)
class Rule:
    code: str
    title: str
    why: str
    fix: str
    ref: str = ""
    severity: str = "error"  # error | todo

    def link(self, spec_root: Path) -> str:
        return f"{rules_doc_for(spec_root)}#{self.code.lower()}"


_RULES = [
    # --- structure of the spec
    Rule("S001", "unreadable or malformed spec file",
         "The checker can't reason about content it can't parse, so nothing else about this file was checked.",
         "Fix the YAML so the file is a list of items (or a mapping, for element.yaml and toolkit.yaml)."),
    Rule("S002", "duplicate ID",
         "Two items with one ID make every trace, approval and history query ambiguous.",
         "Give the newer item a fresh ID. Never reuse a retired one."),
    Rule("S003", "retired ID reused",
         "A retired ID still means the removed item in old change records, so reusing it rewrites history.",
         "Pick the next unused number for this system element."),
    Rule("S004", "nested system element",
         "System elements live in one flat directory. Nesting hides the element from the checker.",
         "Move the directory up into spec/elements/ and express the hierarchy with `parent:` instead."),
    Rule("S005", "broken decomposition tree",
         "Requirements flow down the parent links, so they must form one tree rooted at the system.",
         "Give every element except the system exactly one existing `parent`, without loops."),
    Rule("S006", "broken dependency graph",
         "Change impact flows along `depends_on`, so it must name real elements and contain no cycles.",
         "Point `depends_on` at existing elements; break cycles by extracting the shared part into its own element."),
    Rule("S007", "missing or invalid field",
         "Each kind of item has fields the toolkit relies on.",
         "Add the field the message names, with one of the allowed values."),
    Rule("S008", "item in the wrong system element",
         "An item's ID prefix names its system element, so an item filed elsewhere is hard to find and easy to mis-trace.",
         "Move the item into the directory of the element its ID names, or rename it with a fresh ID there."),
    # --- traceability
    Rule("T001", "broken trace",
         "Every requirement traces up to what it serves; the trace is how anyone answers 'why does this exist?'.",
         "Point `traces_to` at an existing requirement (or `serves` at existing needs), or mark it `derived: true` with a `why`."),
    Rule("T002", "need served by nothing",
         "A need with no requirement under it will never be met.",
         "Add a system requirement that serves it, or ask the engineer whether the need still stands.",
         severity="todo"),  # needs may land before their requirements, as in spec-first planning (DR-31)
    Rule("T003", "dangling reference",
         "A link to an item that doesn't exist (or was retired) points readers nowhere.",
         "Fix the ID, or drop the reference."),
    Rule("T004", "requirement without verification", "", "", severity="todo"),
    Rule("T005", "requirement skips a level of the system breakdown",
         "Requirements flow down the system breakdown: a requirement on an element "
         "refines one of its parent element's requirements, so the requirement tree has the same shape as the "
         "element tree and every detail sits under the part of the system it belongs to.",
         "Point `traces_to` at a requirement of the element's parent. If the parent has none that fits, give the "
         "parent a requirement of its own for this one to refine.",
         severity="todo"),  # an error where toolkit.yaml sets `flow_down: enforced` (DR-58)
    # --- attributes
    Rule("A001", "requirement without rationale",
         "The rationale is what an agent reads first when asked why a requirement exists.",
         "Add a `why` (or, for the engineer's own words, a `source`)."),
    Rule("A002", "no intent and no basis",
         "Every item says how directly a person asked for it: a person's intent on it, or where it came from.",
         "Add the person's `intent:` with `spec edit`, or set `basis: derived` or `basis: added`."),
    Rule("A003", "changed since a person locked, stated or guided it", "", "", severity="todo"),
    Rule("A004", "alteration awaiting the engineer's answer",
         "A change altered an item the engineer approved, wrote or decided, and they haven't kept it or had it "
         "rolled back.",
         "Ask the engineer whether to keep it. The review page shows it for them to keep or roll back.",
         severity="todo"),
    Rule("A005", "lock for an unknown item",
         "An approval that matches nothing can't protect anything.",
         "Remove the stale approval, or fix its ID."),
    Rule("A006", "incomplete intent record",
         "An intent record is signal only with its author, when it was said, what was being discussed, a summary of "
         "what was said, whether it states or guides the item, and the content it was given for.",
         "Give each record `by`, `when`, `context`, `said` and `basis` (stated or guided). Add intent through "
         "`spec edit`, which fills in `by`, `when` and `fingerprint`."),
    Rule("A007", "verbatim quote in an intent record",
         "Intent records summarize what a person said, close to their words but never word for word, so "
         "conversation stays out of what the repository publishes. Double quotation marks are the sign of a quote.",
         "Rewrite the summary in the third person, keeping the person's hedges and strength and adding nothing they "
         "didn't say. Single quotes and apostrophes are fine."),
    Rule("A008", "invalid basis",
         "An item's basis says where it came from when no person stated, guided or locked it: derived when something "
         "above needs it, added when an agent added it unasked.",
         "Set `basis: derived` or `basis: added`, or record the person's intent instead."),
    Rule("A009", "field of the older format",
         "This spec has moved to intent records and locks, so a person's words live only as summarized intent "
         "records, and an agent's items say where they came from with a basis.",
         "Replace `source`, `quotes` or `refines` with `intent:` records, `origin` with intent or a basis, and drop "
         "`derived`; take `words` out of locks."),
    Rule("A010", "invalid lock",
         "A lock is a record of who locked which content, how and when; a malformed one can't show any of that.",
         "Fix the field the message names. Locks are written by `spec lock`, which fills every field in."),
    Rule("F001", "feedback not yet answered",
         "A person's comment from the review page is steering; one that's never answered is lost, and their next "
         "review page shows each comment with its response.",
         "Do what the comment asks, or explain why not, then record it: `spec feedback respond F<n> \"...\"`."),
    Rule("C001", "altered intent with no conflict raised",
         "This change alters an item a person locked or stated, and nothing brings that to them with options. "
         "In code-first mode the change goes ahead, so the end of the change is "
         "where the conflict must be raised.",
         "Raise it: `spec decide` with `kind: conflict`, `involves:` naming the item, and options such as keeping "
         "the new text, rolling back, or rewording, one recommended. A pure rewording is declared with "
         "`rewording: true` on the edit instead."),
    # --- verification items
    Rule("V001", "invalid verification item",
         "A verification item needs a method and a technique to be runnable and reviewable.",
         "Use a method from test, analysis, demonstration or inspection, and a technique the toolkit knows."),
    # --- rendered views
    Rule("V002", "linked test not found",
         "A verification item that points at a test that isn't there verifies nothing, and nobody notices.",
         "Fix the link to `path::name`, where the name is a pytest test (`test_x` or `TestThing::test_x`) or a "
         "GoogleTest (`Suite.Test`). If the test is gone, remove the link."),
    Rule("V003", "test no verification item links",
         "A test nothing links to checks something the spec doesn't claim, or a requirement that's missing.",
         "Link it from the verification item whose requirement it checks, or add the requirement it shows is "
         "missing.", severity="todo"),
    Rule("R001", "stale Markdown view",
         "The review page replaced the Markdown views; one left behind shows a spec that no longer exists.",
         "Run `spec render`, which removes it, and `spec review` for the page."),
    # --- wording (MODEL-16, MODEL-17)
    Rule("W001", "not exactly one 'shall'",
         "One requirement, one obligation: a second 'shall' hides a second requirement that can't be traced, verified or approved on its own.",
         "Split the sentence into separate requirements, or turn the extra 'shall' into a condition.",
         "INCOSE R18, R19"),
    Rule("W002", "sentence shape",
         "A requirement names who shall do what. EARS gives the shape: '[When/While/If/Where/In/During…, ]<subject> shall <response>.' Without a subject before 'shall', nobody owns the obligation.",
         "Rephrase as '[condition, ]<subject> shall <response>.'",
         "EARS; INCOSE R1, R2"),
    Rule("W003", "escape clause",
         "Phrases like 'where possible' let any implementation claim compliance, so the requirement can never fail.",
         "Delete the escape, or state the exact condition under which the requirement applies.",
         "INCOSE R8"),
    Rule("W004", "open-ended wording",
         "'etc.' or 'and/or' leaves the reader to guess the rest of the list or the logic.",
         "Name every member of the list, or split 'and/or' into explicit cases.",
         "INCOSE R9, R15"),
    Rule("W005", "vague term",
         "Words like 'easy' or 'appropriate' can't be measured, so two readers will disagree on whether the requirement holds.",
         "Replace the word with something checkable, such as a number, a named condition or an observable behavior.",
         "INCOSE R7"),
    Rule("W006", "superfluous infinitive",
         "'shall be able to X' describes a capability, not a behavior. It's satisfied by something that never actually does X.",
         "Say what the subject does: 'shall X'.",
         "INCOSE R10"),
    Rule("W007", "universal quantifier",
         "'any', 'all' and 'both' blur whether the requirement applies to each case individually or to the set as a whole.",
         "Use 'each' or 'every' for individual cases, or name the set.",
         "INCOSE R32"),
    Rule("W008", "purpose clause",
         "Reasons belong in the rationale. A purpose clause in the text adds a second, unverifiable claim.",
         "Move 'in order to …' or 'so that …' into `why`.",
         "INCOSE R20"),
    Rule("W009", "language-specific name",
         "A requirement that names code can't guide a rebuild in another language.",
         "Describe the behavior or concept. Put code names in test links or related-code lists; quote an exact value "
         "another program depends on, such as \"node_id\".",
         "INCOSE R31"),
    Rule("W010", "requirement states its own test",
         "A requirement says what must hold. How it's checked belongs in a verification item, written separately.",
         "Delete the verification wording, and put it in a verification item.",
         "INCOSE R31"),
    Rule("W011", "gendered pronoun",
         "Pronouns guessed from a name misgender people; the spec talks about real people for years.",
         "Name the person or their role (the engineer, the operator) instead of he, she, his or her."),
]
RULES = {r.code: r for r in _RULES}

METHODS = ("test", "analysis", "demonstration", "inspection")
TECHNIQUES = ("unit test", "integration test", "reasoning check", "manual")

# --- wording patterns -------------------------------------------------------------
_QUOTED = re.compile(r'"[^"]*"')

ESCAPE_CLAUSES = ["as appropriate", "where possible", "if possible", "as required", "as needed",
                  "if necessary", "when necessary", "to the extent possible", "to the extent practical",
                  "if practicable", "so far as is possible", "as much as possible", "as little as possible",
                  "where applicable"]
OPEN_ENDED = ["etc", "and so on", "including but not limited to", "and/or"]
VAGUE = ["appropriate", "adequate", "sufficient", "reasonable", "efficient", "effective", "flexible",
         "user-friendly", "easy", "easier", "easily", "simple", "simply", "fast", "quickly", "significant",
         "typical", "typically", "usually", "approximately", "several", "many", "some", "few", "almost",
         "nearly", "relevant", "various", "robust", "seamless", "seamlessly", "intuitive", "normally",
         "generally", "best"]
SUPERFLUOUS = ["be able to", "be capable of", "be designed to"]
QUANTIFIERS = ["any", "all", "both"]
PURPOSE = ["in order to", "so that", "so as to"]
SELF_TEST = ["verified by", "shall be tested", "test case", "by testing"]

# EARS, read loosely (DR-30): optional condition clauses up front, then a subject, then
# "shall" and the response. Where a condition sits inside the response is left to auditors:
# a mechanical check for it was mostly false positives on real requirements.
EARS_LEADS = ("When", "While", "If", "Where", "In", "During", "Before", "After", "Once", "Whenever",
              "Within", "Unless", "On", "For", "At", "Upon", "Throughout", "Until")
_LEAD = r"(?:" + "|".join(EARS_LEADS) + r")\b[^,]*,\s*"
_MORE = r"(?:(?:when|while|if|where|unless|once)\b[^,]*,\s*)*"
_EARS = re.compile(r"^(?:" + _LEAD + _MORE + r"(?:then\s+)?)?(?P<subject>\S.*?)\s+shall\s+\S", re.S)

_CODE_PATTERNS = [
    re.compile(r"`[^`]+`"),                                   # code spans
    re.compile(r"\b\w+\.(?:py|cpp|cc|h|hpp|rs|go|ts|js|java|yaml|yml|toml|json)\b"),  # file names
    re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b"),                 # snake_case identifiers
    re.compile(r"\b[a-z]+[A-Z][A-Za-z0-9]*\b"),               # camelCase identifiers
    re.compile(r"\b\w+\(\)"),                                 # call syntax
]


def _phrase_re(phrase: str) -> re.Pattern:
    return re.compile(r"(?<![\w-])" + re.escape(phrase).replace(r"\ ", r"\s+") + r"(?![\w-])", re.I)


_PHRASE_RULES = [
    ("W003", [(p, _phrase_re(p)) for p in ESCAPE_CLAUSES]),
    ("W004", [(p, _phrase_re(p)) for p in OPEN_ENDED]),
    ("W005", [(p, _phrase_re(p)) for p in VAGUE]),
    ("W006", [(p, _phrase_re(p)) for p in SUPERFLUOUS]),
    ("W007", [(p, _phrase_re(p)) for p in QUANTIFIERS]),
    ("W008", [(p, _phrase_re(p)) for p in PURPOSE]),
    ("W010", [(p, _phrase_re(p)) for p in SELF_TEST]),
]


@dataclass(frozen=True)
class WordingIssue:
    code: str
    message: str
    span: tuple[int, int] | None = None


def _exempt(code: str, text: str, m: re.Match) -> bool:
    """Known false positives, found by running the rules on real requirements (DR-30)."""
    word, before, after = m.group(0), text[: m.start()], text[m.end():]
    if code == "W005":
        if word.lower() == "many" and before.rstrip().lower().endswith("how"):
            return True  # "how many" asks a quantity; it isn't vague
        if word[:1].isupper() and before.strip() and not before.rstrip().endswith((".", ":")):
            return True  # capitalized mid-sentence: part of a proper name, e.g. "Easy Approach to …"
    if code == "W007" and word.lower() == "both" and re.search(r"\band\b", after):
        return True  # "both A and B" is a conjunction, not a quantifier
    return False


def _blank_quotes(text: str) -> str:
    """Hides quoted text (a quoted 'shall' is a mention, not an obligation) while keeping offsets."""
    return _QUOTED.sub(lambda m: " " * len(m.group(0)), text)


def check_wording(text: str) -> list[WordingIssue]:
    issues: list[WordingIssue] = []
    plain = _blank_quotes(text)
    shalls = list(re.finditer(r"\bshall\b", plain, re.I))
    if len(shalls) != 1:
        span = (shalls[1].start(), shalls[1].end()) if len(shalls) > 1 else None
        issues.append(WordingIssue("W001", f"found {len(shalls)} uses of 'shall'; a requirement has exactly one", span))
    elif not _EARS.match(plain):
        issues.append(WordingIssue("W002", "doesn't read '[condition, ]<subject> shall <response>'"))
    for code, patterns in _PHRASE_RULES:
        for phrase, pat in patterns:
            for m in pat.finditer(plain):
                if _exempt(code, plain, m):
                    continue
                issues.append(WordingIssue(code, f"'{m.group(0)}'", (m.start(), m.end())))
    for pat in _CODE_PATTERNS:
        for m in pat.finditer(plain):
            issues.append(WordingIssue("W009", f"'{m.group(0)}' looks like a code name", (m.start(), m.end())))
    return issues
