from backend.app.retrieval import InMemoryStore
from backend.app.models import Chunk


def test_search_returns_most_relevant_chunk_first():
    store = InMemoryStore()
    store.add([
        Chunk("a", "d", 1, "Clause 5.1", "Rent is due on the 5th monthly"),
        Chunk("b", "d", 2, "Clause 9", "Termination needs 30 days notice"),
    ])
    hits = store.search("when is rent due?", top_k=1)
    assert len(hits) == 1
    assert hits[0].chunk_id == "a"


def test_empty_store_returns_empty():
    assert InMemoryStore().search("rent", top_k=3) == []


def test_empty_query_returns_empty():
    store = InMemoryStore()
    store.add([Chunk("a", "d", 1, "Clause 1", "rent due")])
    assert store.search("   ", top_k=3) == []
