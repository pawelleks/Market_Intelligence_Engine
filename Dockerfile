# Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install build essential for compiling some python packages if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY run_api.py .
COPY api_server.py .
COPY make_admin.py .
# Copy config (will be overridden by volume in docker-compose, but good for build)
COPY config/ ./config/
# Copy prompts (required for AI features)
COPY prompts/ ./prompts/
# Copy CLI scripts for orchestrator execution
COPY cli/ ./cli/
RUN chmod +x cli/orchestrator.sh

# Ensure src is in python path
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# Expose API port
EXPOSE 8000

# Run API
CMD ["python", "run_api.py"]
