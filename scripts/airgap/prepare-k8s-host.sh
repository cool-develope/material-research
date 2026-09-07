#!/usr/bin/env bash
# Add offline Kubernetes host deps to an existing airgap-release/.
# kubeadm/kubelet/kubectl/cri-tools/kubernetes-cni are official .deb files.
# Helm has no pkgs.k8s.io package — it stays a tarball in k8s/bin/.
# Does not wipe wheels or compose images.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${AIRGAP_OUT:-$ROOT/airgap-release}"
K8S_MINOR="${K8S_MINOR:-1.32}"
HELM_VER="${HELM_VER:-v3.17.3}"
FLANNEL_VER="${FLANNEL_VER:-v0.26.7}"
FLANNEL_CNI_VER="${FLANNEL_CNI_VER:-v1.6.2-flannel1}"
SKIP_K8S_IMAGES="${SKIP_K8S_IMAGES:-0}"

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing command: $1" >&2
    exit 1
  }
}

need curl
need docker
need sha256sum
need python3
need tar
need zstd

mkdir -p \
  "$OUT/ubuntu/k8s-debs" \
  "$OUT/k8s/bin" \
  "$OUT/k8s/manifests" \
  "$OUT/k8s/charts" \
  "$OUT/scripts"

echo "== Kubernetes version (stable-${K8S_MINOR}) =="
K8S_VER="$(curl -fsSL "https://dl.k8s.io/release/stable-${K8S_MINOR}.txt")"
echo "$K8S_VER" | tee "$OUT/k8s/KUBERNETES_VERSION"
K8S_NUM="${K8S_VER#v}"

echo "== official k8s .deb packages from pkgs.k8s.io =="
REPO="https://pkgs.k8s.io/core:/stable:/v${K8S_MINOR}/deb"
curl -fsSL "${REPO}/Packages" -o /tmp/k8s-Packages
python3 - "$REPO" "$OUT/ubuntu/k8s-debs" "$K8S_NUM" <<'PY'
import re, sys, urllib.request
from pathlib import Path

repo, dest, k8s_num = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
want = {
    "kubeadm": k8s_num,
    "kubelet": k8s_num,
    "kubectl": k8s_num,
    "cri-tools": None,
    "kubernetes-cni": None,
}
blocks = Path("/tmp/k8s-Packages").read_text().split("\n\n")
picked: dict[str, tuple[str, str]] = {}
for block in blocks:
    pkg = re.search(r"^Package: (\S+)", block, re.M)
    ver = re.search(r"^Version: (\S+)", block, re.M)
    fn = re.search(r"^Filename: (\S+)", block, re.M)
    if not (pkg and ver and fn):
        continue
    name, version, filename = pkg.group(1), ver.group(1), fn.group(1)
    if name not in want or "/amd64/" not in f"/{filename}" and not filename.startswith("amd64/"):
        continue
    if not filename.startswith("amd64/"):
        continue
    pin = want[name]
    if pin and not version.startswith(pin):
        continue
    picked[name] = (version, filename)

missing = set(want) - set(picked)
if missing:
    raise SystemExit(f"missing amd64 debs in Packages: {sorted(missing)}")

dest.mkdir(parents=True, exist_ok=True)
for name, (version, filename) in sorted(picked.items()):
    url = f"{repo}/{filename}"
    out = dest / Path(filename).name
    print(f"GET {name} {version} -> {out.name}", flush=True)
    urllib.request.urlretrieve(url, out)
PY

echo "== Ubuntu runtime debs (kubelet Depends) =="
(
  cd "$OUT/ubuntu/k8s-debs"
  apt-get download \
    conntrack \
    socat \
    ebtables \
    ipset \
    iptables \
    ethtool \
    kmod \
    iproute2 \
    zstd \
    || echo "warn: apt-get download failed for Ubuntu runtime debs" >&2
)

echo "== Helm ${HELM_VER} (no official k8s deb) =="
curl -fsSL -o /tmp/helm.tgz \
  "https://get.helm.sh/helm-${HELM_VER}-linux-amd64.tar.gz"
tar -xzf /tmp/helm.tgz -C /tmp linux-amd64/helm
mv /tmp/linux-amd64/helm "$OUT/k8s/bin/helm"
rm -rf /tmp/helm.tgz /tmp/linux-amd64
chmod +x "$OUT/k8s/bin/helm"

# Drop leftover raw kube* binaries from the old layout.
rm -f \
  "$OUT/k8s/bin/kubeadm" \
  "$OUT/k8s/bin/kubelet" \
  "$OUT/k8s/bin/kubectl" \
  "$OUT/k8s/bin/crictl" \
  "$OUT/k8s/bin/kubelet.service" \
  "$OUT/k8s/bin/10-kubeadm.conf"
rm -rf "$OUT/k8s/cni"

echo "== Flannel ${FLANNEL_VER} =="
curl -fsSL -o "$OUT/k8s/manifests/kube-flannel.yml" \
  "https://github.com/flannel-io/flannel/releases/download/${FLANNEL_VER}/kube-flannel.yml"

if [[ "$SKIP_K8S_IMAGES" != "1" ]]; then
  echo "== kubeadm image list ${K8S_VER} =="
  tmp_kubeadm="$(mktemp -d)"
  dpkg-deb -x "$OUT/ubuntu/k8s-debs/kubeadm_${K8S_NUM}-"*.deb "$tmp_kubeadm"
  "$tmp_kubeadm/usr/bin/kubeadm" config images list \
    --kubernetes-version="$K8S_VER" \
    | tee "$OUT/k8s/kubeadm-images.txt"
  rm -rf "$tmp_kubeadm"
  {
    echo "ghcr.io/flannel-io/flannel:${FLANNEL_VER}"
    echo "ghcr.io/flannel-io/flannel-cni-plugin:${FLANNEL_CNI_VER}"
  } >>"$OUT/k8s/kubeadm-images.txt"
  sort -u "$OUT/k8s/kubeadm-images.txt" -o "$OUT/k8s/kubeadm-images.txt"

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

  echo "== pull control-plane + Flannel images =="
  while read -r img; do
    [[ -z "$img" ]] && continue
    pull_retry "$img"
  done <"$OUT/k8s/kubeadm-images.txt"

  echo "== save k8s images =="
  mapfile -t k8s_images <"$OUT/k8s/kubeadm-images.txt"
  docker save "${k8s_images[@]}" | zstd -T0 -10 -o "$OUT/k8s/images.tar.zst"
fi

cp "$ROOT/scripts/airgap/"*.sh "$OUT/scripts/"
chmod +x "$OUT/scripts/"*.sh

echo "== checksums =="
(
  cd "$OUT"
  find . -type f ! -name SHA256SUMS -print0 \
    | sort -z \
    | xargs -0 sha256sum >SHA256SUMS
)

echo "k8s host deps added to $OUT"
du -sh "$OUT/ubuntu/k8s-debs" "$OUT/k8s" "$OUT/k8s/images.tar.zst" 2>/dev/null || true
