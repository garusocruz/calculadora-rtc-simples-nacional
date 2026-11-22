#!/usr/bin/env bash
# Configure git so Terraform can fetch private github.com modules (git::https://...).
# Writes token to /workspace/.ci/github_token (or $CI_GITHUB_TOKEN_FILE) for later CB steps.
#
# Env:
#   PROJECT_ID (required for Secret Manager)
#   GITHUB_CI_TOKEN_SECRET (default lynko-github-ci-token)
set -euo pipefail

SECRET_ID="${GITHUB_CI_TOKEN_SECRET:-lynko-github-ci-token}"
TOKEN_FILE="${CI_GITHUB_TOKEN_FILE:-/workspace/.ci/github_token}"
PROJECT_ID="${PROJECT_ID:-${GCP_PROJECT:-}}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "configure-github-git: PROJECT_ID unset — skip" >&2
  exit 0
fi

mkdir -p "$(dirname "${TOKEN_FILE}")"

TOKEN=""
if [[ -f "${TOKEN_FILE}" && -s "${TOKEN_FILE}" ]]; then
  TOKEN="$(tr -d '[:space:]' < "${TOKEN_FILE}")"
elif command -v gcloud >/dev/null 2>&1; then
  TOKEN="$(gcloud secrets versions access latest \
    --secret="${SECRET_ID}" \
    --project="${PROJECT_ID}" 2>/dev/null || true)"
  TOKEN="$(printf '%s' "${TOKEN}" | tr -d '[:space:]')"
  if [[ -n "${TOKEN}" ]]; then
    printf '%s' "${TOKEN}" >"${TOKEN_FILE}"
    chmod 600 "${TOKEN_FILE}"
  fi
fi

if [[ -z "${TOKEN}" ]]; then
  echo "configure-github-git: no token (secret ${SECRET_ID}) — private modules may fail" >&2
  exit 0
fi

if ! command -v git >/dev/null 2>&1; then
  echo "configure-github-git: git not installed" >&2
  exit 0
fi

git config --global url."https://x-access-token:${TOKEN}@github.com/".insteadOf "https://github.com/"
echo "configure-github-git: configured github.com HTTPS via ${SECRET_ID}"
