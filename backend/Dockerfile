FROM python:3.12-slim

# Pull in Debian security fixes newer than the base image.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /uvx /bin/

# Set the working directory
WORKDIR /app

# Build context is the repository root: this is a uv workspace, so the root
# manifest and the single lockfile are needed to resolve the backend member.
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml ./backend/
COPY packages ./packages

# Install dependencies for the backend member only
RUN uv sync --frozen --no-cache --package backend

# Copy the application code
COPY backend/app ./backend/app

# Run the application
CMD ["uv", "run", "--package", "backend", "fastapi", "run", "--host", "0.0.0.0", "--port", "8000", "backend/app/main.py"]
