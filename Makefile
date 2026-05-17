# Taskraptor Self-Hosted Deployment Makefile
# Run from the repo root on the deployment server.

COMPOSE := docker compose -f docker-compose.yml
PROJECT := taskraptor-prod
HEALTH_URL := http://localhost/api/health

.PHONY: help build up down logs status health deploy prune

help:
	@echo "Available targets:"
	@echo "  build   - Build or rebuild all service images"
	@echo "  up      - Start all services in detached mode"
	@echo "  down    - Stop and remove all services"
	@echo "  logs    - Tail logs for all services"
	@echo "  status  - Show running container status"
	@echo "  health  - Hit the local API health endpoint"
	@echo "  deploy  - Full redeploy: pull, build, down, up, health"
	@echo "  prune   - Remove dangling Docker images"

build:
	$(COMPOSE) build --no-cache

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

status:
	$(COMPOSE) ps

health:
	@echo "Checking health endpoint..."
	@curl -sS $(HEALTH_URL) || echo "Health check failed"

deploy: down build up
	@echo "Waiting for services to settle..."
	@sleep 5
	$(MAKE) health

prune:
	docker image prune -f
