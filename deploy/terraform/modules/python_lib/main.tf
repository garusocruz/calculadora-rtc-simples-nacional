# Vendored copy of lynko-terraform adapters/gcp/delivery/python_lib (source of truth).
# Edit the foundation adapter first, then sync here (scripts/sync-python-lib-module.sh).
# Local path avoids private git:: fetches in Cloud Build (PAT 403 on lynko-terraform).

# Per-repo Terraform for one Lynko core Python lib (thin CD stack).
#
# Foundation (`lynko-terraform`) owns shared project infra including Python AR
# (`lynko-python`). Lib stacks set create_python_registry=false and consume it.
#
# Owns:
#   - required GCP APIs (idempotent enable)
#   - optional AR create (legacy / bootstrap only — prefer foundation)
#   - publish service account + AR writer IAM
#   - Cloud Build v2 repository link (optional) + feature / rc / prod triggers
#
# Publish order: flow_engine → lynkobuffers → fast_flow

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.40.0"
    }
  }
}

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "lib_id" {
  description = "Internal id: flow_engine | lynkobuffers | fast_flow"
  type        = string
}

variable "package_name" {
  description = "Distribution name: flow-engine | lynko-buffers | fast-flow"
  type        = string
}

variable "github_owner" {
  type    = string
  default = "garusocruz"
}

variable "github_repo" {
  type = string
}

variable "python_registry_id" {
  type    = string
  default = "lynko-python"
}

variable "create_python_registry" {
  description = "Create shared Python AR. Prefer false — foundation owns lynko-python."
  type        = bool
  default     = false
}

variable "cloudbuild_connection_id" {
  description = "projects/PROJECT/locations/REGION/connections/NAME. Empty skips triggers."
  type        = string
  default     = ""
}

variable "cloudbuild_repository_id" {
  description = "Existing v2 repository resource id. Empty → Terraform creates one named github_repo."
  type        = string
  default     = ""
}

variable "create_feature_triggers" {
  description = "Prefer false — foundation delivery/lib_cicd owns lib PR triggers."
  type        = bool
  default     = false
}

variable "create_rc_triggers" {
  type    = bool
  default = false
}

variable "create_prod_triggers" {
  type    = bool
  default = false
}

variable "publish_sa_id" {
  description = "SA account_id (6-30 chars). Empty → short default per lib."
  type        = string
  default     = ""
}

variable "terraform_runner_sa_id" {
  description = "Existing SA that runs Cloud Build (terraform+publish). Default lynko-deploy."
  type        = string
  default     = "lynko-deploy"
}

variable "labels" {
  type    = map(string)
  default = {}
}

locals {
  triggers_active  = var.cloudbuild_connection_id != ""
  create_cb_repo   = local.triggers_active && var.cloudbuild_repository_id == ""
  cb_repository_id = local.create_cb_repo ? google_cloudbuildv2_repository.lib[0].id : var.cloudbuild_repository_id
  sa_id = var.publish_sa_id != "" ? var.publish_sa_id : (
    var.lib_id == "flow_engine" ? "lynko-pub-floweng" : (
      var.lib_id == "lynkobuffers" ? "lynko-pub-buffers" : "lynko-pub-fastflow"
    )
  )
  trigger_slug              = replace(var.lib_id, "_", "-")
  terraform_runner_sa_email = "${var.terraform_runner_sa_id}@${var.project_id}.iam.gserviceaccount.com"
  terraform_runner_sa_id    = "projects/${var.project_id}/serviceAccounts/${local.terraform_runner_sa_email}"
  labels = merge(
    {
      managed-by = "terraform"
      lynko-lib  = var.lib_id
    },
    var.labels,
  )
  apis = toset([
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
  ])
}

data "google_project" "this" {
  project_id = var.project_id
}

resource "google_project_service" "apis" {
  for_each = local.apis

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "python" {
  count = var.create_python_registry ? 1 : 0

  project       = var.project_id
  location      = var.region
  repository_id = var.python_registry_id
  description   = "Lynko core Python libs (owned by ${var.lib_id} TF)"
  format        = "PYTHON"
  labels        = local.labels

  depends_on = [google_project_service.apis]
}

data "google_artifact_registry_repository" "python" {
  count = var.create_python_registry ? 0 : 1

  project       = var.project_id
  location      = var.region
  repository_id = var.python_registry_id

  depends_on = [google_project_service.apis]
}

locals {
  python_repo_name = var.create_python_registry ? google_artifact_registry_repository.python[0].name : data.google_artifact_registry_repository.python[0].name
}

resource "google_service_account" "publish" {
  project      = var.project_id
  account_id   = local.sa_id
  display_name = "Lynko lib publisher (${var.lib_id})"
  description  = "Publishes ${var.package_name} to Artifact Registry Python"

  depends_on = [google_project_service.apis]
}

resource "google_artifact_registry_repository_iam_member" "publish_writer" {
  project    = var.project_id
  location   = var.region
  repository = local.python_repo_name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.publish.email}"
}

