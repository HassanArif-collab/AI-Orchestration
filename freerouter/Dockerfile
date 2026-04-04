# FreeRouter v3 Dockerfile (optional — not required for local development)
#
# This project is designed to run with Python directly:
#   pip install -e .
#   python -m freerouter
#
# Only use Docker if you need containerized deployment.

FROM python:3.11-slim

LABEL maintainer="FreeRouter Team"
LABEL description="LiteLLM-based task router v3"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY pyproject.toml .
RUN pip install -e .

EXPOSE 4000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:4000/health || exit 1

CMD ["python", "-m", "freerouter"]
