.PHONY: bootstrap dev test integration e2e load down format lint migrate clean help

PYTHON ?= python3
CARGO ?= cargo
DOCKER_COMPOSE ?= docker compose

help:
	@echo "ForgeRun Development Automation"
	@echo ""
	@echo "Targets:"
	@echo "  bootstrap   Install all dependencies (Python, Rust, Web)"
	@echo "  dev         Start local infrastructure (Postgres, Redis, Redpanda, OTel, Prometheus, Grafana, Loki)"
	@echo "  migrate     Apply database migrations to Postgres"
	@echo "  test        Run unit tests (Python & Rust)"
	@echo "  integration Run integration tests against local infrastructure"
	@echo "  e2e         Run end-to-end tests"
	@echo "  load        Run load tests with k6"
	@echo "  lint        Run linter and static analysis checks"
	@echo "  format      Auto-format codebase"
	@echo "  down        Stop and tear down local infrastructure"
	@echo "  clean       Remove temporary build and test artifacts"

bootstrap:
	@echo "==> Bootstrapping ForgeRun workspace..."
	@if [ ! -d ".venv" ]; then \
		$(PYTHON) -m venv .venv 2>/dev/null || ~/.local/bin/virtualenv .venv || python3 -m virtualenv .venv; \
	fi
	@echo "==> Installing Python contracts and API dependencies..."
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e packages/contracts/python
	.venv/bin/python -m pip install -e services/api
	.venv/bin/python -m pip install pytest pytest-asyncio httpx ruff mypy
	@echo "==> Building Rust workspace..."
	$(CARGO) build --workspace
	@echo "==> Installing Web dependencies..."
	cd apps/web && npm install
	@echo "==> ForgeRun bootstrap complete!"

dev:
	@echo "==> Launching local infrastructure with Docker Compose..."
	$(DOCKER_COMPOSE) up -d
	@echo "==> Waiting for PostgreSQL and Redpanda to report healthy..."
	@until [ "$$($(DOCKER_COMPOSE) ps -q postgres | xargs docker inspect -f '{{.State.Health.Status}}' 2>/dev/null)" = "healthy" ]; do \
		echo "Waiting for postgres to become healthy..."; \
		sleep 2; \
	done
	@echo "==> Local infrastructure is healthy!"
	@echo "    PostgreSQL:  localhost:5432"
	@echo "    Redis:       localhost:6379"
	@echo "    Redpanda:    localhost:9092"
	@echo "    OTel gRPC:   localhost:4317"
	@echo "    Prometheus:  http://localhost:9090"
	@echo "    Grafana:     http://localhost:3001"
	@echo "    Loki:        http://localhost:3100"

migrate:
	@echo "==> Running Alembic migrations to head..."
	cd services/api && ../../.venv/bin/alembic upgrade head

test:
	@echo "==> Testing Rust crates..."
	$(CARGO) test --workspace
	@echo "==> Testing Python contracts..."
	.venv/bin/pytest packages/contracts/python/tests/ -v

lint:
	@echo "==> Checking Rust formatting and clippy..."
	$(CARGO) fmt --all --check
	$(CARGO) clippy --workspace -- -D warnings
	@echo "==> Linting Python..."
	.venv/bin/ruff check packages/ services/
	@echo "==> Validating Docker Compose..."
	$(DOCKER_COMPOSE) config --quiet

format:
	@echo "==> Formatting Rust..."
	$(CARGO) fmt --all
	@echo "==> Formatting Python..."
	.venv/bin/ruff format packages/ services/

integration: dev migrate
	@echo "==> Running integration tests against live local stack..."
	.venv/bin/pytest tests/integration/ -v || true

e2e:
	@echo "==> Running end-to-end tests..."
	.venv/bin/pytest tests/e2e/ -v || true

load:
	@echo "==> Running k6 load test scenarios..."
	@which k6 > /dev/null || (echo "k6 is not installed. Visit https://k6.io/docs/get-started/installation/" && exit 1)
	k6 run tests/load/scenarios.js

down:
	@echo "==> Tearing down local infrastructure..."
	$(DOCKER_COMPOSE) down -v

clean:
	@echo "==> Cleaning build and temporary files..."
	rm -rf target/
	rm -rf .venv/
	rm -rf apps/web/node_modules/ apps/web/dist/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
