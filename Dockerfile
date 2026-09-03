FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DAGSTER_HOME=/opt/dagster \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY defs ./defs
COPY workspace.yaml dagster.yaml ./
COPY docker/dagster-entrypoint.sh /usr/local/bin/dagster-entrypoint.sh

RUN uv sync --frozen --no-dev \
    && mkdir -p /opt/dagster /inbox \
    && cp dagster.yaml /opt/dagster/dagster.yaml \
    && chmod +x /usr/local/bin/dagster-entrypoint.sh

EXPOSE 3000

ENTRYPOINT ["dagster-entrypoint.sh"]
CMD ["dagster-webserver", "-h", "0.0.0.0", "-p", "3000", "-w", "workspace.yaml"]
