#!/usr/bin/env bash
# Build airgap-release/: wheels, web UI, compose + project image,
# official Dagster control-plane image, Helm charts, kubeadm host deps.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${AIRGAP_OUT:-$ROOT/airgap-release}"
VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$ROOT/pyproject.toml" | head -1)"
DAGSTER_VER="$(awk '/^name = "dagster"$/{getline; gsub(/"/, "", $3); print $3; exit}' "$ROOT/uv.lock")"
SKIP_DOCKER="${SKIP_DOCKER:-0}"
SKIP_WHEELS="${SKIP_WHEELS:-0}"
SKIP_WEB="${SKIP_WEB:-0}"
SKIP_K8S="${SKIP_K8S:-0}"

cd "$ROOT"
export PATH="${HOME}/.local/node/bin:${PATH}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing command: $1" >&2
    exit 1
  }
}

need python3
need uv
need sha256sum
need curl

echo "== platform =="
{
  echo "bundle_version=$VERSION"
  echo "dagster=$DAGSTER_VER"
  echo "uname=$(uname -s) $(uname -m) $(uname -r)"
  python3 --version
} | tee /tmp/mp-airgap-platform.txt

rm -rf "$OUT"
mkdir -p \
  "$OUT/app" \
  "$OUT/python/wheels" \
  "$OUT/docker" \
  "$OUT/web" \
  "$OUT/k8s/charts" \
  "$OUT/scripts"

echo "$VERSION" >"$OUT/VERSION"
cp /tmp/mp-airgap-platform.txt "$OUT/PLATFORM"

cp "$ROOT/Dockerfile" "$OUT/app/Dockerfile"
cp "$ROOT/docker/Dockerfile.wheels" "$OUT/app/Dockerfile.wheels"
cp "$ROOT/docker-compose.yml" "$OUT/app/docker-compose.yml"
cp "$ROOT/.env.example" "$OUT/app/.env.example"
cp "$ROOT/dagster.yaml" "$OUT/app/dagster.yaml"
cp "$ROOT/workspace.yaml" "$OUT/app/workspace.yaml"
cp "$ROOT/alembic.ini" "$OUT/app/alembic.ini"
cp "$ROOT/scripts/airgap/"*.sh "$OUT/scripts/"
chmod +x "$OUT/scripts/"*.sh
cp "$ROOT/docs/airgap.md" "$OUT/docs-airgap.md"

echo "== freeze Python deps (runtime + k8s extra) =="
uv export --frozen --no-dev --extra k8s --no-emit-project --no-hashes \
  -o "$OUT/app/requirements.lock"
uv export --frozen --no-dev --no-emit-project --no-hashes \
  -o "$OUT/app/requirements-compose.lock"
cp "$OUT/app/requirements.lock" "$ROOT/requirements.lock"

if [[ "$SKIP_WHEELS" != "1" ]]; then
  echo "== Python wheelhouse =="
  rm -rf /tmp/mp-airgap-download
  uv venv --seed /tmp/mp-airgap-download
  /tmp/mp-airgap-download/bin/pip install -q --upgrade pip
  PIP_DL=(/tmp/mp-airgap-download/bin/pip download -d "$OUT/python/wheels")
  # brotli 1.2.0 (and a few others) publish manylinux_2_17 / manylinux2014,
  # not manylinux_2_28. pip --platform is exact, so list all three.
  set +e
  "${PIP_DL[@]}" \
    --python-version 3.12 \
    --platform manylinux_2_28_x86_64 \
    --platform manylinux_2_17_x86_64 \
    --platform manylinux2014_x86_64 \
    --implementation cp \
    --abi cp312 \
    --only-binary=:all: \
    -r "$OUT/app/requirements.lock"
  wheel_rc=$?
  set -e
  if [[ "$wheel_rc" -ne 0 ]]; then
    echo "manylinux-only failed; downloading for this interpreter" >&2
    "${PIP_DL[@]}" -r "$OUT/app/requirements.lock"
  fi
  "${PIP_DL[@]}" pip setuptools wheel hatchling
  uv build --wheel -o "$OUT/python/wheels"
  rm -rf /tmp/mp-airgap-download

  echo "== verify wheelhouse =="
  rm -rf /tmp/mp-airgap-venv
  uv venv --seed /tmp/mp-airgap-venv
  /tmp/mp-airgap-venv/bin/pip install -q --upgrade pip
  /tmp/mp-airgap-venv/bin/pip install \
    --no-index \
    --find-links="$OUT/python/wheels" \
    -r "$OUT/app/requirements.lock"
  /tmp/mp-airgap-venv/bin/pip install \
    --no-index \
    --find-links="$OUT/python/wheels" \
    material-platform
  /tmp/mp-airgap-venv/bin/pip check
  /tmp/mp-airgap-venv/bin/python - <<'PY'
