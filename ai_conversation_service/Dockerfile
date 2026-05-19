# Use Python 3.9 slim image (matching projects service)
FROM python:3.9-slim

# Install git (required for git dependencies if any)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY . /app

WORKDIR /app

# Install dependencies
RUN uv sync --frozen --no-cache

CMD ["/app/.venv/bin/uvicorn", "src.ai_conversation_service.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Install the project
RUN uv sync --frozen --no-dev

# Create non-root user
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application
CMD ["uv", "run", "src/ai_conversation_service/main.py"]