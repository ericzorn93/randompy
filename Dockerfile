FROM python:3.14-alpine AS builder

ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install build-time system deps
RUN apk add --no-cache build-base libffi-dev openssl-dev git curl

# Install uv and create the virtualenv + install deps
RUN python -m pip install --upgrade pip && \
  python -m pip install --no-cache-dir uv

COPY pyproject.toml .

# Create and sync the virtualenv (.venv) inside the builder stage
RUN uv venv --python python && \
  uv sync --no-dev

# Copy application code into builder (so dependencies that rely on source are available)
COPY . .


FROM python:3.14-alpine AS runtime

ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install only runtime libraries (smaller than build deps)
RUN apk add --no-cache libffi openssl

# Copy the application and the prepared virtualenv from the builder stage
COPY --from=builder /app /app

# Make the virtualenv executables available
ENV PATH="/app/.venv/bin:$PATH"

# Expose the port Fly will map internally
EXPOSE 8090

# Bind to 0.0.0.0 and respect Fly's PORT env
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8090}"]