import dagster
import dagster_k8s
import dagster_postgres
import fastapi
print("dagster", dagster.__version__)
print("dagster_k8s ok")
print("dagster_postgres ok")
PY
  rm -rf /tmp/mp-airgap-venv
fi

if [[ "$SKIP_WEB" != "1" ]] && command -v npm >/dev/null 2>&1; then
  echo "== web source + Node modules =="
  mkdir -p "$OUT/web"
  tar -C "$ROOT/web" --exclude=node_modules --exclude=dist -cf - . \
    | tar -C "$OUT/web" -xf -
  (
    cd "$ROOT/web"
    for attempt in 1 2 3 4 5; do
      if npm ci; then
        break
      fi
      echo "npm ci failed (attempt ${attempt}); retry in 5s" >&2
      sleep 5
      if [[ "$attempt" -eq 5 ]]; then
        exit 1
      fi
    done
    tar -czf "$OUT/web/node_modules.tar.gz" node_modules
  )
else
  echo "skip web"
fi

if [[ "$SKIP_K8S" != "1" ]]; then
  echo "== Dagster Helm charts ${DAGSTER_VER} =="
  mkdir -p "$OUT/k8s"
  curl -fsSL -o "$OUT/k8s/charts/dagster-${DAGSTER_VER}.tgz" \
    "https://dagster-io.github.io/helm/dagster-${DAGSTER_VER}.tgz"
  curl -fsSL -o "$OUT/k8s/charts/dagster-user-deployments-${DAGSTER_VER}.tgz" \
    "https://dagster-io.github.io/helm/dagster-user-deployments-${DAGSTER_VER}.tgz"
  cp "$ROOT/k8s/"*.yaml "$OUT/k8s/"
  sed -i "s/tag: \"1.13.20\"/tag: \"${DAGSTER_VER}\"/g" \
    "$OUT/k8s/values-platform.yaml"
fi

retag_if_present() {
  local from="$1" to="$2"
  if docker image inspect "$from" >/dev/null 2>&1; then
    docker tag "$from" "$to"
  fi
}

