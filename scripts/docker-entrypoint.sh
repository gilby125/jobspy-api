#!/bin/bash
# Docker entrypoint script that handles script permissions and execution

# Ensure scripts are executable (needed when mounted as volumes)
find /app/scripts -type f -name "*.sh" -exec chmod +x {} \;
find /app/scripts -type f -name "*.py" -exec chmod +x {} \;

# Display environment variable debug info
echo "=== Environment Variable Load Order Debug ==="
echo "Environment variables from different sources:"
echo "1. Command line/docker-compose.yml environment section:"
echo "   LOG_LEVEL=$LOG_LEVEL"
echo "   ENABLE_API_KEY_AUTH=$ENABLE_API_KEY_AUTH"
echo 

# Check Dockerfile ENV vs runtime environment
echo "2. Default values from Dockerfile (these should be overridden at runtime):"
echo "   Dockerfile ARG LOG_LEVEL default=DEBUG"
echo "   Dockerfile ARG ENABLE_API_KEY_AUTH default=false"
echo 

# Dump all environment variables for analysis
echo "3. All current environment variables (alphabetical):"
env | grep -E "LOG_LEVEL|ENABLE_|API_KEY|ENVIRONMENT" | sort
echo

echo "=== Environment Variable Override Chain ==="
echo "Command line args > docker-compose environment > .env > Dockerfile ENV > Dockerfile ARG defaults"
echo "==========================================="

# Run the confirmation script
bash /app/scripts/confirm_env.sh

# Change to app directory and start the FastAPI application
cd /app
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
