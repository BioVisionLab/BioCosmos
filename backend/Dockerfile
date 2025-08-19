FROM python:3.12-slim

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory
WORKDIR /app

# Copy dependency configuration files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-cache

# Copy the application code
COPY app ./app

# Run the application
CMD ["uv", "run", "--host", "0.0.0.0", "--port", "80", "fastapi", "run", "app/main.py"]