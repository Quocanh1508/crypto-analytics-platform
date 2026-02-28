#!/bin/bash
# Airflow initialization script – baked into the image at /opt/airflow/init.sh
# Uses 'python -m airflow' so it works regardless of PATH configuration.
set -e

echo ">>> Running airflow db migrate..."
python -m airflow db migrate

echo ">>> Creating admin user..."
python -m airflow users create \
  --username "${AIRFLOW_ADMIN_USERNAME}" \
  --password "${AIRFLOW_ADMIN_PASSWORD}" \
  --firstname "${AIRFLOW_ADMIN_FIRSTNAME}" \
  --lastname  "${AIRFLOW_ADMIN_LASTNAME}" \
  --role Admin \
  --email "${AIRFLOW_ADMIN_EMAIL}" || true

echo ">>> Airflow initialization complete."
