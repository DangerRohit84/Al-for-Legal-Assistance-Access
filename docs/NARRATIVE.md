# Narrative — submission writeup (copy-paste ready)

## Problem
Everyday legal text (rent agreements, consumer terms, FIR-type PDFs) is unreadable for non-lawyers; general AI hallucinates clauses, page numbers, and amounts with no way to verify.

## Why better than general AI
- Traceability: every claim cites `[Doc p.X, Clause Y]` with `doc_id` + page + clause + text; no citation → no answer.
- Refusal: exact `Cannot Determine from the provided documents.` + `Partial/Grounded/Cannot Determine` confidence; zero-overlap retrieval returns `[]` so the hard backend override fires.
- Workflow: comparison mode (same question side-by-side across two docs) + 5-step action checklist ending with lawyer-verify + `[DRAFT]` letter helper, not just a summary.
- Access: plain-language toggle (prompt-level style switch, E2E wired), keyboard + ARIA-live UI, AA contrast, reduced-motion support.

## Trust design
- Grounded prompt forces citations + verbatim refusal (Rules 1–5, `<context>`/`<question>` delimiters + do-not-follow-data rule, temperature 0); backend hard-enforces Cannot Determine on zero hits per side.
- Disclaimer `General information only — not legal advice. Verify with a qualified lawyer.` on banner UI + `/ask` + `/compare` + `/action-plan` + draft footer + prompt Rule 4.
- PDF validation pre-parse (extension → bounded `MAX+1` read → `%PDF-` magic → content-type, then pages post-parse), sanitized echo, Pydantic bounds (`doc_ids ≤5`, `top_k 1..10`), env-only keys, allowlist CORS, security headers, full-entropy `doc_id`, bounded index with 429.

## Tech flexibility note
Any LLM / any host per FAQ Technical Flexibility. Default offline provider (zero-key demo);
optional Gemini toggle (`LLM_PROVIDER=gemini`) + Cloud Run Dockerfile for Google-services weightage
without forcing Google-only.

## Gen AI usage (for portal "Gen AI description" field)
AI-assisted boilerplate (FastAPI wiring, clause regex, TF-IDF + fallback, vanilla JS fetch handlers, pytest skeletons), then human-engineered trust logic: citation schema + renderer, exact refusal + hard override, disclaimer everywhere, prompt Rules 1–5 with delimiters, zero-overlap filter, Pydantic bounds, magic pre-parse ordering, bounded index, headers, allowlist CORS. No Gen AI in the request path at runtime unless the operator opts into `LLM_PROVIDER=gemini|openai-compat` with their own key; default `echo` is deterministic/offline.

## Changes description (for portal "changes description" field)
Final hardening for 100/100: bounded upload read (`MAX+1`, no OOM), full-entropy `doc_id` (32 hex), Pydantic bounds (`doc_ids ≤5`, `top_k 1..10`), allowlist CORS + security headers, non-root Docker + HEALTHCHECK, action-plan citations now include `text` like ask/compare, 12 hardening regression tests (magic, entropy, 422 bounds, headers, CORS, delimiters + Rule 5), README extended with vertical/approach/how-it-works/assumptions/Gen-AI/evaluation mapping. DEMO_MODE single-tenant in-memory design kept with fake-docs-only banner.

## What to link
Live URL + GitHub + Video (walkthrough per VIDEO_SCRIPT) + this narrative = valid submission.
