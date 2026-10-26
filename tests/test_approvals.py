"""Approvals: fingerprints of meaning (MODEL-24, MODEL-25, MODEL-31), merge gating (CHECK-14, CHECK-15)."""

from syseng import cli, fingerprint, yamlio


def _approve(spec, item_id, kind, data):
    spec.files["approvals.yaml"].append({"id": item_id, "fingerprint": fingerprint.of(kind, data)})


def test_rewording_unapproves_but_relinking_does_not(spec):
    req = spec.files["elements/CORE/requirements.yaml"][0]
    vi = spec.files["elements/CORE/verification.yaml"][0]
    _approve(spec, "CORE-1", "requirement", req)
    _approve(spec, "CORE-V1", "vi", vi)
    spec.write()
    unapproved = {f.item for f in spec.findings() if f.code == "A003"}
    assert "CORE-1" not in unapproved and "CORE-V1" not in unapproved

    vi["tests"] = {"python": ["tests/test_core.py::test_stamp_renamed"]}   # re-link: checker's job
    spec.write()
    assert "CORE-V1" not in {f.item for f in spec.findings() if f.code == "A003"}

    req["text"] = "The core shall stamp each widget twice."               # reword: meaning changed
    spec.write()
    assert "CORE-1" in {f.item for f in spec.findings() if f.code == "A003"}


def test_merge_check_never_fails_because_of_approvals(spec, capsys):
    root = spec.write()
    assert "A003" not in spec.codes(severity="todo")   # nothing a person gave has changed since
    assert cli.main(["--spec", str(root), "check", "--merge"]) == 0
    assert "No alteration awaits the engineer's answer." in capsys.readouterr().out


def test_approval_of_unknown_item_is_reported(spec):
    spec.files["approvals.yaml"].append({"id": "GHOST-1", "fingerprint": "000000000000"})
    spec.write()
    assert "A005" in spec.codes()


def test_approve_command_records_fingerprint_and_words(spec, capsys):
    root = spec.write()
    assert cli.main(["--spec", str(root), "approve", "CORE-1", "SYS-1..1", "--words", "approve CORE-1, SYS-1"]) == 0
    records = {a["id"]: a for a in yamlio.read(root / "approvals.yaml")}
    assert set(records) == {"CORE-1", "SYS-1"}
    assert records["CORE-1"]["said"] == "approve CORE-1, SYS-1" and "words" not in records["CORE-1"]
    assert records["CORE-1"]["fingerprint"] == fingerprint.of(
        "requirement", spec.files["elements/CORE/requirements.yaml"][0])


def test_approve_refuses_unknown_ids(spec, capsys):
    root = spec.write()
    assert cli.main(["--spec", str(root), "approve", "NOPE-9", "--words", "x"]) == 1
    assert yamlio.read(root / "approvals.yaml") == []


def test_a_lock_recorded_with_a_summary_keeps_it_in_said(spec):                        # MODEL-34
    from syseng import cli
    spec.write()
    assert cli.main(["--spec", str(spec.root), "lock", "CORE-1", "--via", "chat",
                     "--words", "Locked the stamping rule after reviewing it."]) == 0
    lock = spec.load().approvals[-1]
    assert lock["said"].startswith("Locked") and "words" not in lock
