#!/bin/bash
set -e

# Configuration
PORTAINER_URL="http://192.168.7.10:9000"
PORTAINER_TOKEN="ptr_H9KdupIq3ZakdoGs5uueMzXf/TUwIe7oQXwmYCjCj2k="
STACK_NAME="jobspy-v2"

echo "🚀 Deploying JobSpy API to Portainer..."

# First, get the environment ID
echo "📋 Getting environment information..."
ENVIRONMENT_ID=$(curl -s -H "X-API-Key: $PORTAINER_TOKEN" \
  "$PORTAINER_URL/api/endpoints" | \
  jq -r '.[0].Id')

echo "   Environment ID: $ENVIRONMENT_ID"

# Check if stack already exists
echo "🔍 Checking for existing stack..."
EXISTING_STACK=$(curl -s -H "X-API-Key: $PORTAINER_TOKEN" \
  "$PORTAINER_URL/api/stacks" | \
  jq -r ".[] | select(.Name == \"$STACK_NAME\") | .Id" || echo "")

if [ ! -z "$EXISTING_STACK" ]; then
    echo "⚠️  Stack '$STACK_NAME' already exists (ID: $EXISTING_STACK)"
    echo "   Updating existing stack..."
    METHOD="PUT"
    URL_PATH="/api/stacks/$EXISTING_STACK"
else
    echo "✨ Creating new stack '$STACK_NAME'..."
    METHOD="POST"
    URL_PATH="/api/stacks/create"
fi

# Create the docker-compose content
cat > docker-compose.deploy.yml << 'EOF'
services:
  postgres:
    image: timescale/timescaledb:latest-pg15
    environment:
      - POSTGRES_DB=${POSTGRES_DB:-jobspy}
      - POSTGRES_USER=${POSTGRES_USER:-jobspy}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-jobspy_password}
      - TIMESCALEDB_TELEMETRY=off
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-jobspy} -d ${POSTGRES_DB:-jobspy}"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  jobspy-api:
    build: 
      context: https://github.com/gilby125/jobspy-api.git#main
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8787:8000"
    environment:
      # Database Configuration
      - DATABASE_URL=postgresql://${POSTGRES_USER:-jobspy}:${POSTGRES_PASSWORD:-jobspy_password}@postgres:5432/${POSTGRES_DB:-jobspy}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
      # Settings with defaults
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - ENABLE_API_KEY_AUTH=${ENABLE_API_KEY_AUTH:-false}
      - API_KEYS=${API_KEYS:-}
      - RATE_LIMIT_ENABLED=${RATE_LIMIT_ENABLED:-false}
      - DEFAULT_SITE_NAMES=${DEFAULT_SITE_NAMES:-indeed,linkedin,zip_recruiter,glassdoor}
      - DEFAULT_RESULTS_WANTED=${DEFAULT_RESULTS_WANTED:-20}
      - DEFAULT_DISTANCE=${DEFAULT_DISTANCE:-50}
      - DEFAULT_DESCRIPTION_FORMAT=${DEFAULT_DESCRIPTION_FORMAT:-markdown}
      - DEFAULT_COUNTRY_INDEED=${DEFAULT_COUNTRY_INDEED:-USA}
      - ENABLE_CACHE=${ENABLE_CACHE:-false}
      - CACHE_EXPIRY=${CACHE_EXPIRY:-3600}
      - ENVIRONMENT=${ENVIRONMENT:-production}
      - CORS_ORIGINS=${CORS_ORIGINS:-*}
      - ENABLE_HEALTH_ENDPOINTS=${ENABLE_HEALTH_ENDPOINTS:-true}
      - ENABLE_DETAILED_HEALTH=${ENABLE_DETAILED_HEALTH:-true}
      - ENABLE_SWAGGER_UI=${ENABLE_SWAGGER_UI:-true}
      - ENABLE_REDOC=${ENABLE_REDOC:-true}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 120s
      timeout: 5s
      retries: 3
      start_period: 10s

  celery-worker:
    build: 
      context: https://github.com/gilby125/jobspy-api.git#main
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      # Database Configuration
      - DATABASE_URL=postgresql://${POSTGRES_USER:-jobspy}:${POSTGRES_PASSWORD:-jobspy_password}@postgres:5432/${POSTGRES_DB:-jobspy}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
      # Settings
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - ENABLE_API_KEY_AUTH=${ENABLE_API_KEY_AUTH:-false}
      - API_KEYS=${API_KEYS:-}
      - DEFAULT_SITE_NAMES=${DEFAULT_SITE_NAMES:-indeed,linkedin,zip_recruiter,glassdoor}
      - DEFAULT_RESULTS_WANTED=${DEFAULT_RESULTS_WANTED:-20}
      - DEFAULT_DISTANCE=${DEFAULT_DISTANCE:-50}
      - DEFAULT_DESCRIPTION_FORMAT=${DEFAULT_DESCRIPTION_FORMAT:-markdown}
      - DEFAULT_COUNTRY_INDEED=${DEFAULT_COUNTRY_INDEED:-USA}
      - ENVIRONMENT=${ENVIRONMENT:-production}
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    command: >
      /bin/bash -c "cd /app && python -m celery -A app.celery_app worker --loglevel=info --concurrency=2"

  celery-beat:
    build: 
      context: https://github.com/gilby125/jobspy-api.git#main
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      # Database Configuration
      - DATABASE_URL=postgresql://${POSTGRES_USER:-jobspy}:${POSTGRES_PASSWORD:-jobspy_password}@postgres:5432/${POSTGRES_DB:-jobspy}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
      # Settings
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - ENVIRONMENT=${ENVIRONMENT:-production}
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    command: >
      /bin/bash -c "cd /app && python -m celery -A app.celery_app beat --loglevel=info"

