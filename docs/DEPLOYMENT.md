# Deployment — any host works, Cloud Run suggested for Google bonus

MVP is a single FastAPI app serving API + static frontend. No build step, no disk writes.

## Option A: Cloud Run (bonus + easiest prod)

```bash
gcloud run deploy legal-aid-mvp --source . --port 8080 --allow-unauthenticated --set-env-vars LLM_PROVIDER=echo
# with Gemini:
gcloud run deploy legal-aid-mvp --source . --set-env-vars LLM_PROVIDER=gemini,GEMINI_API_KEY=...,GEMINI_MODEL=gemini-2.0-flash
```

Why: Dockerfile honours `$PORT`, stateless (in-memory index per instance — fine for demo/video).

## Option B: Render / Railway / Fly

- Build: `pip install -r requirements.txt`
- Start: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
- Env: `LLM_PROVIDER=echo` (or gemini/openai-compat keys).

## Option C: Vercel (Python)

- Keep `backend/app/main.py` as the entry; add `vercel.json` routing `/ -> backend/app/main.py` if needed.
- Note: serverless cold starts clear in-memory docs — re-upload per session (call out in video).

## Prod hardening (post-MVP)

- CORS is secure-by-default (no middleware unless `FRONTEND_ORIGIN`/`ALLOWED_ORIGINS` set — never `*`). For cross-origin prod: `--set-env-vars FRONTEND_ORIGIN=https://your-app.run.app`.
- Security headers on (nosniff/DENY/no-referrer/CSP) + non-root Docker + HEALTHCHECK `/health`.
- Upload DoS-safe: extension + size + `%PDF-` magic pre-parse, pages post-parse, bounded index (`MAX_STORE_CHUNKS`, 429 when full), bounded `doc_ids`/`top_k`.
- Add Redis/pgvector for shared index across instances.
- Add auth + per-user doc isolation (current MVP is single-tenant demo).
- Add rate limiting + request logging (no PII).
- Set `MAX_CHUNKS` + page caps per plan tier.
