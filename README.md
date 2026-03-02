# 🚀 Real-Time Crypto Analytics Platform

> An end-to-end, production-grade streaming data engineering platform that ingests live cryptocurrency trade data from **Binance**, processes it through a **Medallion Architecture**, and visualizes it with interactive dashboards — all running locally inside Docker.

---

## 📌 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Data Flow](#data-flow)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Services & Ports](#services--ports)
- [Running Each Phase](#running-each-phase)
- [Design Decisions](#design-decisions)

---

## Overview

This platform was built to answer a single question: **How do you build a complete, production-like streaming data pipeline from scratch on a single machine?**

It tracks live OHLCV (Open, High, Low, Close, Volume) data for **BTCUSDT, ETHUSDT, and BNBUSDT** in real time, processes it through multiple quality and transformation layers, and serves it up for analytics.

The platform is structured into **5 phases**:

| Phase | Name | Description |
|-------|------|-------------|
| 0 | Environment & Scaffolding | Docker Compose, `.env`, schemas, init scripts |
| 1 | Python Streaming (Variant A) | Binance WebSocket → Kafka → Python Consumer → Postgres/MinIO |
| 2 | dbt + Airflow + Great Expectations | Batch transforms, data quality, orchestration |
| 3 | Superset Dashboards | Interactive visualizations on the Gold layer |
| 4 | Spark Structured Streaming (Variant B) | PySpark replaces the Python consumer for scalable processing |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          REAL-TIME INGESTION LAYER                         │
│                                                                             │
│   ┌─────────────┐    WebSocket     ┌──────────┐    Messages    ┌────────┐  │
│   │   Binance   │ ──────────────── │  Kafka   │ ────────────── │ Topic  │  │
│   │  API Feed   │   (trade events) │ (Broker) │                │ raw    │  │
│   └─────────────┘                  └──────────┘                └────────┘  │
└───────────────────────────────────────────────────────────────┬─────────────┘
                                                                │
                        ┌───────────────────────────────────────┤
                        │                                       │
          ┌─────────────▼──────────┐              ┌────────────▼──────────┐
          │  Variant A: Python     │              │  Variant B: PySpark   │
          │  (stream_consumer.py)  │              │  (stream_job.py)      │
          │  - Aggregates to 1m    │              │  - Windowed 1m OHLCV  │
          │  - Writes Postgres     │              │  - Writes Postgres    │
          │  - Writes MinIO JSONL  │              │  - Writes MinIO JSON  │
          └─────────────┬──────────┘              └────────────┬──────────┘
                        └───────────────┬───────────────────────┘
                                        │
┌───────────────────────────────────────▼────────────────────────────────────┐
│                          STORAGE LAYER                                     │
│                                                                             │
│   ┌────────────────┐              ┌────────────────────────────────────┐   │
│   │  MinIO (S3)    │              │  PostgreSQL (crypto_analytics DB)  │   │
│   │  raw/          │              │  ┌──────────────────────────────┐  │   │
│   │  bronze/       │              │  │ raw_klines (REST batch)      │  │   │
│   │  silver/       │              │  │ fact_realtime_trades_1m      │  │   │
│   │  gold/         │              │  └──────────────────────────────┘  │   │
│   └────────────────┘              └────────────────────────────────────┘   │
└───────────────────────────────────────┬────────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼────────────────────────────────────┐
│                     TRANSFORMATION & QUALITY LAYER                         │
│                                                                             │
│   Apache Airflow (Orchestrator — every 5 min)                              │
│       │                                                                     │
│       ├─► dbt run    → bronze → silver (silver_klines_1m) →                │
│       │                        gold   (gold_klines_5m)                     │
│       ├─► dbt test   → schema assertions (not_null, unique, values)        │
│       └─► Great Expectations → runtime data quality validation             │
└───────────────────────────────────────┬────────────────────────────────────┘
                                        │
┌───────────────────────────────────────▼────────────────────────────────────┐
│                          PRESENTATION LAYER                                │
│                                                                             │
│   Apache Superset                                                           │
│       ├─► "Crypto 5m Prices"   — Line chart  (AVG close by symbol)        │
│       └─► "Volume by Symbol"   — Bar chart   (SUM volume by symbol)        │
│                                                                             │
│   Dashboard: "Real-time Crypto Analytics"                                  │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer | Technology | Version | Why This Choice |
|-------|-----------|---------|-----------------|
| **Message Broker** | Apache Kafka | via Confluent `7.6.1` | Industry-standard for high-throughput event streaming. Decouples producers from consumers and provides persistent, replayable message logs. |
| **Coordination** | Apache Zookeeper | via Confluent `7.6.1` | Required by the Confluent Kafka broker. Handles leader election and cluster metadata. |
| **Object Storage** | MinIO | `RELEASE.2024-05-10` | S3-compatible open-source storage. Allows the same `boto3`/`s3a://` code to run locally as it would on AWS S3. Stores raw trade JSONL and Spark checkpoint data. |
| **Relational DB** | PostgreSQL | `15` | Acts as both the Airflow metadata database and the analytics database. Chosen for its excellent support for `ON CONFLICT ... DO UPDATE` upserts (critical for streaming 1m candles). |
| **Streaming (Var A)** | Python + `kafka-python` | `3.11` | Lightweight, easy to iterate consumer for initial delivery. Low overhead, fast to develop, great for prototyping the pipeline logic. |
| **Streaming (Var B)** | Apache Spark Structured Streaming | `3.5` via `apache/spark-py` | Fault-tolerant, distributed, exactly-once streaming with native tumbling window aggregations. Purpose-built for large-scale event processing — a direct evolution from the Python consumer. |
| **Transformation** | dbt (data build tool) | `dbt-postgres 1.8.2` | SQL-first data transformation with built-in testing, lineage graphs, and documentation. Implements the Medallion Architecture (Bronze → Silver → Gold). |
| **Data Quality** | Great Expectations | `0.18.8` | Programmatic data quality framework. Validates live data in PostgreSQL against an `ExpectationSuite` with type, null, and value constraints. |
| **Orchestration** | Apache Airflow | `2.9.1` | Industry-standard workflow orchestrator. Schedules the `dbt run → dbt test → GE validate` pipeline on a 5-minute cron. |
| **Visualization** | Apache Superset | `4.0.2` | Open-source business intelligence tool. Connects directly to PostgreSQL and provides no-code chart building on top of the Gold layer. |
| **Containerization** | Docker + Docker Compose | `v2` | Ensures 100% reproducible environments. All 10+ services run on a single machine with memory limits tuned for a 16GB RAM laptop. |
| **Data Source** | Binance REST & WebSocket API | — | Free, real-time crypto market data. REST for historical klines backfill; WebSocket for live trade-by-trade tick data. |

---

## Data Flow

### Real-Time Path (Streaming)

```
Binance WebSocket
    │
    │  (trade events: symbol, price, qty, timestamp)
    ▼
Kafka Topic: crypto.trades.raw
    │
    ├─────────────────────────────────────────────────────────────┐
    │  Variant A: Python Consumer                                 │  Variant B: PySpark
    │  - Buffers trades in memory (10s or 5000 items)            │  - Reads Kafka as a stream
    │  - Aggregates by (symbol, 1-minute bucket)                 │  - Tumbling window: 1 minute
    │  - Flushes raw JSONL to MinIO                              │  - ForeachBatch → Postgres upsert
    │  - Upserts OHLCV rows to fact_realtime_trades_1m           │  - Raw JSON → MinIO partitioned by symbol
    └────────────────────────────────────────────────────────────┘
                              │
                     fact_realtime_trades_1m (PostgreSQL)
```

### Batch Path (Historical + dbt)

```
Binance REST API
    │
    │  (1-minute kline candles, backfill)
    ▼
raw_klines (PostgreSQL)
    │
    ▼
Airflow DAG: crypto_batch_pipeline (every 5 min)
    │
    ├─► dbt run
    │     ├──► Bronze layer: bronze_historical_klines (view on raw_klines)
    │     │                  bronze_realtime_klines   (view on fact_realtime_trades_1m)
    │     ├──► Silver layer: silver_klines_1m         (unified, deduplicated 1m candles)
    │     └──► Gold layer:   gold_klines_5m           (5-minute OHLCV rollup)
    │
    ├─► dbt test  (not_null, unique, accepted_values assertions)
    │
    └─► Great Expectations checkpoint
              (validates silver_klines_1m: null checks, symbol whitelist, volume >= 0)
```

---

## Project Structure

```
crypto-analytics-platform/
├── producer/                   # Binance WebSocket producer
│   └── binance_producer.py     # Connects to Binance WS, publishes to Kafka
│
├── consumer/                   # Python Kafka consumer (Variant A)
│   └── stream_consumer.py      # 1m aggregation → Postgres + MinIO
│
├── spark/                      # PySpark Structured Streaming (Variant B)
│   ├── Dockerfile              # Built from apache/spark-py:latest
│   ├── stream_job.py           # Tumbling window aggregation + dual sinks
│   └── requirements.txt
│
├── ingestion/                  # Batch REST ingestion
│   └── fetch_klines.py         # Pulls historical klines from Binance REST
│
├── dbt_crypto/                 # dbt project
│   ├── models/
│   │   ├── bronze/             # Raw source views
│   │   ├── silver/             # Unified, cleaned 1m candles
│   │   └── gold/              # 5m OHLCV rollup for dashboards
│   └── dbt_project.yml
│
├── ge_tests/                   # Great Expectations
│   └── run_validations.py      # Programmatic GE checkpoint runner
│
├── airflow/
│   └── dags/
│       └── crypto_batch_pipeline.py  # DAG: dbt → dbt test → GE
│
├── sql/
│   └── schema.sql              # All Postgres table definitions
│
├── init/
│   ├── postgres/               # DB + schema init on first boot
│   └── minio/                  # Bucket creation scripts
│
├── superset/
│   └── superset_config.py      # Custom Superset config (DB, secret key)
│
├── docker-compose.yml          # Full stack definition
├── .env                        # All credentials & config (not committed)
├── Makefile                    # Developer shortcuts
└── README.md
```

---

## Quick Start

### Prerequisites

- Docker Desktop (with WSL2 on Windows, 8GB+ RAM allocated)
- A free [Binance API account](https://www.binance.com/en/my/settings/api-management) (optional — producer works anonymously for public trades)

### 1. Clone and Configure

```bash
git clone https://github.com/Quocanh1508/crypto-analytics-platform.git
cd crypto-analytics-platform

# Copy the example env (edit as needed)
cp .env.example .env
```

### 2. Start Core Infrastructure

Runs only what is needed to get streaming working — saves RAM:

```bash
docker compose up -d zookeeper kafka postgres minio
```

### 3. Initialize Databases & Buckets

```bash
# PostgreSQL tables are created automatically via init/postgres/
# MinIO buckets are created by:
docker compose up minio-init
```

### 4. Start Streaming (choose one consumer)

**Option A — Python consumer:**
```bash
docker compose --profile streaming up -d binance-producer binance-consumer
```

**Option B — Spark Structured Streaming:**
```bash
docker compose --profile spark-streaming up -d --build binance-producer spark-master
```

### 5. Run the Batch Pipeline (dbt + GE)

```bash
# First, backfill 2 days of history:
python ingestion/fetch_klines.py

# Then start the Airflow orchestrator:
docker compose up -d airflow-db-init airflow-webserver airflow-scheduler

# Open http://localhost:8080 → unpause `crypto_batch_pipeline` DAG
```

### 6. Open Dashboards

```bash
docker compose up -d superset superset-init
# Open http://localhost:8088 → login: admin / admin
```

---

## Services & Ports

| Service | Container | Port | URL |
|---------|-----------|------|-----|
| Kafka Broker | `crypto-kafka` | `9092` | — |
| Zookeeper | `crypto-zookeeper` | `2181` | — |
| PostgreSQL | `crypto-postgres` | `5432` | — |
| MinIO API | `crypto-minio` | `9000` | — |
| **MinIO Console** | `crypto-minio` | `9001` | http://localhost:9001 |
| **Airflow** | `crypto-airflow-webserver` | `8080` | http://localhost:8080 |
| **Superset** | `crypto-superset` | `8088` | http://localhost:8088 |
| **Spark UI** | `crypto-spark` | `4040` | http://localhost:4040 |

**Default Credentials:**

| Service | Username | Password |
|---------|----------|----------|
| PostgreSQL | `postgres` | `postgres` |
| MinIO | `minioadmin` | `minioadmin` |
| Airflow | `admin` | `admin` |
| Superset | `admin` | `admin` |

---

## Running Each Phase

### Phase 1 only (streaming, no batch)

```bash
docker compose up -d zookeeper kafka postgres minio
docker compose --profile streaming up -d binance-producer binance-consumer
```

### Phase 2 only (batch transforms, no streaming)

Requires data in `raw_klines` first. Run `ingestion/fetch_klines.py`, then:

```bash
docker compose up -d postgres airflow-db-init airflow-webserver airflow-scheduler
```

### Phase 4 — Spark only

```bash
docker compose up -d zookeeper kafka postgres minio
docker compose --profile streaming up -d binance-producer
docker compose --profile spark-streaming up -d spark-master
```

Stop the Spark job cleanly:

```bash
docker compose stop spark-master
```

### RAM Usage Guide

| Scenario | Approximate RAM |
|----------|----------------|
| Kafka + Zookeeper + Postgres + MinIO | ~800 MB |
| + Python producer + consumer | ~1.0 GB |
| + Spark Structured Streaming | ~2.0 GB |
| + Airflow (webserver + scheduler) | ~2.8 GB |
| + Superset | ~3.4 GB |
| Full stack | ~3.5–4.5 GB |

---

## Design Decisions

### Why the Medallion Architecture?

The **Bronze → Silver → Gold** pattern isolates failure domains. Raw data is always preserved in Bronze — if a transformation bug is discovered, only Silver and Gold need to be rerun. This avoids data loss and makes debugging much easier.

### Why two streaming consumers (Python + Spark)?

They serve different purposes:

- **Python consumer (Variant A)**: Lightweight, fast to develop, great for a single-node setup. Perfect for prototyping and quick iteration.
- **Spark consumer (Variant B)**: Fault-tolerant, scales horizontally, supports exactly-once semantics with checkpointing. Designed for production where trade volumes may exceed what a single Python thread can handle.

Both write to the same `fact_realtime_trades_1m` table using the same upsert logic, making them interchangeable at runtime.

### Why Kafka instead of direct database writes?

Kafka acts as the **central nervous system** of the platform. It decouples the producer (Binance WebSocket) from all consumers. This means:
1. Multiple consumers (Python, Spark, future subscribers) can independently read the same data stream.
2. Messages are persisted for a configurable retention period — if a consumer crashes, it can resume from where it left off.
3. No data is lost between producer restarts.

### Why dbt for transformations?

dbt brings **software engineering practices** to SQL:
- Built-in unit testing (`not_null`, `unique`, `accepted_values`)
- Automatic DAG lineage graphs
- Incrementally-materialized models that only process new data
- Separation of raw ingestion from business logic

### Why Great Expectations for data quality?

Unlike dbt tests (which run after transformation), **Great Expectations validates the live Silver data** before it reaches the Gold layer. This catches issues at the data boundary — wrong symbols, unexpected nulls, negative volumes — before bad data propagates into dashboards.

### Why Airflow for orchestration?

Airflow provides a battle-tested scheduler with a visual UI for monitoring pipeline health. The `crypto_batch_pipeline` DAG chains `dbt run → dbt test → GE validate` sequentially, with automatic retry and failure alerting built in.

### Why MinIO instead of local filesystem?

Using **MinIO as S3-compatible storage** means the consumers and Spark job use standard `boto3` / `s3a://` storage APIs — identical to what would be used against real AWS S3. This makes the platform cloud-portable: replacing MinIO with S3 requires only changing an endpoint URL in `.env`.
