# FreeRouter Dockerfile
# Build: docker build -t freerouter .
# Run: docker run -p 4000:4000 --env-file .env freerouter

FROM python:3.11-slim

LABEL maintainer="FreeRouter Team"
LABEL description="Smart LLM proxy that always prefers free models"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY pyproject.toml .

# Install the package
RUN pip install -e .

# Create non-root user for security
RUN useradd -m -u 1000 freerouter && \
    chown -R freerouter:freerouter /app
USER freerouter

# Expose the proxy port
EXPOSE 4000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:4000/health || exit 1

# Default command
CMD ["freerouter", "start", "--host", "0.0.0.0", "--port", "4000"]