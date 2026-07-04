FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ovriq/ ovriq/
RUN useradd -r -u 10001 ovriq && mkdir -p /data && chown ovriq /data
USER ovriq
ENV OVRIQ_JOURNAL_PATH=/data/journal.jsonl
EXPOSE 8642
HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8642/health')"
CMD ["python", "-m", "uvicorn", "ovriq.api.server:app", "--host", "0.0.0.0", "--port", "8642"]
