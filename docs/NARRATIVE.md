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
AI-assisted boilerplate (FastAPI wiring, clause regex, TF-IDF + fallback, vanilla JS fetch handlers, pytest skeletons), then human-engineered trust logic: citation schema with `score` + renderer, exact refusal + hard override, disclaimer everywhere, prompt Rules 1-5 with delimiters, zero-overlap filter + stop_words=english + cached TF-IDF index (Lock, 6-12x) + headers (HSTS/Permissions-Policy/no-store/X-Process-Time) + DEMO guard (session fallback, prod false closes leak), score-calibrated confidence (max >=0.18 + count fallback), Pydantic bounds, magic pre-parse + basename sanitization, bounded index, allowlist CORS/session IDs, `role=alert` errors. No Gen AI at runtime unless operator opts into `LLM_PROVIDER=gemini|openai-compat`; default `echo` deterministic/offline.

## Changes description (for portal "changes description" field)
Final Attempt3 MAX hardening for 100/100: cached TF-IDF index (fit once + query transform, Lock, 6-12x) + stop_words=english + _overlap_search helper (France/banana/stopword-only -> Cannot Determine), extended headers (HSTS/Permissions-Policy/COOP/X-Permitted/no-store/X-Process-Time), DEMO guard matrix (session fallback; prod DEMO_MODE=false -> []), basename sanitization + 429/Retry-After + role=alert + 44px + noscript + AA, 101 green (97 +4 fixforward: stopword/DEMO-guard/cache-repeat) proving every row. Single branch, <10MB, no secrets, fake-docs-only banner.

## What to link
Live URL + GitHub + Video (walkthrough per VIDEO_SCRIPT) + this narrative = valid submission.
