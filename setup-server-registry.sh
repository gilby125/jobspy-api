#!/bin/bash
set -e

# Configuration - REPLACE WITH YOUR SERVER IP
SERVER_IP="${1:-192.168.7.10}"  # Default to your server IP, or pass as first argument
REGISTRY_PORT="5000"
REGISTRY_URL="${SERVER_IP}:${REGISTRY_PORT}"
IMAGE_NAME="jobspy-api"
IMAGE_TAG="latest"

echo "🚀 Setting up Docker registry on server ${SERVER_IP}..."

# Step 1: Deploy registry on server (run this on the server)
echo "📋 To set up the registry on your server (${SERVER_IP}), run these commands on the server:"
echo ""
echo "# 1. Create directory and copy files"
echo "mkdir -p ~/docker-registry && cd ~/docker-registry"
echo ""
echo "# 2. Copy these files to the server:"
echo "# - docker-compose.server-registry.yml"
echo "# - registry-config.yml"
echo ""
echo "# 3. Start the registry"
echo "docker-compose -f docker-compose.server-registry.yml up -d"
echo ""
echo "# 4. Verify registry is running"
echo "curl http://localhost:5000/v2/_catalog"
echo ""

# Step 2: Configure Docker to use insecure registry (for local development)
echo "🔧 Configuring Docker for insecure registry..."

# Check if Docker daemon.json exists
DOCKER_CONFIG="/etc/docker/daemon.json"
if [ -f "$DOCKER_CONFIG" ]; then
    echo "📝 Docker daemon.json already exists, you may need to manually add:"
else
    echo "📝 Creating Docker daemon.json..."
    sudo mkdir -p /etc/docker
fi

echo "Add this to your Docker daemon.json on BOTH your local machine AND the server:"
echo "{"
echo "  \"insecure-registries\": [\"${REGISTRY_URL}\"]"
echo "}"
echo ""
echo "Then restart Docker: sudo systemctl restart docker"
echo ""

# Step 3: Build and tag image
echo "🔨 Building and tagging image for server registry..."
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}

echo "📤 Ready to push to server registry..."
echo "Run this after setting up the registry on the server:"
echo "docker push ${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}"
echo ""

# Step 4: Create updated Portainer compose file
echo "📄 Creating Portainer compose file for server registry..."
cat > docker-compose.portainer-registry.yml << EOF
services:
  postgres:
    image: timescale/timescaledb:latest-pg15
    container_name: jobspy-postgres
    environment:
      - POSTGRES_DB=\${POSTGRES_DB:-jobspy}
      - POSTGRES_USER=\${POSTGRES_USER:-jobspy}
      - POSTGRES_PASSWORD=\${POSTGRES_PASSWORD:-jobspy_password}
      - TIMESCALEDB_TELEMETRY=off
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/init:/docker-entrypoint-initdb.d
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \${POSTGRES_USER:-jobspy} -d \${POSTGRES_DB:-jobspy}"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    container_name: jobspy-redis
    volumes:
      - redis_data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

  jobspy-api:
    image: ${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}
    container_name: jobspy-docker-api
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    ports:
      - "8787:8000"
    environment:
      # Database Configuration
      - DATABASE_URL=postgresql://\${POSTGRES_USER:-jobspy}:\${POSTGRES_PASSWORD:-jobspy_password}@postgres:5432/\${POSTGRES_DB:-jobspy}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
      # Settings with defaults
      - LOG_LEVEL=\${LOG_LEVEL:-INFO}
      - ENABLE_API_KEY_AUTH=\${ENABLE_API_KEY_AUTH:-false}
      - API_KEYS=\${API_KEYS:-}
      - RATE_LIMIT_ENABLED=\${RATE_LIMIT_ENABLED:-false}
      - DEFAULT_SITE_NAMES=\${DEFAULT_SITE_NAMES:-indeed,linkedin,zip_recruiter,glassdoor}
      - DEFAULT_RESULTS_WANTED=\${DEFAULT_RESULTS_WANTED:-20}
      - DEFAULT_DISTANCE=\${DEFAULT_DISTANCE:-50}
      - DEFAULT_DESCRIPTION_FORMAT=\${DEFAULT_DESCRIPTION_FORMAT:-markdown}
      - DEFAULT_COUNTRY_INDEED=\${DEFAULT_COUNTRY_INDEED:-USA}
      - ENABLE_CACHE=\${ENABLE_CACHE:-false}
      - CACHE_EXPIRY=\${CACHE_EXPIRY:-3600}
      - ENVIRONMENT=\${ENVIRONMENT:-production}
      - CORS_ORIGINS=\${CORS_ORIGINS:-*}
      - ENABLE_HEALTH_ENDPOINTS=\${ENABLE_HEALTH_ENDPOINTS:-true}
      - ENABLE_DETAILED_HEALTH=\${ENABLE_DETAILED_HEALTH:-true}
      - ENABLE_SWAGGER_UI=\${ENABLE_SWAGGER_UI:-true}
      - ENABLE_REDOC=\${ENABLE_REDOC:-true}
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 120s
      timeout: 5s
      retries: 3
      start_period: 10s

  celery-worker:
    image: ${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}
    container_name: jobspy-celery-worker
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      # Database Configuration
      - DATABASE_URL=postgresql://\${POSTGRES_USER:-jobspy}:\${POSTGRES_PASSWORD:-jobspy_password}@postgres:5432/\${POSTGRES_DB:-jobspy}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
      # Settings
      - LOG_LEVEL=\${LOG_LEVEL:-INFO}
      - ENABLE_API_KEY_AUTH=\${ENABLE_API_KEY_AUTH:-false}
      - API_KEYS=\${API_KEYS:-}
      - DEFAULT_SITE_NAMES=\${DEFAULT_SITE_NAMES:-indeed,linkedin,zip_recruiter,glassdoor}
      - DEFAULT_RESULTS_WANTED=\${DEFAULT_RESULTS_WANTED:-20}
      - DEFAULT_DISTANCE=\${DEFAULT_DISTANCE:-50}
      - DEFAULT_DESCRIPTION_FORMAT=\${DEFAULT_DESCRIPTION_FORMAT:-markdown}
      - DEFAULT_COUNTRY_INDEED=\${DEFAULT_COUNTRY_INDEED:-USA}
      - ENVIRONMENT=\${ENVIRONMENT:-production}
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    command: >
      /bin/bash -c "cd /app && python -m celery -A app.celery_app worker --loglevel=info --concurrency=2"

  celery-beat:
    image: ${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}
    container_name: jobspy-celery-beat
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    environment:
      # Database Configuration
      - DATABASE_URL=postgresql://\${POSTGRES_USER:-jobspy}:\${POSTGRES_PASSWORD:-jobspy_password}@postgres:5432/\${POSTGRES_DB:-jobspy}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
      # Settings
      - LOG_LEVEL=\${LOG_LEVEL:-INFO}
      - ENVIRONMENT=\${ENVIRONMENT:-production}
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
    command: >
      /bin/bash -c "cd /app && python -m celery -A app.celery_app beat --loglevel=info"

volumes:
  postgres_data:
  redis_data:
EOF

echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Set up registry on server ${SERVER_IP}"
echo "2. Configure Docker for insecure registries"
echo "3. Push image: docker push ${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}"
echo "4. Use docker-compose.portainer-registry.yml in Portainer"
echo ""
echo "🔗 Registry will be available at: http://${SERVER_IP}:5000"
echo "📦 Image will be: ${REGISTRY_URL}/${IMAGE_NAME}:${IMAGE_TAG}"