volumes:
  postgres_data:
  redis_data:
EOF

# Read the compose file content and escape it for JSON
COMPOSE_CONTENT=$(cat docker-compose.deploy.yml)

# Create the JSON payload
if [ "$METHOD" = "POST" ]; then
    # Creating new stack
    JSON_PAYLOAD=$(jq -n \
        --arg name "$STACK_NAME" \
        --arg compose "$COMPOSE_CONTENT" \
        --arg endpointId "$ENVIRONMENT_ID" \
        '{
            "Name": $name,
            "StackFileContent": $compose,
            "EndpointId": ($endpointId | tonumber)
        }')
else
    # Updating existing stack
    JSON_PAYLOAD=$(jq -n \
        --arg compose "$COMPOSE_CONTENT" \
        --arg endpointId "$ENVIRONMENT_ID" \
        '{
            "StackFileContent": $compose,
            "EndpointId": ($endpointId | tonumber)
        }')
fi

# Deploy the stack
echo "📦 Deploying stack..."
RESPONSE=$(curl -s -w "%{http_code}" -X $METHOD \
    -H "X-API-Key: $PORTAINER_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$JSON_PAYLOAD" \
    "$PORTAINER_URL$URL_PATH?endpointId=$ENVIRONMENT_ID")

HTTP_CODE="${RESPONSE: -3}"
BODY="${RESPONSE%???}"

if [[ $HTTP_CODE =~ ^2[0-9][0-9]$ ]]; then
    echo "✅ Stack deployed successfully!"
    echo "   HTTP Status: $HTTP_CODE"
    echo "🌐 JobSpy API should be available at: http://192.168.7.10:8787"
    echo "📚 API Documentation: http://192.168.7.10:8787/docs"
    echo "🔧 Admin Panel: http://192.168.7.10:8787/admin/"
    echo ""
    echo "🔍 Check deployment status in Portainer: $PORTAINER_URL"
else
    echo "❌ Deployment failed!"
    echo "   HTTP Status: $HTTP_CODE"
    echo "   Response: $BODY"
    exit 1
fi

# Clean up
rm -f docker-compose.deploy.yml