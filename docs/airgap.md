# Air-gap deps bundle

Python **3.12**, amd64. Output is gitignored (`airgap-release/`).

Build on an online machine that matches production (Ubuntu 24.04, amd64):

```bash
./scripts/airgap/prepare-online.sh
```

That writes wheels, Node modules, compose/app images, Dagster Helm charts, then calls `prepare-k8s-host.sh` (kubeadm `.deb` files, Flannel, Helm, control-plane images). Incremental host-only refresh:

```bash
./scripts/airgap/prepare-k8s-host.sh
```

Skip while iterating: `SKIP_DOCKER=1`, `SKIP_WHEELS=1`, `SKIP_WEB=1`, `SKIP_K8S=1`. Host-image refresh skip: `SKIP_K8S_IMAGES=1`.

## What is in the bundle

| Path | Role |
| --- | --- |
| `python/wheels/` | `pip install --no-index --find-links` (app + `dagster-k8s` + `dagster-postgres`) |
| `web/` | Vite UI source + `node_modules.tar.gz` |
| `docker/images.tar.zst` | Compose stack + `material-platform:0.1.0` + `busybox:1.28` |
| `ubuntu/k8s-debs/` | `kubeadm` `kubelet` `kubectl` `cri-tools` `kubernetes-cni` + conntrack/socat/iptables/zstd |
| `k8s/bin/helm` | Helm binary (no official k8s `.deb`) |
| `k8s/images.tar.zst` | kubeadm control-plane + Flannel |
| `k8s/manifests/kube-flannel.yml` | Pod network |
| `k8s/charts/` | `dagster` + `dagster-user-deployments` (same version as `uv.lock`) |
| `k8s/values.yaml` | Existing Postgres, `K8sRunLauncher`, this app image |
| `app/` | compose file, `.env.example`, Dagster workspace, Alembic ini |

**Not bundled:** Docker Engine / containerd (install from your Ubuntu media first). LLM / embed / rerank weights — point `LLM_BASE_URL` and `EMBEDDER=http` at servers on your network.

## Two ways to run

### A. Compose only (no Kubernetes)

Needs: Docker Engine, `zstd`.

```bash
cd airgap-release
sha256sum -c SHA256SUMS
./scripts/install-offline.sh
# edit app/.env
./scripts/start.sh
./scripts/verify.sh
```

Then: API http://127.0.0.1:8000, Dagster http://127.0.0.1:3000, Langfuse http://127.0.0.1:3100.

Web UI (Node 22+ on the host):

```bash
cd web && npm run preview -- --host 127.0.0.1 --port 5173
```

`install-offline.sh` unpacks `web/node_modules.tar.gz` on top of the bundled `web/` source.

### B. Kubernetes for Dagster

Needs: Docker Engine **and** containerd (`ctr`), plus the `.deb` set above.

Postgres / MinIO / Qdrant / Redis / ClickHouse / Langfuse are **not** Helm-packaged. Run them with path A (`start.sh`) or point Helm at servers you already have.

```bash
cd airgap-release
sha256sum -c SHA256SUMS
./scripts/install-k8s-offline.sh
# script prints kubeadm init — run it once:
sudo kubeadm init --kubernetes-version=v1.32.13 \
  --pod-network-cidr=10.244.0.0/16 \
  --cri-socket=unix:///run/containerd/containerd.sock
mkdir -p "$HOME/.kube"
sudo cp /etc/kubernetes/admin.conf "$HOME/.kube/config"
sudo chown "$(id -u):$(id -g)" "$HOME/.kube/config"
kubectl apply -f k8s/manifests/kube-flannel.yml
kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true

./scripts/install-offline.sh    # docker load + unpack web
# also imports compose images into containerd so Helm can see material-platform

helm upgrade --install dagster k8s/charts/dagster-1.13.20.tgz -f k8s/values.yaml \
  --set postgresql.postgresqlHost=YOUR_PG_HOST \
  --set postgresql.postgresqlPassword=YOUR_PG_PASSWORD
```

`install-k8s-offline.sh` already `ctr -n k8s.io images import`s `k8s/images.tar.zst` **and** `docker/images.tar.zst` (Dagster pods pull from the CRI, not from `docker images`).

Helm webserver, daemon, and user code all use `material-platform:0.1.0`. `busybox:1.28` is the Helm Postgres check image.

If `kubeadm init` fails on a Docker-only host, set containerd to `SystemdCgroup = true` and load `overlay` / `br_netfilter`.

## Prepare (online)

| Script | Writes |
| --- | --- |
| `scripts/airgap/prepare-online.sh` | wheels, web, compose images, charts; then host deps |
| `scripts/airgap/prepare-k8s-host.sh` | k8s `.deb` files, Helm, Flannel, control-plane images |

## Offline scripts

| Script | Does |
| --- | --- |
| `scripts/install-k8s-offline.sh` | `apt install` kube debs, install Helm, import both image tars into containerd, enable kubelet |
| `scripts/install-offline.sh` | checksums, `docker load` compose tar, unpack Node modules, copy `.env` |
| `scripts/start.sh` | `docker compose up --pull never --no-build`, Alembic |
| `scripts/verify.sh` | checksums, required files, compose image tags, optional HTTP |
