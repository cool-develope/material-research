#!/usr/bin/env bash
# Load Docker images and unpack Node modules. Docker Engine is assumed present.
set -euo pipefail

BUNDLE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BUNDLE"

if [[ ! -f SHA256SUMS ]]; then
  echo "run this from an airgap-release tree (missing SHA256SUMS)" >&2
  exit 1
fi

echo "== checksums =="
sha256sum -c SHA256SUMS

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed (not part of this bundle)" >&2
  exit 1
fi

load_images() {
  if [[ -f docker/images.tar.zst ]]; then
    zstd -dc docker/images.tar.zst | docker load
  elif [[ -f docker/images.tar ]]; then
    docker load -i docker/images.tar
  else
    echo "no docker/images.tar.zst in this bundle" >&2
    exit 1
  fi
}

echo "== docker load =="
if ! load_images 2>/dev/null; then
  sudo zstd -dc docker/images.tar.zst | sudo docker load
fi

if [[ -f web/node_modules.tar.gz ]]; then
  echo "== Node modules =="
  if [[ ! -f web/index.html ]]; then
    echo "warn: web/index.html missing — bundle should include Vite source" >&2
  fi
  tar -xzf web/node_modules.tar.gz -C web
fi

if [[ ! -f app/.env ]]; then
  cp app/.env.example app/.env
  echo "wrote app/.env from .env.example — edit secrets before start.sh"
fi

mkdir -p "$BUNDLE/inbox"
echo "images loaded (control plane: dagster-celery-k8s; project: material-platform)."
echo "Compose: ./scripts/start.sh"
echo "New cluster: ./scripts/install-k8s-offline.sh"
echo "Helm: PG_HOST=... ./scripts/install-dagster.sh"
