FROM apache/airflow:2.9.1-python3.11

# Use root only to set up the init script with execute permissions
USER root
COPY init.sh /opt/airflow/init.sh
RUN chmod +x /opt/airflow/init.sh && chown airflow:root /opt/airflow/init.sh

# Switch to airflow user for pip install — this keeps the venv PATH intact
USER airflow
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
