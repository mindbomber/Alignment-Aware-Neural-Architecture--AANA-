FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY Dockerfile docker-compose.yml .dockerignore ./
COPY .github ./.github
COPY aana ./aana
COPY eval_pipeline ./eval_pipeline
COPY scripts ./scripts
COPY examples ./examples
COPY docs ./docs
COPY web ./web

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

RUN mkdir -p /app/eval_outputs/audit/docker

EXPOSE 8765

CMD ["python", "scripts/aana_server.py", "--host", "0.0.0.0", "--port", "8765", "--gallery", "examples/adapter_gallery.json", "--audit-log", "eval_outputs/audit/docker/aana-bridge.jsonl"]
