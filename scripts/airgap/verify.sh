#!/usr/bin/env bash
# Confirm the bundle is intact. HTTP checks are optional (start.sh first).
set -euo pipefail

BUNDLE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BUNDLE"

echo "== SHA256 =="
sha256sum -c SHA256SUMS

echo "== required files =="
missing=0
require() {
  if [[ ! -e "$1" ]]; then
    echo "MISSING $1"
    missing=1
  else
    echo "ok $1"
  fi
}
require VERSION
require app/docker-compose.yml
require app/.env.example
require app/requirements.lock
require web/package.json
require web/index.html
require web/node_modules.tar.gz
require docker/images.tar.zst
require docker/images.txt
require k8s/charts
require k8s/values-platform.yaml
require k8s/values-material-research.yaml
require k8s/rbac-run-pods.yaml
require k8s/images.tar.zst
require k8s/kubeadm-images.txt
require k8s/manifests/kube-flannel.yml
require k8s/bin/helm
require docs-airgap.md
require ubuntu/k8s-debs
if [[ -f docker/images.txt ]] && ! grep -q 'dagster-celery-k8s' docker/images.txt; then
  echo "MISSING dagster-celery-k8s in docker/images.txt"
  missing=1
else
  echo "ok docker/images.txt lists dagster-celery-k8s"
fi
if ! compgen -G "ubuntu/k8s-debs/kubeadm_*.deb" >/dev/null; then
  echo "MISSING ubuntu/k8s-debs/kubeadm_*.deb"
  missing=1
else
  echo "ok ubuntu/k8s-debs/kubeadm_*.deb"
fi
if ! compgen -G "python/wheels/*.whl" >/dev/null; then
  echo "MISSING python/wheels/*.whl"
  missing=1
else
  echo "ok python/wheels ($(find python/wheels -name '*.whl' | wc -l) wheels)"
fi

echo "== docker images vs images.txt (after install-offline.sh) =="
if command -v docker >/dev/null 2>&1 && [[ -f docker/images.txt ]]; then
  while read -r img; do
    [[ -z "$img" ]] && continue
    if docker image inspect "$img" >/dev/null 2>&1; then
      echo "ok $img"
    else
      echo "not loaded $img  (run install-offline.sh)"
    fi
  done <docker/images.txt
fi

if command -v docker >/dev/null 2>&1 && [[ -f app/docker-compose.yml ]]; then
  if [[ -f app/.env ]]; then
    echo "== compose config (no pull) =="
    docker compose --project-name material-platform \
      -f "$BUNDLE/app/docker-compose.yml" config --images | sort
  else
    echo "== compose config skipped (no app/.env yet; install-offline.sh copies it) =="
  fi
fi

if command -v curl >/dev/null 2>&1; then
  echo "== HTTP =="
  curl -sfS -o /dev/null "http://127.0.0.1:8000/health" \
    && echo "api /health ok" \
    || echo "api not up yet (start.sh first)"
  curl -sfS -o /dev/null "http://127.0.0.1:3000/server_info" \
    && echo "dagster ok" \
    || echo "dagster not up yet"
fi

if [[ "$missing" -ne 0 ]]; then
  echo "bundle incomplete" >&2
  exit 1
fi
echo "verify finished."
