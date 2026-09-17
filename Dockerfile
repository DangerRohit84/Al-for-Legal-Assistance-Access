# Cloud Run ready: stateless, PORT-driven, no local disk assumptions.
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY frontend ./frontend
# Least privilege: run as non-root.
RUN useradd -m app && chown -R app:app /app
USER app
ENV PORT=8080 LLM_PROVIDER=echo DEMO_MODE=true
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:'+os.getenv('PORT','8080')+'/health')"
CMD exec uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT}
