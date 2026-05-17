# BOS Agent — Phase A image.
#
# Independent service. Talks to BOS Core (port 8000) over HTTP only.
# Does NOT import app.* (enforced by agent/tests/test_isolation.py).
#
# Build context: the repo root (so we can COPY backend/agent).
#   docker build -f backend/agent/Dockerfile -t bos-agent:phase-a .
# Run:
#   docker run --rm -p 8001:8001 \
#     -e BOS_CORE_URL=http://localhost:8000/api/v1 \
#     -e AGENT_ROUTER_USE_LLM=0 \
#     bos-agent:phase-a

# ---- Stage 1: install agent dependencies into a wheelhouse layer ----
FROM python:3.11-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/agent/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: runtime ----
FROM python:3.11-slim AS runtime

LABEL maintainer="BOS Platform Team"
LABEL service="bos-agent"
LABEL phase="A"

WORKDIR /srv

# Copy installed wheels.
COPY --from=builder /install /usr/local

# Copy ONLY the agent tree. Refusing to copy app/* enforces the
# architectural isolation rule at the image layer too.
COPY backend/agent /srv/agent

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BOS_CORE_URL=http://bos-core:8000/api/v1 \
    AGENT_HOST=0.0.0.0 \
    AGENT_PORT=8001 \
    AGENT_LOG_LEVEL=info

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request,sys; \
        sys.exit(0 if urllib.request.urlopen('http://localhost:8001/agent/health',timeout=2).status==200 else 1)"

CMD ["python", "-m", "agent.main", "--host", "0.0.0.0", "--port", "8001"]
