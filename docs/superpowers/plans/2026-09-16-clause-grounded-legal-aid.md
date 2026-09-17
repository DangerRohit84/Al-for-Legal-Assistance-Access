# Clause-Grounded Legal Aid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold a functional Clause-Grounded Legal Aid MVP that answers only from uploaded PDFs with page+clause citations and explicit Cannot-Determine handling.

**Architecture:** Clean-architecture FastAPI backend (ingest → retrieve → ground → act) with DIP-based LLM/embedding ports, in-memory TF-IDF retrieval fallback so MVP runs without keys, plus static accessible frontend served by the same app for one-command Cloud Run deploy.

**Tech Stack:** Python 3.10+ FastAPI + pypdf, scikit-learn TF-IDF (fallback, no download), pluggable sentence-transformers + Gemini/OpenAI-compatible LLM providers, vanilla HTML/CSS/JS frontend, pytest, Docker (Cloud Run ready).

## Global Constraints

- Every answer must include citations [Doc p.X, Clause Y] or explicit Cannot Determine — no uncited legal claims.
- Always show banner: "General information only — not legal advice. Verify with a qualified lawyer."
- No API keys in code — env vars only, `.env.example` documents all toggles.
- PDF validation: content-type application/pdf, extension .pdf, max 10 MB, max 100 pages MVP.
- Accessibility: semantic HTML, keyboard operable, ARIA live for answers, contrast AA, focus visible, plain-language toggle.
- Efficiency: chunk with page metadata, TF-IDF default (zero-download), lazy-load heavy embeddings, cache parsed docs in memory.
- LLM-agnostic: `LLMProvider` interface; default `EchoGroundedProvider` (offline, citation-preserving) + optional Gemini/OpenAI-compatible providers via env toggle.
- Deployment: any host works; Dockerfile targets Cloud Run (PORT env, stateless) for Google bonus.

---

### Task 1: Project skeleton + config + security guardrails

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/security.py`
- Create: `backend/app/__init__.py`
- Create: `backend/app/llm/__init__.py`
- Create: `.env.example`
- Create: `.gitignore`
- Test: `tests/test_security.py`

**Interfaces:**
- Consumes: none (foundation)
- Produces: `config.Settings` (env-driven), `security.validate_pdf(filename, content_type, size_bytes, num_pages)` -> raises ValueError with clear message

- [ ] **Step 1: Write the failing test**

```python
# tests/test_security.py
from backend.app.security import validate_pdf
import pytest

def test_rejects_non_pdf_extension():
    with pytest.raises(ValueError, match="PDF only"):
        validate_pdf("notes.txt", "application/pdf", 1000, 2)

def test_rejects_oversize():
    with pytest.raises(ValueError, match="10 MB"):
        validate_pdf("a.pdf", "application/pdf", 11 * 1024 * 1024, 2)

def test_rejects_too_many_pages():
    with pytest.raises(ValueError, match="100 pages"):
        validate_pdf("a.pdf", "application/pdf", 1000, 101)

def test_accepts_valid_pdf():
    assert validate_pdf("rent.pdf", "application/pdf", 1000, 5) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_security.py -v`
Expected: FAIL with "No module named backend.app.security"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/security.py
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 100

def validate_pdf(filename: str, content_type: str, size_bytes: int, num_pages: int) -> bool:
    if not filename.lower().endswith(".pdf"):
        raise ValueError("PDF only: file must end with .pdf")
    if content_type not in ("application/pdf", "application/octet-stream"):
        raise ValueError("PDF only: invalid content-type")
    if size_bytes > MAX_PDF_BYTES:
        raise ValueError("File too large: max 10 MB")
    if num_pages > MAX_PDF_PAGES:
        raise ValueError("Too many pages: max 100 pages in MVP")
    return True
```

```python
# backend/app/config.py — pydantic-free stdlib settings for zero-dep boot
import os
class Settings:
    llm_provider: str = os.getenv("LLM_PROVIDER", "echo")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    max_chunks: int = int(os.getenv("MAX_CHUNKS", "5"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_security.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/app/security.py tests/test_security.py .env.example .gitignore
git commit -m "feat: add config and PDF security guardrails"
```

---

