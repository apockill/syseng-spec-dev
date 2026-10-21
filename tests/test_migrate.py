"""Moving a spec to intent records and locks (CLI-28, DR-63)."""

import pytest

from syseng import changes, check, cli, edit, migrate, model, yamlio

_ADA = "Ada <ada@example.com>"


def _intent(said):
    return {"by": _ADA, "when": "2026-10-11", "basis": "stated", "context": "Planning widgets.", "said": said}


def _convert(root):
    """What an agent does first: a person's words become intent, an agent's items get a basis."""
    batch = {"edits": [
        {"modify": "NEED-1", "unset": ["origin", "source"], "intent": _intent("wants widgets"), "reason": "migration"},
        {"modify": "SYS-1", "unset": ["origin", "source"], "intent": _intent("asked for widgets"),
         "reason": "migration"},
        {"modify": "CORE-1", "unset": ["origin"], "set": {"basis": "derived"}, "reason": "migration"},
        {"modify": "CORE-V1", "unset": ["origin"], "reason": "migration"},
    ]}
    result = edit.run(root, batch)
    if result.needs_acks:
        result = edit.run(root, {**batch, "acks": {k: "migration" for k in result.needs_acks}})
    assert result.applied, result.errors


@pytest.fixture
def old(spec):
    spec.files["approvals.yaml"] = [{"id": "SYS-1", "fingerprint": "", "approved_at": "2026-10-11T10:00-07:00",
                                     "by": "Tess Tester", "via": "chat (round 8)", "batch": 1,
                                     "words": "approve SYS-1, love it"}]
    root = spec.write()
    s = model.load(root)
    from syseng import fingerprint
    spec.files["approvals.yaml"][0]["fingerprint"] = fingerprint.of_item(s.items["SYS-1"])
    root = spec.write()
    changes.start(model.load(root), "move to intent records", None, None, None)
    return root


def test_migrate_refuses_while_items_keep_the_older_fields(old):
    with pytest.raises(migrate.MigrateError, match="NEED-1 \\(source, origin\\)"):
        migrate.run(model.load(old), changes.current(model.load(old)))


def test_migrate_moves_locks_without_words_and_marks_the_spec_current(old):
    _convert(old)
    assert cli.main(["--spec", str(old), "migrate"]) == 0
    assert not (old / "approvals.yaml").exists()
    lock = yamlio.read(old / "locks.yaml")[0]
    assert lock["locked_at"] == "2026-10-11T10:00-07:00" and "words" not in lock and "approved_at" not in lock
    assert (lock["by"], lock["via"]) == ("Tess Tester <tess@example.com>", "chat")  # the person running it
    assert "given via chat (round 8)" in lock["note"]
    config = yamlio.read(old / "toolkit.yaml")
    assert config["spec_version"] == 2 and config["flow_down"] == "enforced"
    s = model.load(old)
    assert not [f for f in check.check(s) if f.severity == "error" and f.code != "R001"]
    with pytest.raises(migrate.MigrateError, match="already"):
        migrate.run(s, changes.current(s))


def test_migrate_takes_verbatim_words_out_of_change_records_and_keeps_summaries(old):
    _convert(old)
    c = changes.current(model.load(old))
    c.data.setdefault("decisions", []).append({"id": "D1", "question": "q", "status": "resolved", "chosen": "a",
                                               "words": "yeah do it, love it"})
    c.data["decisions"].append({"id": "D2", "question": "q", "status": "resolved", "chosen": "b",
                                "words": "Ada (summary): agreed to b"})
    c.save()
    migrate.run(model.load(old), changes.current(model.load(old)))
    data = changes.current(model.load(old)).data
    befores = [e.get("before", {}) for e in data["entries"] if e["id"] in ("NEED-1", "SYS-1")]
    assert all(b["source"] == migrate.MARKER for b in befores)
    assert [d["words"] for d in data["decisions"]] == [migrate.MARKER, "Ada (summary): agreed to b"]


def test_migrate_carries_a_lock_over_a_declared_rewording(old):
    _convert(old)
    batch = {"edits": [{"modify": "SYS-1", "set": {"text": "The system shall produce widgets."},
                        "rewording": True, "reason": "vocabulary"}]}
    result = edit.run(old, batch)
    if result.needs_acks:
        result = edit.run(old, {**batch, "acks": {k: "same meaning" for k in result.needs_acks}})
    assert result.applied
    report = migrate.run(model.load(old), changes.current(model.load(old)))
    assert report["carried"] == ["SYS-1"]
    lock = yamlio.read(old / "locks.yaml")[0]
    assert lock["migrated_from"] and lock["text"] == "The system shall produce widgets."
    from syseng import levels
    assert not levels.level_of(model.load(old), "SYS-1").changed


def test_a_migrated_spec_rejects_the_older_fields(old):
    _convert(old)
    migrate.run(model.load(old), changes.current(model.load(old)))
    reqs = yamlio.read(old / "elements/CORE/requirements.yaml")
    reqs[0]["origin"] = "agent"
    yamlio.write(old / "elements/CORE/requirements.yaml", reqs)
    assert any(f.code == "A009" and f.item == "CORE-1" for f in check.check(model.load(old)))
