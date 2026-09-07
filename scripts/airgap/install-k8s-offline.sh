#!/usr/bin/env bash
# Install Kubernetes on an offline Ubuntu host from .deb packages, then print
# kubeadm init + Helm. Docker/containerd is assumed already present.
set -euo pipefail

BUNDLE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BUNDLE"

if [[ ! -f k8s/KUBERNETES_VERSION ]]; then
  echo "missing k8s/KUBERNETES_VERSION — run prepare-k8s-host.sh online first" >&2
  exit 1
fi

K8S_VER="$(cat k8s/KUBERNETES_VERSION)"

if ! compgen -G "ubuntu/k8s-debs/kubeadm_*.deb" >/dev/null; then
  echo "missing ubuntu/k8s-debs/kubeadm_*.deb" >&2
  exit 1
fi

echo "== apt install kubeadm kubelet kubectl cri-tools kubernetes-cni + runtime =="
sudo apt-get install -y ./ubuntu/k8s-debs/*.deb
sudo apt-mark hold kubeadm kubelet kubectl cri-tools kubernetes-cni || true

if [[ -x k8s/bin/helm ]]; then
  echo "== Helm =="
  sudo install -m 0755 k8s/bin/helm /usr/local/bin/helm
fi

echo "== load images into containerd (k8s.io namespace) =="
if [[ ! -f k8s/images.tar.zst ]]; then
  echo "missing k8s/images.tar.zst" >&2
  exit 1
fi
zstd -dc k8s/images.tar.zst | sudo ctr -n k8s.io images import -
if [[ -f docker/images.tar.zst ]]; then
  echo "== also import compose/app images (material-platform, busybox, postgres) =="
  zstd -dc docker/images.tar.zst | sudo ctr -n k8s.io images import -
fi

sudo swapoff -a || true
sudo systemctl daemon-reload
sudo systemctl enable --now kubelet

echo
echo "Packages and images are on this host. Initialize the cluster (once):"
echo
echo "  sudo kubeadm init --kubernetes-version=${K8S_VER} \\"
echo "    --pod-network-cidr=10.244.0.0/16 \\"
echo "    --cri-socket=unix:///run/containerd/containerd.sock"
echo
echo "  mkdir -p \$HOME/.kube"
echo "  sudo cp /etc/kubernetes/admin.conf \$HOME/.kube/config"
echo "  sudo chown \"\$(id -u):\$(id -g)\" \$HOME/.kube/config"
echo "  kubectl apply -f ${BUNDLE}/k8s/manifests/kube-flannel.yml"
echo "  kubectl taint nodes --all node-role.kubernetes.io/control-plane- || true"
echo
echo "Load app / compose images if not already:"
echo "  ${BUNDLE}/scripts/install-offline.sh"
echo
echo "Then install Dagster:"
echo "  helm upgrade --install dagster ${BUNDLE}/k8s/charts/dagster-*.tgz \\"
echo "    -f ${BUNDLE}/k8s/values.yaml \\"
echo "    --set postgresql.postgresqlHost=YOUR_PG_HOST \\"
echo "    --set postgresql.postgresqlPassword=YOUR_PG_PASSWORD"
