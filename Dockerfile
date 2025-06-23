FROM python:3.13-slim

WORKDIR /app

LABEL maintainer="Shannon Atkinson <rainmanjam@gmail.com>"
LABEL description="JobSpy Docker API - Job search across multiple platforms"

# Use ARG instead of ENV for settings that should be overridable
ARG API_KEY_HEADER_NAME=x-api-key
ARG ENABLE_API_KEY_AUTH=false
ARG API_KEYS=""
ARG RATE_LIMIT_ENABLED=false
ARG RATE_LIMIT_REQUESTS=100
ARG RATE_LIMIT_TIMEFRAME=3600
ARG DEFAULT_SITE_NAMES=indeed,linkedin,zip_recruiter,glassdoor,google,bayt,naukri
ARG DEFAULT_PROXIES=""
ARG DEFAULT_RESULTS_WANTED=20
ARG DEFAULT_DISTANCE=50
ARG DEFAULT_DESCRIPTION_FORMAT=markdown
ARG ENABLE_CACHE=false
ARG CACHE_EXPIRY=3600
ARG LOG_LEVEL=DEBUG
ARG ENVIRONMENT=production
ARG CORS_ORIGINS=*
ARG ENABLE_HEALTH_ENDPOINTS=true
ARG ENABLE_DETAILED_HEALTH=true
ARG ENABLE_SWAGGER_UI=true
ARG ENABLE_REDOC=true
ARG SWAGGER_UI_PATH=/docs
ARG REDOC_PATH=/redoc

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    # Convert ARGs to ENVs
    API_KEY_HEADER_NAME=${API_KEY_HEADER_NAME} \
    ENABLE_API_KEY_AUTH=${ENABLE_API_KEY_AUTH} \
    API_KEYS=${API_KEYS} \
    RATE_LIMIT_ENABLED=${RATE_LIMIT_ENABLED} \
    RATE_LIMIT_REQUESTS=${RATE_LIMIT_REQUESTS} \
    RATE_LIMIT_TIMEFRAME=${RATE_LIMIT_TIMEFRAME} \
    DEFAULT_SITE_NAMES=${DEFAULT_SITE_NAMES} \
    DEFAULT_PROXIES=${DEFAULT_PROXIES} \
    DEFAULT_RESULTS_WANTED=${DEFAULT_RESULTS_WANTED} \
    DEFAULT_DISTANCE=${DEFAULT_DISTANCE} \
    DEFAULT_DESCRIPTION_FORMAT=${DEFAULT_DESCRIPTION_FORMAT} \
    ENABLE_CACHE=${ENABLE_CACHE} \
    CACHE_EXPIRY=${CACHE_EXPIRY} \
    LOG_LEVEL=${LOG_LEVEL} \
    ENVIRONMENT=${ENVIRONMENT} \
    CORS_ORIGINS=${CORS_ORIGINS} \
    ENABLE_HEALTH_ENDPOINTS=${ENABLE_HEALTH_ENDPOINTS} \
    ENABLE_DETAILED_HEALTH=${ENABLE_DETAILED_HEALTH} \
    ENABLE_SWAGGER_UI=${ENABLE_SWAGGER_UI} \
    ENABLE_REDOC=${ENABLE_REDOC} \
    SWAGGER_UI_PATH=${SWAGGER_UI_PATH} \
    REDOC_PATH=${REDOC_PATH}

# Install curl and build-essential for healthcheck and required dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install python-json-logger

# Copy application code
COPY . .
# Explicitly ensure app directory exists and has content
RUN ls -la /app && ls -la /app/app || echo "app directory missing - copying explicitly"
COPY app/ /app/app/

# Create logs directory
RUN mkdir -p logs

# Make all scripts executable
RUN find /app/scripts -type f -name "*.sh" -exec chmod +x {} \; && \
    find /app/scripts -type f -name "*.py" -exec chmod +x {} \; && \
    chmod +x /app/scripts/confirm_env.sh /app/scripts/debug_env_load_order.sh

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the confirmation script and then start the application
CMD ["/bin/bash", "-c", "/app/scripts/confirm_env.sh && cd /app && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
