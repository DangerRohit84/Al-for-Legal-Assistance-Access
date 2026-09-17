from backend.app.prompting import build_grounded_prompt, confidence_for, format_citations
from backend.app.models import Chunk
from backend.app.llm.factory import get_provider


def test_prompt_forces_citations_and_refusal():
    p = build_grounded_prompt("When is rent due?", [], plain_language=False)
    assert "Cannot Determine" in p
    assert "[Doc p." in p or "Citation" in p


def test_plain_language_toggle_changes_style():
    p = build_grounded_prompt("q?", [], plain_language=True)
    assert "plain" in p.lower()


def test_confidence_levels():
    assert confidence_for([], 0) == "Cannot Determine"
    assert confidence_for([Chunk("a", "d", 1, "Clause 5.1", "rent due")], 1) == "Partial"
    assert confidence_for(
        [Chunk("a", "d", 1, "Clause 5.1", "x"), Chunk("b", "d", 2, "Clause 5.2", "y")], 2
    ) == "Grounded"


def test_echo_provider_cites_or_refuses():
    prov = get_provider("echo")
    assert prov.answer("q", []) == "Cannot Determine from the provided documents."
    out = prov.answer("q", [Chunk("a", "d1", 3, "Clause 5.1", "Rent due 5th")])
    assert "p.3" in out and "Clause 5.1" in out


def test_format_citations_shape():
    line = format_citations([Chunk("a", "d1", 2, "Clause 9", "text")])
    assert line == "[Doc d1 p.2, Clause 9]"
