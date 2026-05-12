FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV AANA_BRIDGE_HOST=0.0.0.0
ENV AANA_BRIDGE_PORT=8765
ENV AANA_ADAPTER_GALLERY=examples/adapter_gallery.json
ENV AANA_AUDIT_LOG=eval_outputs/audit/docker/aana-fastapi.jsonl
ENV AANA_MAX_REQUEST_BYTES=1048576
ENV AANA_RATE_LIMIT_PER_MINUTE=60
ENV AANA_BRIDGE_TOKEN_SCOPES=pre_tool_check,agent_check,workflow_check,workflow_batch,validation,aix_audit,durable_audit_storage,human_review_export,live_monitoring,enterprise_connectors,enterprise_live_connectors,enterprise_demo,mlcommons_aix_report,production_candidate_profile,production_candidate_check
ENV AANA_EVIDENCE_REGISTRY=examples/evidence_registry.json
ENV AANA_PRODUCTION_CANDIDATE_PROFILE=examples/production_candidate_profile_enterprise_support.json
ENV AANA_LIVE_CONNECTOR_CONFIG=examples/enterprise_support_live_connectors.json
ENV AANA_LIVE_MONITORING_CONFIG=examples/live_monitoring_metrics.json

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
    && python -m pip install --no-cache-dir ".[api]"

RUN addgroup --system aana \
    && adduser --system --ingroup aana --uid 10001 aana \
    && mkdir -p /app/eval_outputs/audit/docker \
    && chown -R aana:aana /app/eval_outputs

USER 10001

EXPOSE 8765

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=6 \
    CMD python -c "import json, os, urllib.request; port=os.environ.get('AANA_BRIDGE_PORT','8765'); data=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/ready', timeout=5)); raise SystemExit(0 if data.get('status') == 'ok' else 1)"

CMD ["/bin/sh", "-c", "mkdir -p \"$(dirname \"$AANA_AUDIT_LOG\")\" && aana-fastapi --host \"$AANA_BRIDGE_HOST\" --port \"$AANA_BRIDGE_PORT\" --gallery \"$AANA_ADAPTER_GALLERY\" --audit-log \"$AANA_AUDIT_LOG\" --rate-limit-per-minute \"$AANA_RATE_LIMIT_PER_MINUTE\" --max-request-bytes \"$AANA_MAX_REQUEST_BYTES\""]
