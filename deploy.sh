#!/bin/bash

# JobSpy API Deployment Script
# Streamlined deployment with testing and verification

set -e

echo "🚀 JobSpy API Deployment Script"
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEPLOYMENT_URL="http://192.168.7.10:8787"
LOCAL_URL="http://localhost:8787"
MAX_WAIT_TIME=300  # 5 minutes
CHECK_INTERVAL=10   # 10 seconds

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if API is responding
check_api_health() {
    local url=$1
    local timeout=${2:-5}
    
    if curl -s --max-time $timeout "$url/health" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Function to wait for API to be ready
wait_for_api() {
    local url=$1
    local max_wait=$2
    local check_interval=$3
    
    print_status "Waiting for API at $url to be ready..."
    
    local elapsed=0
    while [ $elapsed -lt $max_wait ]; do
        if check_api_health "$url"; then
            print_success "API is responding at $url"
            return 0
        fi
        
        echo -n "."
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
    done
    
    print_error "API at $url failed to respond within ${max_wait} seconds"
    return 1
}

# Function to run comprehensive tests
run_tests() {
    print_status "Running comprehensive tests..."
    
    # Test local development environment first
    if check_api_health "$LOCAL_URL"; then
        print_success "Local API is healthy"
        
        # Run Python tests if pytest is available
        if command -v pytest >/dev/null 2>&1; then
            if python -m pytest tests/ -v --tb=short; then
                print_success "All tests passed"
            else
                print_error "Some tests failed"
                return 1
            fi
        else
            print_warning "pytest not installed, skipping unit tests"
            print_status "Running basic syntax checks instead..."
            
            # Basic syntax check on key files
            if python -m py_compile app/main.py app/routes/admin.py; then
                print_success "Syntax checks passed"
            else
                print_error "Syntax errors found"
                return 1
            fi
        fi
    else
        print_warning "Local API not running, skipping tests"
    fi
}

# Function to verify deployment
verify_deployment() {
    local url=$1
    
    print_status "Verifying deployment at $url..."
    
    # Check health endpoint
    if ! check_api_health "$url"; then
        print_error "Health check failed"
        return 1
    fi
    
    # Check specific endpoints
    local endpoints=(
        "/docs"
        "/admin/"
        "/admin/analytics"
    )
    
    for endpoint in "${endpoints[@]}"; do
        print_status "Testing endpoint: $endpoint"
        if curl -s --max-time 10 "$url$endpoint" >/dev/null; then
            print_success "✓ $endpoint"
        else
            print_warning "⚠ $endpoint may have issues"
        fi
    done
    
    # Check database connectivity
    print_status "Testing database connectivity..."
    if curl -s --max-time 10 "$url/admin/api/stats" >/dev/null; then
        print_success "✓ Database connectivity"
    else
        print_warning "⚠ Database connectivity issues"
    fi
    
    print_success "Deployment verification completed"
}

# Main deployment process
main() {
    print_status "Starting deployment process..."
    
    # Step 1: Run tests locally
    print_status "Step 1: Running local tests"
    if ! run_tests; then
        print_error "Tests failed, aborting deployment"
        exit 1
    fi
    
    # Step 2: Check current git status
    print_status "Step 2: Checking git status"
    if [ -n "$(git status --porcelain)" ]; then
        print_warning "Working directory has uncommitted changes:"
        git status --short
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_error "Deployment aborted"
            exit 1
        fi
    fi
    
    # Step 3: Push to main branch
    print_status "Step 3: Pushing to main branch"
    if git push origin main; then
        print_success "Code pushed to main branch"
    else
        print_error "Failed to push code"
        exit 1
    fi
    
    # Step 4: Wait for Portainer to detect and deploy
    print_status "Step 4: Waiting for Portainer deployment (polling interval)"
    print_status "This may take a few minutes..."
    
    # Give Portainer time to detect the change and start deployment
    sleep 30
    
    # Step 5: Wait for deployment to complete
    print_status "Step 5: Waiting for deployment to complete"
    if wait_for_api "$DEPLOYMENT_URL" $MAX_WAIT_TIME $CHECK_INTERVAL; then
        print_success "Deployment completed successfully"
    else
        print_error "Deployment failed or timed out"
        print_status "Check Portainer logs for details"
        exit 1
    fi
    
    # Step 6: Verify deployment
    print_status "Step 6: Verifying deployment"
    if verify_deployment "$DEPLOYMENT_URL"; then
        print_success "✅ Deployment verification passed"
    else
        print_warning "⚠ Deployment verification had issues"
    fi
    
    # Step 7: Show final status
    print_success "🎉 Deployment completed successfully!"
    echo
    print_status "Deployment URL: $DEPLOYMENT_URL"
    print_status "Admin Interface: $DEPLOYMENT_URL/admin/"
    print_status "API Documentation: $DEPLOYMENT_URL/docs"
    print_status "Analytics: $DEPLOYMENT_URL/admin/analytics"
    echo
    print_status "To monitor the deployment:"
    echo "  - Check Portainer dashboard"
    echo "  - Monitor container logs"
    echo "  - Test API endpoints"
}

# Handle script arguments
case "${1:-}" in
    "test")
        print_status "Running tests only..."
        run_tests
        ;;
    "verify")
        print_status "Running verification only..."
        verify_deployment "$DEPLOYMENT_URL"
        ;;
    "quick")
        print_status "Quick deployment (skip tests)..."
        git push origin main
        wait_for_api "$DEPLOYMENT_URL" $MAX_WAIT_TIME $CHECK_INTERVAL
        verify_deployment "$DEPLOYMENT_URL"
        ;;
    *)
        main
        ;;
esac