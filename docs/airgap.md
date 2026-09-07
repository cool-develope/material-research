# Air-gap deps bundle

Python **3.12**, amd64. Output is gitignored (`airgap-release/`).

```bash
./scripts/airgap/prepare-online.sh
```

That writes wheels, Node modules, compose/project images, the **official Dagster control-plane image**, Helm charts, then `prepare-k8s-host.sh` (kubeadm `.deb` files, Flannel, Helm, kubeadm images). Incremental host-only refresh:

```bash
./scripts/airgap/prepare-k8s-host.sh
```

Skip while iterating: `SKIP_DOCKER=1`, `SKIP_WHEELS=1`, `SKIP_WEB=1`, `SKIP_K8S=1`. Host-image refresh skip: `SKIP_K8S_IMAGES=1`.

## Dagster layout (Kubernetes)

One shared instance. This repo is **one code location**, not the webserver image.

```text
dagster-system                          official dagster-celery-k8s
  webserver + daemon + Dagster Postgres (database `dagster`)

material-research                       material-platform:0.1.0
  long-lived gRPC code-location pod
  ephemeral K8s run pods (one per job)

shared data (compose or existing)
  Postgres (material / langfuse / langgraph DBs)
  MinIO, Qdrant, Redis, Langfuse
```

Do not install project libraries into the webserver image. A later project (crawler, analytics) gets its own image + `dagster-user-deployments` release + one `workspace.servers` entry.

Project secrets stay in `material-research-env` (from `app/.env`). They are not baked into the control-plane image.

## What is in the bundle

| Path | Role |
| --- | --- |
| `python/wheels/` | This project + `dagster-k8s` (code location / run pods) |
| `web/` | Vite UI source + `node_modules.tar.gz` |
| `docker/images.tar.zst` | Compose stack + `material-platform` + `dagster-celery-k8s` + `busybox:1.28` |
| `ubuntu/k8s-debs/` | `kubeadm` `kubelet` `kubectl` `cri-tools` `kubernetes-cni` + runtime + zstd |
| `k8s/bin/helm` | Helm binary |
| `k8s/images.tar.zst` | kubeadm + Flannel |
| `k8s/manifests/kube-flannel.yml` | Pod network |
| `k8s/charts/` | `dagster` + `dagster-user-deployments` |
| `k8s/values-platform.yaml` | Shared webserver / daemon |
| `k8s/values-material-research.yaml` | This code location |
| `k8s/rbac-run-pods.yaml` | Daemon may create Jobs in the project namespace |
| `app/` | compose file, `.env.example`, workspace, Alembic ini |

**Not bundled:** Docker Engine / containerd. LLM / embed / rerank weights — point `LLM_BASE_URL` and `EMBEDDER=http` at your network.

## Two ways to run

### A. Compose only (local shortcut)

Needs: Docker Engine, `zstd`. UI and daemon run in `material-platform` on one box. That is not the Kubernetes model.

```bash
cd airgap-release
sha256sum -c SHA256SUMS
./scripts/install-offline.sh
# edit app/.env
./scripts/start.sh
./scripts/verify.sh
```

API http://127.0.0.1:8000, Dagster http://127.0.0.1:3000, Langfuse http://127.0.0.1:3100.

```bash
cd web && npm run preview -- --host 127.0.0.1 --port 5173
```

### B. Kubernetes (shared instance)

Needs: Docker Engine **and** containerd (`ctr`).

Create a **`dagster`** database on Postgres (not `material` / `langfuse` / `langgraph`). `PG_HOST` must be reachable from pods (node IP if compose Postgres is on this box — not `127.0.0.1`).

```bash
cd airgap-release
sha256sum -c SHA256SUMS
./scripts/install-k8s-offline.sh
sudo kubeadm init --kubernetes-version=v1.32.13 \
  --pod-network-cidr=10.244.0.0/16 \
  --cri-socket=unix:///run/containerd/containerd.sock
mkdir -p "$HOME/.kube"
sudo cp /etc/kubernetes/admin.conf "$HOME/.kube/config"
sudo chown "$(id -u):$(id -g)" "$HOME/.kube/config"
kubectl apply -f k8s/manifests/kube-flannel.yml
kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true

./scripts/install-offline.sh
PG_HOST=YOUR_PG_HOST PG_PASSWORD=YOUR_PG_PASSWORD ./scripts/install-dagster.sh
kubectl -n dagster-system port-forward svc/dagster-dagster-webserver 3000:80
```

`install-dagster.sh` creates `dagster-system` and `material-research`, installs both Helm releases, loads `app/.env` into secret `material-research-env`, and binds the daemon ServiceAccount so it can launch run pods in the project namespace.

If `kubeadm init` fails on a Docker-only host, set containerd to `SystemdCgroup = true` and load `overlay` / `br_netfilter`.

## Offline scripts

| Script | Does |
| --- | --- |
| `scripts/install-k8s-offline.sh` | kubeadm debs, Helm, import image tars into containerd |
| `scripts/install-offline.sh` | `docker load`, unpack Node modules, copy `.env` |
| `scripts/install-dagster.sh` | Helm control plane + this code location (`PG_HOST` required) |
| `scripts/start.sh` | compose stack (local shortcut) |
| `scripts/verify.sh` | checksums and required files |
