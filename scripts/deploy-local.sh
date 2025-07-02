#!/bin/bash
# Local deployment script for JobSpy API
# Use this when Portainer webhook is not accessible from internet

set -e

echo "🚀 Starting local deployment..."

# Configuration
DOCKER_HUB_USERNAME="${DOCKER_HUB_USERNAME:-yourusername}"
IMAGE_NAME="jobspy-api"
COMPOSE_FILE="docker-compose.yml"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check if docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker is not running${NC}"
        exit 1
    fi
}

# Function to pull latest image
pull_latest() {
    echo -e "${YELLOW}📥 Pulling latest image from Docker Hub...${NC}"
    docker pull ${DOCKER_HUB_USERNAME}/${IMAGE_NAME}:latest
}

# Function to update local deployment
deploy_local() {
    echo -e "${YELLOW}🔄 Updating local deployment...${NC}"
    
    # Stop existing containers
    docker-compose down
    
    # Start with new image
    docker-compose up -d
    
    # Wait for health check
    echo -e "${YELLOW}⏳ Waiting for services to be healthy...${NC}"
    sleep 10
    
    # Check health
    if curl -f http://localhost:8787/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Deployment successful!${NC}"
        echo -e "${GREEN}📊 API is running at: http://localhost:8787${NC}"
        echo -e "${GREEN}📚 Docs available at: http://localhost:8787/docs${NC}"
    else
        echo -e "${RED}❌ Health check failed${NC}"
        echo "Checking logs..."
        docker-compose logs --tail=50 jobspy-api
        exit 1
    fi
}

# Function to watch for GitHub updates
watch_github() {
    echo -e "${YELLOW}👀 Watching for GitHub updates...${NC}"
    echo "This will check for new pushes to main branch every 5 minutes"
    echo "Press Ctrl+C to stop"
    
    LAST_COMMIT=""
    
    while true; do
        # Get latest commit from GitHub
        CURRENT_COMMIT=$(git ls-remote origin main | cut -f1)
        
        if [ "$LAST_COMMIT" != "$CURRENT_COMMIT" ] && [ -n "$LAST_COMMIT" ]; then
            echo -e "${GREEN}🔔 New commit detected: ${CURRENT_COMMIT:0:7}${NC}"
            git pull origin main
            pull_latest
            deploy_local
        fi
        
        LAST_COMMIT=$CURRENT_COMMIT
        sleep 300 # Check every 5 minutes
    done
}

# Main script
main() {
    check_docker
    
    case "${1:-deploy}" in
        deploy)
            pull_latest
            deploy_local
            ;;
        watch)
            watch_github
            ;;
        pull)
            pull_latest
            ;;
        *)
            echo "Usage: $0 [deploy|watch|pull]"
            echo "  deploy - Pull latest and deploy (default)"
            echo "  watch  - Watch GitHub for updates and auto-deploy"
            echo "  pull   - Only pull latest image"
            exit 1
            ;;
    esac
}

main "$@"