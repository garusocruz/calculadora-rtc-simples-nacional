provider "google" {
  project = var.project_id
  region  = var.region
}

# Thin composition root. Module SoT: lynko-terraform
# adapters/gcp/delivery/python_lib — sync with scripts/sync-python-lib-module.sh.
# Local path (not git::) so Cloud Build does not need read access to the private
# foundation repo for terraform validate/apply.
module "lib" {
  source = "./modules/python_lib"

  project_id               = var.project_id
  region                   = var.region
  lib_id                   = "calculadora_rtc_simples_nacional"
  package_name             = "calculadora-rtc-simples-nacional"
  github_owner             = var.github_owner
  github_repo              = "calculadora-rtc-simples-nacional"
  python_registry_id       = var.python_registry_id
  create_python_registry   = var.create_python_registry
  cloudbuild_connection_id = var.cloudbuild_connection_id
  cloudbuild_repository_id = var.cloudbuild_repository_id
  create_feature_triggers  = var.create_feature_triggers
  create_rc_triggers       = var.create_rc_triggers
  create_prod_triggers     = var.create_prod_triggers
}
