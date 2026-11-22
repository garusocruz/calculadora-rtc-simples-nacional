#!/usr/bin/env bash
# Filesystem Trivy scan via official container (no native install).
# https://trivy.dev/docs/latest/getting-started/installation/
# Image: docker.io/aquasec/trivy
set -euo pipefail

ROOT="$(cd "${1:?ROOT dir required}" && pwd)"
shift

TRIVY_VERSION="${TRIVY_VERSION:-v0.74.0}"
TRIVY_IMAGE="${TRIVY_IMAGE:-docker.io/aquasec/trivy:${TRIVY_VERSION#v}}"
CACHE_DIR="${TRIVY_CACHE_DIR:-${ROOT}/.ci/trivy-cache}"
CACHE_MOUNT="/tmp/trivy-cache"
DOCKER_CLI_VERSION="${DOCKER_CLI_VERSION:-27.3.1}"
mkdir -p "${CACHE_DIR}"

ensure_docker_cli() {
  if command -v docker >/dev/null 2>&1; then
    return 0
  fi
  # Cloud Build cloud-sdk steps have the daemon socket but often no client.
  local arch tgz
  case "$(uname -m)" in
    x86_64|amd64) arch="x86_64" ;;
    aarch64|arm64) arch="aarch64" ;;
    *)
      echo "FAIL: unsupported arch $(uname -m) for static docker CLI" >&2
      return 1
      ;;
  esac
  tgz="$(mktemp)"
  curl -fsSL \
    "https://download.docker.com/linux/static/stable/${arch}/docker-${DOCKER_CLI_VERSION}.tgz" \
    -o "${tgz}"
  tar -xzf "${tgz}" -C /tmp "docker/docker"
  rm -f "${tgz}"
  install -m 0755 /tmp/docker/docker /usr/local/bin/docker
  rm -rf /tmp/docker
  command -v docker >/dev/null 2>&1
}

if ! ensure_docker_cli; then
  echo "FAIL: docker is required to run ${TRIVY_IMAGE}" >&2
  exit 1
fi

# Run as host uid/gid so bind-mounted cache is not root-owned (pre-push mktemp cleanup).
# Absolute mounts so CB (/workspace) and local paths both work.
exec docker run --rm \
  --user "$(id -u):$(id -g)" \
  -e TRIVY_CACHE_DIR="${CACHE_MOUNT}" \
  -v "${CACHE_DIR}:${CACHE_MOUNT}" \
  -v "${ROOT}:${ROOT}" \
  -w "${ROOT}" \
  "${TRIVY_IMAGE}" \
  "$@"