resource "google_artifact_registry_repository_iam_member" "cloudbuild_writer" {
  project    = var.project_id
  location   = var.region
  repository = local.python_repo_name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_project.this.number}@cloudbuild.gserviceaccount.com"
}

resource "google_service_account_iam_member" "cloudbuild_act_as_publish" {
  service_account_id = google_service_account.publish.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${data.google_project.this.number}@cloudbuild.gserviceaccount.com"
}

# Custom trigger SA must be able to run Cloud Build steps + write logs.
resource "google_project_iam_member" "publish_cloudbuild_builder" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.builder"
  member  = "serviceAccount:${google_service_account.publish.email}"
}

resource "google_project_iam_member" "publish_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.publish.email}"
}

# lynko-deploy (or terraform_runner_sa_id) executes Cloud Build: terraform apply + publish.
data "google_service_account" "terraform_runner" {
  account_id = var.terraform_runner_sa_id
  project    = var.project_id

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "runner_cloudbuild_builder" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.builder"
  member  = "serviceAccount:${data.google_service_account.terraform_runner.email}"
}

resource "google_project_iam_member" "runner_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${data.google_service_account.terraform_runner.email}"
}

resource "google_project_iam_member" "runner_serviceusage" {
  project = var.project_id
  role    = "roles/serviceusage.serviceUsageAdmin"
  member  = "serviceAccount:${data.google_service_account.terraform_runner.email}"
}

resource "google_project_iam_member" "runner_sa_admin" {
  project = var.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${data.google_service_account.terraform_runner.email}"
}

resource "google_project_iam_member" "runner_ar_admin" {
  project = var.project_id
  role    = "roles/artifactregistry.admin"
  member  = "serviceAccount:${data.google_service_account.terraform_runner.email}"
}

resource "google_project_iam_member" "runner_cb_editor" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.editor"
  member  = "serviceAccount:${data.google_service_account.terraform_runner.email}"
}

resource "google_project_iam_member" "runner_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${data.google_service_account.terraform_runner.email}"
}

resource "google_project_iam_member" "runner_project_iam" {
  # Needed to bind IAM members on AR / project for this lib stack.
  project = var.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${data.google_service_account.terraform_runner.email}"
}

resource "google_service_account_iam_member" "cb_act_as_runner" {
  service_account_id = data.google_service_account.terraform_runner.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${data.google_project.this.number}@cloudbuild.gserviceaccount.com"
}

# CD runner (lynko-deploy) applies TF; publish step impersonates the lib publish SA.
resource "google_service_account_iam_member" "runner_impersonate_publish" {
  service_account_id = google_service_account.publish.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${data.google_service_account.terraform_runner.email}"
}

resource "google_service_account_iam_member" "runner_act_as_publish" {
  service_account_id = google_service_account.publish.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${data.google_service_account.terraform_runner.email}"
}

resource "google_cloudbuildv2_repository" "lib" {
  count = local.create_cb_repo ? 1 : 0

  project           = var.project_id
  location          = var.region
  name              = var.github_repo
  parent_connection = var.cloudbuild_connection_id
  remote_uri        = "https://github.com/${var.github_owner}/${var.github_repo}.git"

  depends_on = [google_project_service.apis]
}

resource "google_cloudbuild_trigger" "pr_quality" {
  count = local.triggers_active && var.create_feature_triggers ? 1 : 0

  project            = var.project_id
  location           = var.region
  name               = "${local.trigger_slug}-lib-feature-pr"
  description        = "${var.lib_id}: pull_request → main → quality gates only"
  service_account    = local.terraform_runner_sa_id
  include_build_logs = "INCLUDE_BUILD_LOGS_WITH_STATUS"
  tags               = ["lynko", "pr", "libs", var.lib_id]

  repository_event_config {
    repository = local.cb_repository_id
    pull_request {
      branch          = "^main$"
      comment_control = "COMMENTS_DISABLED"
    }
  }

  filename = "cloudbuild.yaml"
  substitutions = {
    _LIB_NAME                 = var.lib_id
    _ENVIRONMENT              = "pr"
    _REGION                   = var.region
    _PYTHON_REPO              = var.python_registry_id
    _RUN_TERRAFORM            = "0"
    _RUN_PUBLISH              = "0"
    _CREATE_PYTHON_REGISTRY   = tostring(var.create_python_registry)
    _CLOUDBUILD_CONNECTION_ID = var.cloudbuild_connection_id
    _CLOUDBUILD_REPOSITORY_ID = local.cb_repository_id
    _PUBLISH_SA_EMAIL         = google_service_account.publish.email
    _GITHUB_OWNER             = var.github_owner
    _GITHUB_REPO              = var.github_repo
    _CONTEXT                  = var.lib_id
  }
}

