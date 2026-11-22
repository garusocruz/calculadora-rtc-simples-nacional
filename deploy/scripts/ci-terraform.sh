#!/usr/bin/env bash
# Run this lib's Terraform from Cloud Build (or locally with the same contract).
#
# Env / substitutions:
#   GCP_PROJECT / PROJECT_ID
#   GCP_REGION / _REGION
#   PYTHON_ARTIFACT_REPO / _PYTHON_REPO
#   CLOUDBUILD_CONNECTION_ID / _CLOUDBUILD_CONNECTION_ID
#   CLOUDBUILD_REPOSITORY_ID / _CLOUDBUILD_REPOSITORY_ID  (prefer linked Gen2 repo)
#   TF_STATE_BUCKET / _TF_STATE_BUCKET  (default: ${PROJECT}-tfstate)
#   TF_STATE_PREFIX                     (default: libs/fast_flow)
#   CREATE_PYTHON_REGISTRY / _CREATE_PYTHON_REGISTRY (default false — foundation owns AR)
#   GITHUB_OWNER / _GITHUB_OWNER (default garusocruz)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_DIR="${ROOT}/deploy/terraform"
cd "${TF_DIR}"

PROJECT_ID="${GCP_PROJECT:-${PROJECT_ID:?set GCP_PROJECT or PROJECT_ID}}"
REGION="${GCP_REGION:-${_REGION:-us-central1}}"
PYTHON_REPO="${PYTHON_ARTIFACT_REPO:-${_PYTHON_REPO:-lynko-python}}"
CONNECTION_ID="${CLOUDBUILD_CONNECTION_ID:-${_CLOUDBUILD_CONNECTION_ID:-}}"
REPOSITORY_ID="${CLOUDBUILD_REPOSITORY_ID:-${_CLOUDBUILD_REPOSITORY_ID:-}}"
GITHUB_OWNER="${GITHUB_OWNER:-${_GITHUB_OWNER:-garusocruz}}"
CREATE_REGISTRY="${CREATE_PYTHON_REGISTRY:-${_CREATE_PYTHON_REGISTRY:-false}}"
STATE_BUCKET="${TF_STATE_BUCKET:-${_TF_STATE_BUCKET:-}}"
if [[ -z "${STATE_BUCKET}" ]]; then
  STATE_BUCKET="${PROJECT_ID}-tfstate"
fi
LIB_PREFIX="${TF_STATE_PREFIX:-libs/calculadora_rtc_simples_nacional}"

# Default linked Gen2 repository when connection is known but repo id omitted.
if [[ -z "${REPOSITORY_ID}" && -n "${CONNECTION_ID}" ]]; then
  REPOSITORY_ID="${CONNECTION_ID}/repositories/calculadora-rtc-simples-nacional"
fi

case "${CREATE_REGISTRY}" in
  true|TRUE|1) CREATE_REGISTRY=true ;;
  *) CREATE_REGISTRY=false ;;
esac

echo "terraform project=${PROJECT_ID} region=${REGION} bucket=${STATE_BUCKET} prefix=${LIB_PREFIX}"
echo "cloudbuild connection=${CONNECTION_ID:-<empty>} repository=${REPOSITORY_ID:-<empty>}"
echo "module source: ./modules/python_lib (vendored from lynko-terraform)"

[[ -f backend.tf ]] || cat > backend.tf <<'BE'
terraform {
  backend "gcs" {}
}
BE

terraform init -input=false \
  -backend-config="bucket=${STATE_BUCKET}" \
  -backend-config="prefix=${LIB_PREFIX}" \
  -reconfigure

# CI-generated tfvars (do not rely on gitignored terraform.tfvars).
cat > terraform.tfvars <<EOF
project_id = "${PROJECT_ID}"
region     = "${REGION}"

python_registry_id     = "${PYTHON_REPO}"
create_python_registry = ${CREATE_REGISTRY}

github_owner             = "${GITHUB_OWNER}"
cloudbuild_connection_id = "${CONNECTION_ID}"
cloudbuild_repository_id = "${REPOSITORY_ID}"

create_feature_triggers = false
create_rc_triggers      = false
create_prod_triggers    = false
EOF

terraform validate

# Publish SA may already exist (foundation bootstrap / prior stack) while this
# state prefix is empty — adopt it to avoid googleapi 409 alreadyExists.
PUBLISH_SA_ID="${PUBLISH_SA_ID:-lynko-pub-fastflow}"
PUBLISH_SA_EMAIL="${PUBLISH_SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"
PUBLISH_SA_ADDR="module.lib.google_service_account.publish"
if ! terraform state list 2>/dev/null | grep -Fxq "${PUBLISH_SA_ADDR}"; then
  echo "importing existing publish SA if present: ${PUBLISH_SA_EMAIL}"
  terraform import -input=false \
    "${PUBLISH_SA_ADDR}" \
    "projects/${PROJECT_ID}/serviceAccounts/${PUBLISH_SA_EMAIL}" \
    || echo "import skipped (SA absent or not importable — apply will create)"
fi

terraform apply -input=false -auto-approve
terraform output
