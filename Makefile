.PHONY: help install run test lint docker-build docker-run docker-compose-up docker-compose-down docker-compose-dev dev prod clean-start update test-and-build ci logs restart rebuild check-env debug-docker docker-push version version-patch version-minor version-major docker-buildx docker-pushx deploy deploy-quick monitor deploy-status

help:
	@echo "Available commands:"
	@echo "  make install            - Install dependencies"
	@echo "  make run                - Run development server"
	@echo "  make test               - Run tests"
	@echo "  make lint               - Run linter"
	@echo "  make docker-build       - Build Docker image"
	@echo "  make docker-run         - Run Docker container"
	@echo "  make docker-compose-up  - Start with Docker Compose"
	@echo "  make docker-compose-down- Stop Docker Compose containers"
	@echo "  make docker-compose-dev - Start development mode with Docker Compose"
	@echo "  make docker-push        - Build and push Docker image to Docker Hub"
	@echo "  make docker-buildx      - Build multi-arch Docker image (x86_64, arm64)"
	@echo "  make docker-pushx       - Build and push multi-arch Docker image to Docker Hub"
	@echo ""
	@echo "Combined commands:"
	@echo "  make dev                - Run development server with auto-reload"
	@echo "  make prod               - Build and run production container"
	@echo "  make clean-start        - Remove containers, rebuild and start"
	@echo "  make update             - Update dependencies and rebuild"
	@echo "  make test-and-build     - Run tests and build if they pass"
	@echo "  make ci                 - Run full CI pipeline (test, build, run)"
	@echo "  make logs               - Show logs from running containers"
	@echo "  make restart            - Restart running containers"
	@echo "  make rebuild            - Rebuild and restart containers"
	@echo "  make check-env          - Check environment issues"
	@echo "  make debug-docker       - Debug environment issues in Docker"
	@echo ""
	@echo "Version commands:"
	@echo "  make version            - Show current version"
	@echo "  make version-patch      - Increment patch version (1.0.0 -> 1.0.1)"
	@echo "  make version-minor      - Increment minor version (1.0.0 -> 1.1.0)"
	@echo "  make version-major      - Increment major version (1.0.0 -> 2.0.0)"
	@echo ""
	@echo "Deployment commands:"
	@echo "  make deploy             - Full deployment with tests and verification"
	@echo "  make deploy-quick       - Quick deployment (skip tests)"
	@echo "  make monitor            - Check deployment status"
	@echo "  make deploy-status      - Show deployment URLs and status"

install:
	pip install -r requirements.txt
	pip install pytest pytest-cov pylint

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest --cov=app tests/

lint:
	pylint app/

docker-build:
	docker build -t jobspy-api .

docker-buildx:
	@echo "Building multi-arch Docker image (linux/amd64,linux/arm64)..."
	@python -c "from app import __version__; print(f'Current version: {__version__}')"
	@VERSION=$$(python -c "from app import __version__; print(__version__)") && \
	docker buildx build --platform linux/amd64,linux/arm64 \
		-t jobspy-api:$$VERSION -t jobspy-api:latest \
		--load .

docker-run:
	docker run -p 8000:8000 jobspy-api

docker-compose-up:
	docker-compose up -d

docker-compose-down:
	docker-compose down

docker-compose-dev:
	docker-compose -f docker-compose.dev.yml up

# Combined commands
dev:
	docker-compose -f docker-compose.dev.yml up --build

prod:
	docker-compose build
	docker-compose up -d

clean-start:
	docker-compose down -v
	docker-compose rm -f
	docker-compose build --no-cache
	docker-compose up -d

update:
	pip install -U -r requirements.txt
	pip install -U -r requirements-dev.txt
	docker-compose build --no-cache
	docker-compose up -d

test-and-build:
	pytest --cov=app tests/ && docker-compose build

ci:
	pytest --cov=app tests/
	docker-compose build
	docker-compose up -d

logs:
	docker-compose logs -f

restart:
	docker-compose restart

rebuild:
	docker-compose down
	docker-compose build
	docker-compose up -d

check-env:
	python scripts/check_env.py

debug-docker:
	docker-compose run --rm jobspy-api python /app/scripts/check_env.py

docker-push:
	@echo "Building and pushing Docker image to Docker Hub..."
	@python -c "from app import __version__; print(f'Current version: {__version__}')"
	@VERSION=$$(python -c "from app import __version__; print(__version__)") && \
	echo "Building version $$VERSION" && \
	docker build -t jobspy-api:$$VERSION -t jobspy-api:latest . && \
	echo "Enter your Docker Hub username:" && \
	read DOCKER_USER && \
	docker tag jobspy-api:$$VERSION $$DOCKER_USER/jobspy-api:$$VERSION && \
	docker tag jobspy-api:latest $$DOCKER_USER/jobspy-api:latest && \
	docker push $$DOCKER_USER/jobspy-api:$$VERSION && \
	docker push $$DOCKER_USER/jobspy-api:latest && \
	echo "Successfully pushed version $$VERSION to Docker Hub"

docker-pushx:
	@echo "Building and pushing multi-arch Docker image to Docker Hub..."
	@python -c "from app import __version__; print(f'Current version: {__version__}')"
	@VERSION=$$(python -c "from app import __version__; print(__version__)") && \
	echo "Enter your Docker Hub username:" && \
	read DOCKER_USER && \
	docker buildx build --platform linux/amd64,linux/arm64 \
		-t $$DOCKER_USER/jobspy-api:$$VERSION -t $$DOCKER_USER/jobspy-api:latest \
		--push .

version:
	@python -c "from app import __version__; print(f'Current version: {__version__}')"

version-patch:
	@python scripts/increment_version.py patch
	@$(MAKE) version

version-minor:
	@python scripts/increment_version.py minor
	@$(MAKE) version

version-major:
	@python scripts/increment_version.py major
	@$(MAKE) version

# Deployment commands
deploy:
	@echo "🚀 Starting full deployment..."
	./deploy.sh

deploy-quick:
	@echo "⚡ Starting quick deployment..."
	./deploy.sh quick

monitor:
	@echo "🔍 Checking deployment status..."
	./monitor_deployment.sh

deploy-status:
	@echo "🌐 JobSpy Deployment Information"
	@echo "==============================="
	@echo ""
	@echo "🔗 URLs:"
	@echo "  Local:      http://localhost:8787"
	@echo "  Deployed:   http://192.168.7.10:8787"
	@echo "  Admin:      http://192.168.7.10:8787/admin/"
	@echo "  Analytics:  http://192.168.7.10:8787/admin/analytics"
	@echo "  API Docs:   http://192.168.7.10:8787/docs"
	@echo ""
	@echo "📊 Quick Status Check:"
	@./monitor_deployment.sh
