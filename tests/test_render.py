"""The Markdown views (REVIEW-1, REVIEW-3, REVIEW-14)."""

from syseng import render


def test_view_reads_top_down(spec):
    spec.write()
    text = render.requirements_view(spec.load())
    positions = [text.index(h) for h in ("## Needs", "## System requirements", "## Constraints",
                                         "## System elements", "## CORE: Core")]
    assert positions == sorted(positions)
    assert text.index("**NEED-1**") < text.index("**SYS-1**") < text.index("**CORE-1**")


def test_system_requirement_lists_what_refines_it(spec):
    spec.write()
    text = render.requirements_view(spec.load())
    assert "*Refined by:* CORE-1" in text


def test_view_hides_verification_items(spec):
    spec.write()
    text = render.requirements_view(spec.load())
    assert "CORE-V1" not in text and "A made widget carries a stamp" not in text


def test_render_is_stable(spec):
    spec.write()
    loaded = spec.load()
    assert render.views(loaded) == render.views(loaded)
    assert render.write_views(spec.load()) == []   # already up to date: nothing rewritten
