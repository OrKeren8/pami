FROM python:3.12-slim

# Install git (required for git dependencies if any)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY . /app

WORKDIR /app

# Install dependencies
# --frozen so the image is built from uv.lock: without it the same commit resolves a
# different dependency tree on a later build.
RUN uv sync --frozen --no-cache

CMD ["/app/.venv/bin/uvicorn", "src.projects_service.main:app", "--host", "0.0.0.0", "--port", "8000"]