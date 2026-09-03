#!/bin/sh
set -eu
mkdir -p "${DAGSTER_HOME:-/opt/dagster}" /inbox
if [ ! -f "${DAGSTER_HOME}/dagster.yaml" ]; then
  cp /app/dagster.yaml "${DAGSTER_HOME}/dagster.yaml"
fi
exec "$@"
