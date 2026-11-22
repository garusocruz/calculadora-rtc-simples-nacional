#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PLAN_ONLY=0; AUTO_APPROVE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --plan-only) PLAN_ONLY=1; shift ;;
    --auto-approve) AUTO_APPROVE=1; shift ;;
    *) echo "unknown: $1" >&2; exit 1 ;;
  esac
done
[[ -f terraform.tfvars ]] || { echo "cp terraform.tfvars.example terraform.tfvars" >&2; exit 1; }
PROJECT_ID="$(awk -F'\"' '/^project_id/{print $2; exit}' terraform.tfvars)"
REGION="$(awk -F'\"' '/^region/{print $2; exit}' terraform.tfvars)"; REGION="${REGION:-us-central1}"
STATE_BUCKET="${TF_STATE_BUCKET:-${PROJECT_ID}-tfstate}"
PREFIX="${TF_STATE_PREFIX:-libs/fast_flow}"
if command -v gcloud >/dev/null 2>&1; then
  gcloud storage buckets describe "gs://${STATE_BUCKET}" --project="${PROJECT_ID}" >/dev/null 2>&1 ||     gcloud storage buckets create "gs://${STATE_BUCKET}" --project="${PROJECT_ID}" --location="${REGION}" --uniform-bucket-level-access
fi
[[ -f backend.tf ]] || cat > backend.tf <<'BE'
terraform {
  backend "gcs" {}
}
BE
terraform init -input=false -backend-config="bucket=${STATE_BUCKET}" -backend-config="prefix=${PREFIX}" -reconfigure
terraform validate
if [[ "$PLAN_ONLY" == "1" ]]; then terraform plan -input=false -out=tfplan; exit 0; fi
ARGS=(-input=false); [[ "$AUTO_APPROVE" == "1" ]] && ARGS+=(-auto-approve)
terraform apply "${ARGS[@]}"; terraform output