resource "google_cloudbuild_trigger" "feature_fc" {
  count = local.triggers_active && var.create_feature_triggers ? 1 : 0

  project            = var.project_id
  location           = var.region
  name               = "${local.trigger_slug}-lib-feature-fc"
  description        = "${var.lib_id}: push fc-* → feature package ({version}+fb.{branch})"
  service_account    = local.terraform_runner_sa_id
  include_build_logs = "INCLUDE_BUILD_LOGS_WITH_STATUS"
  tags               = ["lynko", "feature", "libs", var.lib_id]

  repository_event_config {
    repository = local.cb_repository_id
    push {
      branch = "^fc-.*"
    }
  }

  filename = "cloudbuild.yaml"
  substitutions = {
    _LIB_NAME                 = var.lib_id
    _ENVIRONMENT              = "feature"
    _REGION                   = var.region
    _PYTHON_REPO              = var.python_registry_id
    _RUN_TERRAFORM            = "1"
    _RUN_PUBLISH              = "1"
    _CREATE_PYTHON_REGISTRY   = tostring(var.create_python_registry)
    _CLOUDBUILD_CONNECTION_ID = var.cloudbuild_connection_id
    _CLOUDBUILD_REPOSITORY_ID = local.cb_repository_id
    _PUBLISH_SA_EMAIL         = google_service_account.publish.email
    _GITHUB_OWNER             = var.github_owner
    _GITHUB_REPO              = var.github_repo
    _CONTEXT                  = var.lib_id
  }
}

resource "google_cloudbuild_trigger" "rc_main" {
  count = local.triggers_active && var.create_rc_triggers ? 1 : 0

  project            = var.project_id
  location           = var.region
  name               = "${local.trigger_slug}-lib-rc-main"
  description        = "${var.lib_id}: push main → RC package"
  service_account    = local.terraform_runner_sa_id
  include_build_logs = "INCLUDE_BUILD_LOGS_WITH_STATUS"
  tags               = ["lynko", "rc", "libs", var.lib_id]

  repository_event_config {
    repository = local.cb_repository_id
    push {
      branch = "^main$"
    }
  }

  filename = "cloudbuild.yaml"
  substitutions = {
    _LIB_NAME                 = var.lib_id
    _ENVIRONMENT              = "rc"
    _REGION                   = var.region
    _PYTHON_REPO              = var.python_registry_id
    _RUN_TERRAFORM            = "1"
    _CREATE_PYTHON_REGISTRY   = tostring(var.create_python_registry)
    _CLOUDBUILD_CONNECTION_ID = var.cloudbuild_connection_id
    _CLOUDBUILD_REPOSITORY_ID = local.cb_repository_id
    _PUBLISH_SA_EMAIL         = google_service_account.publish.email
    _GITHUB_OWNER             = var.github_owner
    _GITHUB_REPO              = var.github_repo
    _CONTEXT                  = var.lib_id
  }
}

resource "google_cloudbuild_trigger" "prod_tag" {
  count = local.triggers_active && var.create_prod_triggers ? 1 : 0

  project            = var.project_id
  location           = var.region
  name               = "${local.trigger_slug}-lib-prod-tag"
  description        = "${var.lib_id}: tag vX.Y.Z → production package"
  service_account    = local.terraform_runner_sa_id
  include_build_logs = "INCLUDE_BUILD_LOGS_WITH_STATUS"
  tags               = ["lynko", "production", "libs", var.lib_id]

  repository_event_config {
    repository = local.cb_repository_id
    push {
      tag = "^v[0-9]+\\.[0-9]+\\.[0-9]+$"
    }
  }

  filename = "cloudbuild.yaml"
  substitutions = {
    _LIB_NAME                 = var.lib_id
    _ENVIRONMENT              = "production"
    _REGION                   = var.region
    _PYTHON_REPO              = var.python_registry_id
    _TAG_NAME                 = "$TAG_NAME"
    _RUN_TERRAFORM            = "1"
    _CREATE_PYTHON_REGISTRY   = tostring(var.create_python_registry)
    _CLOUDBUILD_CONNECTION_ID = var.cloudbuild_connection_id
    _CLOUDBUILD_REPOSITORY_ID = local.cb_repository_id
    _PUBLISH_SA_EMAIL         = google_service_account.publish.email
    _GITHUB_OWNER             = var.github_owner
    _GITHUB_REPO              = var.github_repo
    _CONTEXT                  = var.lib_id
  }
}

output "lib_id" {
  value = var.lib_id
}

output "package_name" {
  value = var.package_name
}

output "publish_sa_email" {
  value = google_service_account.publish.email
}

output "python_registry" {
  value = "${var.region}-python.pkg.dev/${var.project_id}/${var.python_registry_id}"
}

output "python_index_url" {
  value = "https://${var.region}-python.pkg.dev/${var.project_id}/${var.python_registry_id}/simple/"
}

output "created_python_registry" {
  value = var.create_python_registry
}

output "trigger_names" {
  value = compact([
    try(google_cloudbuild_trigger.pr_quality[0].name, ""),
    try(google_cloudbuild_trigger.feature_fc[0].name, ""),
    try(google_cloudbuild_trigger.rc_main[0].name, ""),
    try(google_cloudbuild_trigger.prod_tag[0].name, ""),
  ])
}
