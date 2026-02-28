# End-to-End Real-Time Cryptocurrency Market Analytics Platform

> **Status:** Phase 0 – Environment & Scaffolding ✅

## Architecture Overview

```
Binance WebSocket ──► Kafka ──► Python Consumer ──► PostgreSQL
                                                 └──► MinIO (Parquet)
Binance REST API  ──► MinIO + PostgreSQL (batch)

PostgreSQL ──► dbt (models) ──► Great Expectations (validation) ──► Superset (dashboards)
```

## Tech Stack

| Layer | Tool |
|---|---|
| Message broker | Apache Kafka + Zookeeper |
| Object store | MinIO (S3-compatible) |
| Database | PostgreSQL 16 |
| Orchestration | Apache Airflow 2.9 (LocalExecutor) |
| Data modeling | dbt-postgres |
| Data quality | Great Expectations |
| Dashboards | Apache Superset 4.0 |
| Streaming (later) | Apache Spark Structured Streaming |

## Port Map

| Service | Port | URL |
|---|---|---|
| Airflow UI | 8080 | http://localhost:8080 |
| Superset UI | 8088 | http://localhost:8088 |
| MinIO Console | 9001 | http://localhost:9001 |
| MinIO API | 9000 | http://localhost:9000 |
| PostgreSQL | 5432 | localhost:5432 |
| Kafka (external) | 29092 | localhost:29092 |

## Prerequisites

- Docker Desktop ≥ 4.x (enable WSL2 backend on Windows)  
- Python 3.10+ (for local scripts outside Docker)  
- Git  
- (Optional) `make` — on Windows, install via [Chocolatey](https://chocolatey.org/): `choco install make`

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url>
cd Binance

# 2. Copy and review the env file (already committed with dev defaults)
#    NEVER commit .env to production repos!
cp .env.example .env   # (or edit .env directly)

# 3. Start everything
docker compose up -d

# 4. Wait ~90 seconds for services to initialize, then check:
docker compose ps

# 5. Access UIs
# MinIO  → http://localhost:9001  (minioadmin / minioadmin)
# Airflow → http://localhost:8080 (admin / admin)
# Superset → http://localhost:8088 (admin / admin)
```

## Day Profiles (RAM Optimization for 16 GB)

Use targeted profiles to avoid running everything at once:

```bash
# Ingestion & streaming day
docker compose up -d zookeeper kafka minio postgres minio-init

# Batch & modeling day
docker compose up -d postgres minio minio-init airflow-init airflow-webserver airflow-scheduler

# Dashboard day
docker compose up -d postgres superset-init superset
```

Or with `make`:
```bash
make up-streaming    # ingestion & streaming
make up-batch        # batch & modeling
make up-dashboards   # dashboards only
make up              # everything
make down            # stop (keep volumes)
make reset           # ⚠️ wipe all volumes (fresh start)
```

## Project Structure

```
Binance/
├── docker-compose.yml         # All services
├── .env                       # Configuration (don't commit secrets!)
├── Makefile                   # Convenience commands
│
├── init/
│   ├── postgres/              # SQL scripts run at first Postgres start
│   │   ├── 01_create_databases.sql
│   │   └── 02_create_schema.sql
│   └── minio/
│       └── create_buckets.sh  # Creates raw/bronze/silver/gold buckets
│
├── airflow/
│   ├── dags/                  # Airflow DAGs (Phase 2)
│   ├── plugins/               # Custom operators/hooks
│   ├── logs/                  # Runtime logs (git-ignored)
│   └── requirements.txt       # Extra pip packages for workers
│
├── superset/
│   └── superset_config.py     # Superset overrides
│
├── producer/                  # Binance WebSocket producer (Phase 1)
├── consumer/                  # Python streaming consumer (Phase 1)
├── ingestion/                 # Batch historical ingester (Phase 1)
├── dbt/                       # dbt project (Phase 2)
└── spark/                     # Spark jobs (Phase 4)
```

## Development Phases

| Phase | Description | Status |
|---|---|---|
| 0 | Environment & Scaffolding | ✅ Done |
| 1 | Python Streaming (Producer + Consumer + Batch) | 🔜 Next |
| 2 | dbt + Airflow + Great Expectations | ⏳ Planned |
| 3 | Superset Dashboards | ⏳ Planned |
| 4 | Spark Structured Streaming upgrade | ⏳ Planned |
