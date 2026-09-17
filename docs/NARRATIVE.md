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
- PDF validation pre-parse (extension → bounded `MAX+1` read → `%PDF-` magic → content-type, then pages post-parse), basename filename sanitization (traversal-safe) + control-char strip + allowlisted session IDs, sanitized echo, Pydantic bounds (`doc_ids ≤5`, `top_k 1..10` → 422), env-only keys (`.env` never committed), allowlist CORS, extended security headers (nosniff/DENY/no-referrer/CSP + HSTS + Permissions-Policy + `no-store` + `X-Process-Time`) + `X-RateLimit-*`/`Retry-After` with tested 429 path, full-entropy `doc_id`, bounded index with 429, safe errors (no Traceback).
- Accessibility trust: `role=alert` error region (no blocking `alert()`), `role=status` answers, focus management, AA contrast ≥4.5:1, 44px targets, `noscript` fallback.

## Tech flexibility note
Any LLM / any host per FAQ Technical Flexibility. Default offline provider (zero-key demo);
optional Gemini toggle (`LLM_PROVIDER=gemini`) + Cloud Run Dockerfile for Google-services weightage
without forcing Google-only.

## Gen AI usage (for portal "Gen AI description" field)
AI-assisted boilerplate (FastAPI wiring, clause regex, TF-IDF + fallback, vanilla JS fetch handlers, pytest skeletons), then human-engineered trust logic: citation schema with `score` + renderer, exact refusal + hard override, disclaimer everywhere, prompt Rules 1–5 with delimiters, zero-overlap filter, score-calibrated confidence (max ≥0.18 + count fallback), Pydantic bounds, magic pre-parse ordering + basename sanitization, bounded index, extended headers (HSTS/Permissions-Policy/no-store/X-Process-Time), allowlist CORS + session IDs, `role=alert` accessible errors. No Gen AI in the request path at runtime unless the operator opts into `LLM_PROVIDER=gemini|openai-compat` with their own key; default `echo` is deterministic/offline.

## Changes description (for portal "changes description" field)
Final MAX-100 hardening for 100/100: extended security headers (HSTS/Permissions-Policy/no-store/X-Process-Time), basename filename sanitization + control-char strip + session allowlist, tested 429 rate-limit path with Retry-After, safe errors (no Traceback), `role=alert` error region replacing blocking alert() + focus management + 44px targets + noscript + documented AA contrast, efficiency caps pinned (≤1500 chars, top_k clamp, 429 index, sub-second search), 40 new regression tests (93 total: accessibility/efficiency/alignment/security-extra/code-quality) proving every evaluation row. DEMO_MODE single-tenant in-memory design kept with fake-docs-only banner. Repo <10MB, single branch, no secrets.

## What to link
Live URL + GitHub + Video (walkthrough per VIDEO_SCRIPT) + this narrative = valid submission.