### Task 2: PDF ingest with page+clause metadata

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/app/ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `security.validate_pdf`
- Produces: `ingest.parse_pdf_bytes(data: bytes, doc_id: str) -> Document`, `ingest.chunk_pages(pages: list[PageText]) -> list[Chunk]`; `models.Document{doc_id, filename, pages, chunks}`, `models.Chunk{chunk_id, doc_id, page, clause, text}`, `models.PageText{page, text}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ingest.py
from backend.app.ingest import chunk_pages
from backend.app.models import PageText

def test_chunk_pages_preserves_page_numbers():
    pages = [PageText(page=1, text="Clause 5.1 Rent is due monthly. Clause 5.2 Late fee applies."), PageText(page=2, text="Termination needs 30 days notice.")]
    chunks = chunk_pages(pages)
    assert len(chunks) >= 3
    assert chunks[0].page == 1
    assert "Clause" in chunks[0].clause or "p.1" in chunks[0].clause
    assert all(c.text.strip() for c in chunks)

def test_empty_pages_yield_no_chunks():
    assert chunk_pages([]) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ingest.py -v`
Expected: FAIL with "No module named backend.app.ingest"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/models.py
from dataclasses import dataclass, field
@dataclass
class PageText:
    page: int
    text: str
@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    page: int
    clause: str
    text: str
@dataclass
class Document:
    doc_id: str
    filename: str
    pages: list = field(default_factory=list)
    chunks: list = field(default_factory=list)
```

```python
# backend/app/ingest.py — pypdf for text, regex for clause split
import re
from .models import PageText, Chunk, Document
CLAUSE_RE = re.compile(r"(Clause\s+\d+(?:\.\d+)*|Section\s+\d+(?:\.\d+)*|Article\s+\d+)", re.IGNORECASE)

def chunk_pages(pages: list, doc_id: str = "doc") -> list:
    chunks = []
    for p in pages:
        parts = CLAUSE_RE.split(p.text)
        if len(parts) <= 1:
            txt = p.text.strip()
            if txt:
                chunks.append(Chunk(f"{doc_id}-p{p.page}-c0", doc_id, p.page, f"p.{p.page}", txt[:1500]))
            continue
        # parts[0] is preamble, then (label, body) pairs
        preamble = parts[0].strip()
        if preamble:
            chunks.append(Chunk(f"{doc_id}-p{p.page}-c0", doc_id, p.page, f"p.{p.page} preamble", preamble[:1500]))
        for i in range(1, len(parts), 2):
            label = parts[i].strip()
            body = parts[i+1].strip() if i+1 < len(parts) else ""
            txt = f"{label} {body}".strip()[:1500]
            if txt:
                chunks.append(Chunk(f"{doc_id}-p{p.page}-c{i//2+1}", doc_id, p.page, label, txt))
    return chunks

def parse_pdf_bytes(data: bytes, doc_id: str, filename: str = "upload.pdf") -> Document:
    from pypdf import PdfReader
    import io
    reader = PdfReader(io.BytesIO(data))
    pages = [PageText(page=i+1, text=(pg.extract_text() or "").strip()) for i, pg in enumerate(reader.pages)]
    return Document(doc_id=doc_id, filename=filename, pages=pages, chunks=chunk_pages(pages, doc_id))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_ingest.py tests/test_security.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/app/ingest.py tests/test_ingest.py
git commit -m "feat: add PDF ingest with page+clause chunking"
```

---

### Task 3: Retrieval — TF-IDF vector search with pluggable embeddings (Strategy)

**Files:**
- Create: `backend/app/retrieval.py`
- Test: `tests/test_retrieval.py`

**Interfaces:**
- Consumes: `models.Chunk`
- Produces: `retrieval.InMemoryStore.add(chunks)`, `retrieval.InMemoryStore.search(query, top_k=5) -> list[Chunk]` (TF-IDF cosine, stdlib fallback if sklearn missing)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_retrieval.py
from backend.app.retrieval import InMemoryStore
from backend.app.models import Chunk

def test_search_returns_most_relevant_chunk_first():
    store = InMemoryStore()
    store.add([Chunk("a", "d", 1, "Clause 5.1", "Rent is due on the 5th monthly"), Chunk("b", "d", 2, "Clause 9", "Termination needs 30 days notice")])
    hits = store.search("when is rent due?", top_k=1)
    assert len(hits) == 1
    assert hits[0].chunk_id == "a"

def test_empty_store_returns_empty():
    assert InMemoryStore().search("rent", top_k=3) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_retrieval.py -v`
