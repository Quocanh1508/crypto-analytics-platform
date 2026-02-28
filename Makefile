# =============================================================================
# Makefile – Crypto Analytics Platform
# Usage: make <target>
# Windows users: run commands directly with docker compose if make is unavailable
# =============================================================================

COMPOSE = docker compose
PROJECT = crypto

.PHONY: help up down restart logs ps reset kafka-topics kafka-produce

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Start all services
	$(COMPOSE) up -d

down: ## Stop all services (keep volumes)
	$(COMPOSE) down

stop: ## Stop without removing containers
	$(COMPOSE) stop

restart: ## Restart all services
	$(COMPOSE) down && $(COMPOSE) up -d

logs: ## Follow logs for all services
	$(COMPOSE) logs -f

logs-%: ## Follow logs for a specific service, e.g. make logs-kafka
	$(COMPOSE) logs -f $*

ps: ## Show running containers and their status
	$(COMPOSE) ps

reset: ## WARNING: Stop all services AND delete all volumes (fresh start)
	$(COMPOSE) down -v --remove-orphans
	@echo "All volumes deleted. Run 'make up' to start fresh."

# ---------------------------------------------------------------------------
# Kafka helpers
# ---------------------------------------------------------------------------
kafka-topics: ## List all Kafka topics
	$(COMPOSE) exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

kafka-console-consumer: ## Consume from crypto.trades.raw (Ctrl+C to stop)
	$(COMPOSE) exec kafka kafka-console-consumer.sh \
		--bootstrap-server localhost:9092 \
		--topic crypto.trades.raw \
		--from-beginning

# ---------------------------------------------------------------------------
# Postgres helpers
# ---------------------------------------------------------------------------
psql: ## Open a psql shell in the postgres container
	$(COMPOSE) exec postgres psql -U postgres

psql-analytics: ## Open psql connected to crypto_analytics DB
	$(COMPOSE) exec postgres psql -U postgres -d crypto_analytics

# ---------------------------------------------------------------------------
# MinIO helpers
# ---------------------------------------------------------------------------
minio-ls: ## List all MinIO buckets
	$(COMPOSE) exec minio mc alias set local http://localhost:9000 minioadmin minioadmin && \
	$(COMPOSE) exec minio mc ls local/

# ---------------------------------------------------------------------------
# Day profiles (start only the services you need)
# ---------------------------------------------------------------------------
up-streaming: ## Day: ingestion & streaming (Kafka, MinIO, Postgres, Producer)
	$(COMPOSE) --profile streaming up -d zookeeper kafka minio postgres minio-init binance-producer

up-batch: ## Day: batch & modeling (MinIO, Postgres, Airflow)
	$(COMPOSE) up -d postgres minio minio-init airflow-init airflow-webserver airflow-scheduler

up-dashboards: ## Day: dashboards (Postgres, Superset)
	$(COMPOSE) up -d postgres superset-init superset

up-all: up ## Day: everything on (alias for make up)
