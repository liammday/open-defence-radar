# Build the wheel with uv, then install it into a clean slim runtime image.
# The wheel bundles the web templates + static assets (incl. self-hosted fonts),
# so the runtime image needs neither the source tree nor uv.
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv build --wheel --out-dir /dist

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Bind to all interfaces inside the container; store lives on a mounted volume.
ENV ODR_WEB_HOST=0.0.0.0 \
    ODR_WEB_PORT=8000 \
    ODR_DB_PATH=/app/data/odr.sqlite3 \
    ODR_EVAL_DIR=/app/data/eval
EXPOSE 8000

# Liveness probe hits the app's own /healthz (no extra tooling needed).
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/healthz').getcode()==200 else 1)"

CMD ["odr-web"]
