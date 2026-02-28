import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'data_engineer',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Define the DAG
with DAG(
    'crypto_batch_pipeline',
    default_args=default_args,
    description='A batch DAG orchestrating dbt transformations and Great Expectations data quality checks.',
    schedule_interval=timedelta(minutes=5), # Runs every 5 minutes to keep Gold layer fresh
    start_date=datetime(2023, 1, 1),
    catchup=False,
    tags=['crypto', 'dbt', 'ge'],
) as dag:

    # 1. dbt run
    # Builds the Bronze views, the Silver incremental table, and the Gold rollup table.
    dbt_run = BashOperator(
        task_id='dbt_run',
        bash_command='cd /opt/airflow/dbt_crypto && dbt run --profiles-dir .',
        env={**os.environ, 'RUNNING_IN_DOCKER': 'true'}
    )

    # 2. dbt test
    # Runs the basic schema assertions (e.g., not_null on keys)
    dbt_test = BashOperator(
        task_id='dbt_test',
        bash_command='cd /opt/airflow/dbt_crypto && dbt test --profiles-dir .',
        env={**os.environ, 'RUNNING_IN_DOCKER': 'true'}
    )

    # 3. Great Expectations Validation
    # Runs the programmatic validation script against the built silver layer.
    ge_validation = BashOperator(
        task_id='ge_validation',
        bash_command='python /opt/airflow/ge_tests/run_validations.py',
        env={**os.environ, 'RUNNING_IN_DOCKER': 'true'}
    )

    # Define execution order
    dbt_run >> dbt_test >> ge_validation
