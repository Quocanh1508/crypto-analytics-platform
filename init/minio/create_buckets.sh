#!/bin/sh
# =============================================================================
# MinIO Bucket Initialization Script
# Runs inside the minio container (or minio-mc job container) after MinIO starts
# =============================================================================
set -e

MC_ALIAS="local"
MINIO_URL="http://minio:9000"
ACCESS_KEY="${MINIO_ROOT_USER:-minioadmin}"
SECRET_KEY="${MINIO_ROOT_PASSWORD:-minioadmin}"

echo ">>> Waiting for MinIO to be ready..."
until mc alias set ${MC_ALIAS} ${MINIO_URL} ${ACCESS_KEY} ${SECRET_KEY} 2>/dev/null; do
  echo "    MinIO not ready yet, retrying in 3s..."
  sleep 3
done

echo ">>> MinIO is ready. Creating buckets..."

for BUCKET in raw bronze silver gold; do
  if mc ls ${MC_ALIAS}/${BUCKET} > /dev/null 2>&1; then
    echo "    Bucket '${BUCKET}' already exists, skipping."
  else
    mc mb ${MC_ALIAS}/${BUCKET}
    echo "    Created bucket: ${BUCKET}"
  fi
done

echo ">>> Setting public/download policy on raw bucket..."
mc anonymous set download ${MC_ALIAS}/raw

echo ">>> Bucket initialization complete. Current buckets:"
mc ls ${MC_ALIAS}
