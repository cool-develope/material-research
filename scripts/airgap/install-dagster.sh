#!/usr/bin/env bash
# Shared Dagster control plane + this repo as one code location.
# Webserver/daemon: docker.io/dagster/dagster-celery-k8s
# Runs / gRPC: material-platform (project image only)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "$HERE/../k8s" ]]; then
  BUNDLE="$(cd "$HERE/.." && pwd)"
else
  BUNDLE="$(cd "$HERE/../.." && pwd)"
fi
cd "$BUNDLE"
if [[ -x "$BUNDLE/k8s/bin/helm" ]]; then
  export PATH="$BUNDLE/k8s/bin:$PATH"
fi

PLATFORM_NS="${PLATFORM_NS:-dagster-system}"
PROJECT_NS="${PROJECT_NS:-material-research}"
PROJECT_RELEASE="${PROJECT_RELEASE:-material-research}"
PLATFORM_VALUES="${PLATFORM_VALUES:-k8s/values-platform.yaml}"
PROJECT_VALUES="${PROJECT_VALUES:-k8s/values-material-research.yaml}"

if ! command -v helm >/dev/null 2>&1; then
  echo "helm is not on PATH — run install-k8s-offline.sh first" >&2
  exit 1
fi
if ! command -v kubectl >/dev/null 2>&1; then
  echo "kubectl is not on PATH — run install-k8s-offline.sh first" >&2
  exit 1
fi
if ! kubectl cluster-info >/dev/null 2>&1; then
  echo "no cluster — kubeadm init first (printed by install-k8s-offline.sh)" >&2
  exit 1
fi

shopt -s nullglob
platform_charts=()
user_charts=()
for f in k8s/charts/dagster-*.tgz; do
  if [[ "$f" == *user-deployments* ]]; then
    user_charts+=("$f")
  else
    platform_charts+=("$f")
  fi
done
if [[ "${#platform_charts[@]}" -eq 0 || "${#user_charts[@]}" -eq 0 ]]; then
  echo "missing Helm charts in k8s/charts/ — run prepare-online.sh" >&2
  exit 1
fi
shopt -u nullglob
[[ -f "$PLATFORM_VALUES" && -f "$PROJECT_VALUES" ]] || {
  echo "missing $PLATFORM_VALUES or $PROJECT_VALUES" >&2
  exit 1
}

PG_HOST="${PG_HOST:-${DAGSTER_PG_HOST:-}}"
PG_PASSWORD="${PG_PASSWORD:-${DAGSTER_PG_PASSWORD:-material}}"
PG_USER="${PG_USER:-${DAGSTER_PG_USER:-material}}"
PG_DB="${PG_DB:-${DAGSTER_PG_DB:-dagster}}"
if [[ -z "$PG_HOST" ]]; then
  echo "set PG_HOST to Postgres the pods can reach (not 127.0.0.1)" >&2
  echo "  create database ${PG_DB} on that server (separate from material / langfuse)" >&2
  echo "  PG_HOST=10.0.0.5 PG_PASSWORD=material $0" >&2
  exit 1
fi

echo "== namespaces ${PLATFORM_NS} ${PROJECT_NS} =="
kubectl create namespace "$PLATFORM_NS" --dry-run=client -o yaml | kubectl apply -f -
kubectl create namespace "$PROJECT_NS" --dry-run=client -o yaml | kubectl apply -f -
# User-code chart reads DAGSTER_PG_PASSWORD from this name in its own namespace.
kubectl create secret generic dagster-postgresql-secret \
  --namespace "$PROJECT_NS" \
  --from-literal=postgresql-password="$PG_PASSWORD" \
  --dry-run=client -o yaml | kubectl apply -f -

ENV_FILE=""
if [[ -f app/.env ]]; then
  ENV_FILE=app/.env
elif [[ -f .env ]]; then
  ENV_FILE=.env
fi
if [[ -n "$ENV_FILE" ]]; then
  echo "== project secret from ${ENV_FILE} (not in the control-plane image) =="
  kubectl create secret generic material-research-env \
    --namespace "$PROJECT_NS" \
    --from-env-file="$ENV_FILE" \
    --dry-run=client -o yaml | kubectl apply -f -
else
  echo "warn: no app/.env — create secret material-research-env in ${PROJECT_NS}" >&2
fi

echo "== code location ${PROJECT_RELEASE} (${PROJECT_NS}) =="
helm upgrade --install "$PROJECT_RELEASE" "${user_charts[0]}" \
  --namespace "$PROJECT_NS" \
  -f "$PROJECT_VALUES"

CODE_SVC="$(kubectl get svc -n "$PROJECT_NS" -o jsonpath='{.items[0].metadata.name}')"
CODE_HOST="${CODE_HOST:-${CODE_SVC}.${PROJECT_NS}.svc.cluster.local}"
echo "workspace gRPC: ${CODE_HOST}:3030"

echo "== control plane dagster (${PLATFORM_NS}) =="
helm upgrade --install dagster "${platform_charts[0]}" \
  --namespace "$PLATFORM_NS" \
  -f "$PLATFORM_VALUES" \
  --set postgresql.postgresqlHost="$PG_HOST" \
  --set postgresql.postgresqlPassword="$PG_PASSWORD" \
  --set postgresql.postgresqlUsername="$PG_USER" \
  --set postgresql.postgresqlDatabase="$PG_DB" \
  --set-string "dagsterWebserver.workspace.servers[0].host=$CODE_HOST" \
  --set "dagsterWebserver.workspace.servers[0].port=3030" \
  --set-string "dagsterWebserver.workspace.servers[0].name=material-research" \
  --set runLauncher.config.k8sRunLauncher.jobNamespace="$PROJECT_NS"

DAEMON_SA="$(kubectl get deploy -n "$PLATFORM_NS" \
  -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.template.spec.serviceAccountName}{"\n"}{end}' \
  | awk '/daemon/{print $2; exit}')"
if [[ -z "$DAEMON_SA" ]]; then
  DAEMON_SA="dagster"
fi
echo "== run-pod RBAC (daemon SA ${DAEMON_SA} -> ${PROJECT_NS}) =="
tmp="$(mktemp)"
sed \
  -e "s/PLACEHOLDER_DAEMON_SA/${DAEMON_SA}/g" \
  -e "s/namespace: material-research/namespace: ${PROJECT_NS}/g" \
  -e "s/namespace: dagster-system/namespace: ${PLATFORM_NS}/g" \
  k8s/rbac-run-pods.yaml >"$tmp"
kubectl apply -f "$tmp"
rm -f "$tmp"

echo
echo "Shared instance: ${PLATFORM_NS}  (official dagster-celery-k8s)"
echo "This project:    ${PROJECT_NS}  (material-platform code location + run pods)"
echo "  kubectl get pods -n ${PLATFORM_NS}"
echo "  kubectl get pods -n ${PROJECT_NS}"
echo "  kubectl -n ${PLATFORM_NS} port-forward svc/dagster-dagster-webserver 3000:80"
echo "UI: http://127.0.0.1:3000"
echo "Add another project: another user-deployments release + a workspace.servers entry."
