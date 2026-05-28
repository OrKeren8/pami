# Use Python 3.9 slim image (matching projects service)
FROM python:3.9-slim

# Install git (required for git dependencies if any)
RUN apt-get update && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*

# Copy helper uv binary image (keeps build fast in this repo)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy app
COPY . /app
WORKDIR /app

# Install dependencies
RUN uv sync --frozen --no-cache

# Create non-root user and set permissions
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expose the service port used by the task definition
EXPOSE 8001

# Healthcheck: ensure the container responds on the same port
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application with uv runner on port 8001
CMD ["uv", "run", "src/ai_conversation_service/main.py", "--host", "0.0.0.0", "--port", "8001"]