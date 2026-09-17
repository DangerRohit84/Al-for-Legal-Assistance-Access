from backend.app.ingest import chunk_pages
from backend.app.models import PageText


def test_chunk_pages_preserves_page_numbers():
    pages = [
        PageText(page=1, text="Clause 5.1 Rent is due monthly. Clause 5.2 Late fee applies."),
        PageText(page=2, text="Termination needs 30 days notice."),
    ]
    chunks = chunk_pages(pages)
    assert len(chunks) >= 3
    assert chunks[0].page == 1
    assert "Clause" in chunks[0].clause or "p.1" in chunks[0].clause
    assert all(c.text.strip() for c in chunks)


def test_empty_pages_yield_no_chunks():
    assert chunk_pages([]) == []


def test_preamble_preserved():
    pages = [PageText(page=1, text="Intro words. Clause 1.1 First rule here.")]
    chunks = chunk_pages(pages, doc_id="d1")
    assert any("preamble" in c.clause or "Intro" in c.text for c in chunks)
