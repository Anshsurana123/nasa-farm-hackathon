# syntax=docker/dockerfile:1
FROM python:3.11-slim

WORKDIR /app

# Install curl and system tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv package manager
ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

# Copy project definition and packages
COPY pyproject.toml uv.lock ./
COPY packages ./packages
COPY apps/api ./apps/api
COPY data/golden ./data/golden
COPY data/benchmarks ./data/benchmarks

# Install all workspace packages in virtual environment
RUN uv sync --frozen --no-dev

# Expose API port
EXPOSE 8000

ENV PORT=8000
ENV HOST=0.0.0.0

CMD ["sh", "-c", "uv run uvicorn terraloop_api.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --app-dir apps/api"]
