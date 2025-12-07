FROM python:3.14-alpine AS builder

ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Install native build tools and git so uv can compile/build as needed
RUN apk add --no-cache --update build-base libffi-dev openssl-dev git curl

# Install uv (fast package manager) into the builder image and use it to create
# and populate the project virtualenv based on pyproject.toml
RUN python -m pip install --upgrade pip
RUN python -m pip install --no-cache-dir uv
COPY pyproject.toml ./

# Create the virtualenv (uv uses .venv) and sync the project environment
RUN uv venv --python python && \
  uv sync

FROM python:3.14-alpine
WORKDIR /app
COPY --from=builder /app/.venv .venv/
COPY . .

# Install curl in the final image (alpine) to support things like health checks
RUN apk add --no-cache curl

# Use uvicorn (uv) from the virtualenv to run the FastAPI app
# Assumes your application creates a FastAPI app named `app` in `main.py`.
EXPOSE 8090
CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8090"]
