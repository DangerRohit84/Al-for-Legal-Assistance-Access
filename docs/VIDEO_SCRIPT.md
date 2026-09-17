# Video script — 2–3 min functionality walkthrough (required)

Record real app, no slides. Show URL bar at start (proves Live URL).

0:00–0:15 — Hook + disclaimer
- “Rent disputes shouldn’t need a lawyer to start. This answers only from your PDFs, with citations.”
- Point to banner: “General information only — not legal advice.”

0:15–0:45 — Upload
- Upload `rent-agreement.pdf` → show doc_id + pages + chunks.
- Note guards: “PDF only, 10 MB, 100 pages.”

0:45–1:20 — Grounded Q&A
- Ask “When is rent due?” → show answer + `[Doc p.X, Clause Y]` + confidence `Grounded`.
- Toggle plain-language → re-ask → simpler wording, same citations.

1:20–1:45 — Cannot Determine (trust moment — do not skip)
- Ask something NOT in the doc (“What is the capital of France?” or unrelated clause).
- Show exact “Cannot Determine from the provided documents.” + `Cannot Determine` badge.

1:45–2:15 — Comparison mode
- Upload second doc (standard tenant rights) → Compare same question → side-by-side answers + citations.

2:15–2:40 — Action helper
- Topic “Late-fee dispute” → checklist (5 steps, ends with “verify with lawyer”) + `[DRAFT]` letter.

2:40–3:00 — Close + stack
- “LLM-agnostic: offline echo by default, Gemini toggle for Google bonus. TF-IDF retrieval, FastAPI, deploys anywhere incl. Cloud Run.”
- End on Live URL + GitHub link.

Checklist: 1080p, captions on, no API keys visible, sample PDFs are fake/redacted.
