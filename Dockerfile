FROM python:3.14-alpine

ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system deps
RUN apk add --no-cache build-base libffi-dev openssl-dev git curl

# Install uv (Python package installer) and create the venv
RUN python -m pip install --upgrade pip && \
  python -m pip install --no-cache-dir uv

COPY pyproject.toml .

# Create and sync the virtualenv (.venv)
RUN uv venv --python python && \
  uv sync --no-dev

# Copy application code
COPY . .

# Make the virtualenv executables available
ENV PATH="/app/.venv/bin:$PATH"

# Expose the port Fly will map internally
EXPOSE 8090

# Bind to 0.0.0.0 and respect Fly's PORT env
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8090}"]