if [[ "$SKIP_DOCKER" != "1" ]]; then
  need docker
  if [[ ! -f "$ROOT/.env" ]]; then
    cp "$ROOT/.env.example" "$ROOT/.env"
    echo "created .env from .env.example for compose build"
  fi
  echo "== retag floating local images =="
  retag_if_present postgres:16 postgres:16.15
  retag_if_present redis:7 redis:7.4.11
  retag_if_present minio/minio:latest minio/minio:RELEASE.2025-09-07T16-13-09Z
  retag_if_present minio/mc:latest minio/mc:RELEASE.2025-08-13T08-35-41Z
  retag_if_present docker.langfuse.com/langfuse/langfuse:4 \
    docker.langfuse.com/langfuse/langfuse:4.27.0
  retag_if_present docker.langfuse.com/langfuse/langfuse-worker:4 \
    docker.langfuse.com/langfuse/langfuse-worker:4.27.0

  pull_if_missing() {
    local img="$1"
    if docker image inspect "$img" >/dev/null 2>&1; then
      echo "have $img"
    else
      docker pull "$img"
    fi
  }

  echo "== compose images + app build =="
  while read -r img; do
    [[ "$img" == material-platform:* ]] && continue
    pull_if_missing "$img"
  done < <(docker compose -f "$ROOT/docker-compose.yml" config --images | sort -u)

  docker compose -f "$ROOT/docker-compose.yml" build

  docker compose -f "$ROOT/docker-compose.yml" config --images \
    | sort -u >"$OUT/docker/images.txt"

  if [[ "$SKIP_K8S" != "1" ]]; then
    pull_retry() {
      local img="$1" n
      if docker image inspect "$img" >/dev/null 2>&1; then
        echo "have $img"
        return 0
      fi
      for n in 1 2 3 4 5; do
        echo "pull $img attempt $n"
        if docker pull "$img"; then
          return 0
        fi
        sleep 5
      done
      echo "failed to pull $img" >&2
      return 1
    }
    echo "== Dagster control-plane image (not the project image) =="
    pull_retry "docker.io/dagster/dagster-celery-k8s:${DAGSTER_VER}"
    pull_retry docker.io/busybox:1.28
    {
      echo "docker.io/dagster/dagster-celery-k8s:${DAGSTER_VER}"
      echo "docker.io/busybox:1.28"
    } >>"$OUT/docker/images.txt"
    sort -u "$OUT/docker/images.txt" -o "$OUT/docker/images.txt"
  fi

  echo "== docker save (stream to zstd) =="
  mapfile -t images <"$OUT/docker/images.txt"
  set +e
  docker save "${images[@]}" | zstd -T0 -10 -o "$OUT/docker/images.tar.zst"
  save_rc=$?
  set -e
  if [[ "$save_rc" -ne 0 ]]; then
    echo "warn: docker save failed (often disk). images.txt is still in the bundle." >&2
    rm -f "$OUT/docker/images.tar.zst"
  fi
fi

if [[ "$SKIP_K8S" != "1" ]]; then
  echo "== Kubernetes host deps (kubeadm, Helm, Flannel, Ubuntu debs) =="
  AIRGAP_OUT="$OUT" "$ROOT/scripts/airgap/prepare-k8s-host.sh"
else
  echo "== checksums =="
  (
    cd "$OUT"
    find . -type f ! -name SHA256SUMS -print0 \
      | sort -z \
      | xargs -0 sha256sum >SHA256SUMS
  )
fi

cat >"$OUT/README.md" <<EOF
# Material Platform deps bundle $VERSION

See docs-airgap.md (repo docs/airgap.md).

Shared Dagster control plane: \`docker.io/dagster/dagster-celery-k8s:${DAGSTER_VER}\`.
This project code location: \`material-platform:${VERSION}\`.
Docker Engine is not bundled.

## Compose only (local shortcut)

\`\`\`bash
sha256sum -c SHA256SUMS
./scripts/install-offline.sh
# edit app/.env
./scripts/start.sh
\`\`\`

## Kubernetes (shared instance + this project)

\`\`\`bash
sha256sum -c SHA256SUMS
./scripts/install-k8s-offline.sh
# then the printed kubeadm init + flannel apply
./scripts/install-offline.sh
# CREATE DATABASE dagster;  (not material / langfuse)
PG_HOST=YOUR_PG_HOST PG_PASSWORD=YOUR_PG_PASSWORD ./scripts/install-dagster.sh
\`\`\`

| Path | Contents |
| --- | --- |
| \`python/wheels/\` | this project + dagster-k8s (code location) |
| \`web/\` | Vite source + node_modules.tar.gz |
| \`docker/images.tar.zst\` | compose + material-platform + dagster-celery-k8s |
| \`k8s/charts/\` | dagster + dagster-user-deployments |
| \`k8s/values-platform.yaml\` | webserver / daemon |
| \`k8s/values-material-research.yaml\` | this code location |
| \`k8s/images.tar.zst\` | kubeadm + Flannel |
| \`ubuntu/k8s-debs/\` | kubeadm kubelet kubectl + runtime |
| \`k8s/bin/helm\` | Helm |

Point \`LLM_BASE_URL\` / \`EMBEDDER=http\` at servers on your network.
EOF

echo
echo "bundle: $OUT"
du -sh "$OUT" "$OUT"/python/wheels "$OUT"/docker "$OUT"/web "$OUT"/k8s 2>/dev/null || true
echo "done."
