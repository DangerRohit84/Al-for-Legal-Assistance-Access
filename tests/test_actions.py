from backend.app.actions import build_checklist, build_draft


def test_checklist_has_steps_and_disclaimer():
    items = build_checklist("rent due", ["Clause 5.1 rent due 5th"])
    assert len(items) >= 3
    assert any("lawyer" in s.lower() or "verify" in s.lower() for s in items)


def test_draft_labels_as_draft_and_not_advice():
    d = build_draft("late fee dispute", ["Clause 5.2 late fee Rs 500"])
    assert "DRAFT" in d and "not legal advice" in d.lower()


def test_empty_evidence_still_safe():
    assert "DRAFT" in build_draft("topic", [])
    assert len(build_checklist("topic", [])) >= 3