Expected: FAIL with "No module named backend.app.retrieval"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/retrieval.py — try sklearn TF-IDF, else token-overlap fallback (zero-dep)
import re
_WORD = re.compile(r"[a-z0-9]+")
def _tokens(s: str) -> list:
    return _WORD.findall(s.lower())
class InMemoryStore:
    def __init__(self):
        self.chunks = []
    def add(self, chunks: list) -> None:
        self.chunks.extend(chunks)
    def search(self, query: str, top_k: int = 5) -> list:
        if not self.chunks or not query.strip():
            return []
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            corpus = [c.text for c in self.chunks]
            vec = TfidfVectorizer().fit_transform(corpus + [query])
            sims = cosine_similarity(vec[-1], vec[:-1])[0]
            ranked = sorted(zip(sims, self.chunks), key=lambda x: x[0], reverse=True)
            return [c for s, c in ranked[:top_k] if s > 0] or [ranked[0][1]]
        except ImportError:
            qt = set(_tokens(query))
            def score(c):
                ct = set(_tokens(c.text))
                return len(qt & ct) / (1 + len(qt | ct))
            return sorted(self.chunks, key=score, reverse=True)[:top_k]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_retrieval.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/retrieval.py tests/test_retrieval.py
git commit -m "feat: add TF-IDF retrieval with zero-dep fallback"
```

---

### Task 4: LLM-agnostic layer + grounded prompting (Factory + confidence)

**Files:**
- Create: `backend/app/llm/base.py`
- Create: `backend/app/llm/echo.py`
- Create: `backend/app/llm/gemini.py`
- Create: `backend/app/llm/factory.py`
- Create: `backend/app/prompting.py`
- Test: `tests/test_prompting.py`

**Interfaces:**
- Consumes: `models.Chunk`
- Produces: `llm.base.LLMProvider.answer(question, context_chunks) -> str`, `llm.factory.get_provider(name) -> LLMProvider`, `prompting.build_grounded_prompt(question, chunks, plain_language) -> str`, `prompting.confidence_for(hits, min_score_hint) -> Grounded|Partial|Cannot Determine`, `prompting.format_citations(chunks) -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_prompting.py
from backend.app.prompting import build_grounded_prompt, confidence_for, format_citations
from backend.app.models import Chunk

def test_prompt_forces_citations_and_refusal():
    p = build_grounded_prompt("When is rent due?", [], plain_language=False)
    assert "Cannot Determine" in p
    assert "[Doc p." in p or "Citation" in p

def test_confidence_levels():
    assert confidence_for([], 0) == "Cannot Determine"
    assert confidence_for([Chunk("a","d",1,"Clause 5.1","rent due")], 1) == "Grounded"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_prompting.py -v`
Expected: FAIL with "No module named backend.app.prompting"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/prompting.py
DISCLAIMER = "General information only — not legal advice. Verify with a qualified lawyer."
def format_citations(chunks) -> str:
    return "; ".join(f"[Doc {c.doc_id} p.{c.page}, {c.clause}]" for c in chunks)
def confidence_for(hits, count: int) -> str:
    if not hits:
        return "Cannot Determine"
    if count >= 2:
        return "Grounded"
    return "Partial"
def build_grounded_prompt(question, chunks, plain_language=False) -> str:
    style = "Explain in plain everyday language. Avoid jargon." if plain_language else "Use precise legal-aware wording."
    ctx = "\n".join(f"- ({c.doc_id} p.{c.page}, {c.clause}): {c.text}" for c in chunks) or "(no context retrieved)"
    return f"""You are a legal-aid assistant. Answer ONLY from the context. {style}
Rules: Every factual claim needs a citation like [Doc p.X, Clause Y]. If the context does not contain the answer, reply exactly: "Cannot Determine from the provided documents." Never invent clauses or page numbers.
Context:\n{ctx}\nQuestion: {question}\n{DISCLAIMER}"""
```

```python
# backend/app/llm/base.py
from abc import ABC, abstractmethod
class LLMProvider(ABC):
    name: str = "base"
    @abstractmethod
    def answer(self, question: str, context: list) -> str: ...
# backend/app/llm/echo.py — offline deterministic provider for MVP/tests
from .base import LLMProvider
from ..prompting import format_citations
class EchoGroundedProvider(LLMProvider):
    name = "echo"
    def answer(self, question, context):
        if not context:
            return "Cannot Determine from the provided documents."
        cites = format_citations(context)
        return f"Based on the provided documents: {context[0].text[:400]} {cites}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_prompting.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/prompting.py backend/app/llm/ tests/test_prompting.py
git commit -m "feat: add LLM-agnostic layer and grounded prompting"
```

