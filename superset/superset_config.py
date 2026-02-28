"""
Superset configuration for the Crypto Analytics Platform.
Place this file at: superset/superset_config.py
It is mounted into the container at /app/pythonpath/superset_config.py
"""
import os

# Secret key (override from environment)
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "supersetSecretKey123!")

# Use PostgreSQL as the metadata DB (shared postgres container)
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@postgres:5432/airflow",
)

# Disable the DuckDB in-memory default
PREVENT_UNSAFE_DEFAULT_URLS_ON_DATASET = False

# Allow embedding Superset (useful for dashboards)
WTF_CSRF_ENABLED = True
WTF_CSRF_EXEMPT_LIST = []

# Feature flags
FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
}

# Row limit for charts
ROW_LIMIT = 100_000
VIZ_ROW_LIMIT = 50_000

# Silence the SQLAlchemy connection check noise
SQLALCHEMY_TRACK_MODIFICATIONS = False