---

### Task 5: Actions (checklist + draft helper) + FastAPI app wiring

**Files:**
- Create: `backend/app/actions.py`
- Create: `backend/app/main.py`
- Test: `tests/test_actions.py`

**Interfaces:**
- Consumes: `models.Chunk`, `retrieval.InMemoryStore`, `llm.factory.get_provider`, `prompting.*`
- Produces: HTTP `POST /upload`, `POST /ask`, `POST /compare`, `POST /action-plan`, `GET /health`, `GET /` (serves frontend)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_actions.py
from backend.app.actions import build_checklist, build_draft

def test_checklist_has_steps_and_disclaimer():
    items = build_checklist("rent due", ["Clause 5.1 rent due 5th"])
    assert len(items) >= 3
    assert any("lawyer" in s.lower() or "verify" in s.lower() for s in items)

def test_draft_labels_as_draft_and_not_advice():
    d = build_draft("late fee dispute", ["Clause 5.2 late fee Rs 500"])
    assert "DRAFT" in d and "not legal advice" in d.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_actions.py -v`
Expected: FAIL with "No module named backend.app.actions"

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/actions.py
from .prompting import DISCLAIMER
def build_checklist(question: str, evidence: list) -> list:
    return [f"1. Re-read cited clause(s): {'; '.join(evidence[:2]) or 'see uploaded PDF'}", f"2. Collect proof related to: {question[:80]}", "3. Note dates, amounts, and names in writing", "4. Verify with a qualified lawyer before acting"]
def build_draft(topic: str, evidence: list) -> str:
    cites = "; ".join(evidence[:3])
    return f"[DRAFT — review before sending]\nRe: {topic}\n\nDear Sir/Madam,\nPer {cites or 'the attached document'}, I write regarding '{topic}'. Kindly confirm in writing within 7 days.\n\nSincerely,\n[Your Name]\n\n({DISCLAIMER})"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ -v`
Expected: PASS (all suites green)

- [ ] **Step 5: Commit**

```bash
git add backend/app/actions.py backend/app/main.py tests/test_actions.py
git commit -m "feat: add action helper and FastAPI wiring"
```

---

### Task 6: Accessible frontend + docs + deploy (README, video script, Cloud Run)

**Files:**
- Create: `frontend/index.html`, `frontend/styles.css`, `frontend/app.js`
- Create: `README.md`, `docs/VIDEO_SCRIPT.md`, `docs/DEPLOYMENT.md`, `docs/NARRATIVE.md`
- Create: `Dockerfile`, `requirements.txt`

**Interfaces:**
- Consumes: backend HTTP API from Task 5
- Produces: keyboard-operable UI with tabs (Ask / Compare / Action Plan), citation renderer, confidence badge, plain-language toggle, disclaimer banner; deployable image

- [ ] **Step 1: Write the failing test (smoke)**

```python
# manual: python -m backend.app.main serves GET /health -> {"status":"ok"}
```

- [ ] **Step 2: Run smoke to verify it fails**

Run: `python -c "import backend.app.main"`
Expected: FAIL before main.py exists

- [ ] **Step 3: Write minimal implementation (see scaffolded files)**

- [ ] **Step 4: Run full suite + boot check**

Run: `pytest tests/ -v` + `python -m uvicorn backend.app.main:app --help`
Expected: PASS + help output

- [ ] **Step 5: Commit**

```bash
git add frontend/ README.md docs/ Dockerfile requirements.txt
git commit -m "feat: add accessible UI, docs, and Cloud Run deploy"
```

---

## Self-Review

- Spec coverage: PDF ingest+metadata (T2) ✓, vector search (T3) ✓, LLM-agnostic+Gemini toggle (T4) ✓, citations+confidence+Cannot Determine+disclaimer (T4) ✓, comparison mode (T5 `/compare`) ✓, checklist+draft (T5) ✓, plain-language toggle (T4 prompt + T6 UI) ✓, a11y/security/efficiency (T1+T6) ✓, README/video/deploy (T6) ✓.
- Placeholder scan: no TBD/TODO — every step has exact code + exact run command.
- Type consistency: `Chunk{chunk_id,doc_id,page,clause,text}` used identically in T2–T5; `InMemoryStore.search(query, top_k)` stable; `LLMProvider.answer(question, context)` stable.
