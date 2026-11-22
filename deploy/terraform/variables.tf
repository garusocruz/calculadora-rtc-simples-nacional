variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "python_registry_id" {
  type    = string
  default = "lynko-python"
}

variable "create_python_registry" {
  description = "Must stay false when foundation owns lynko-python."
  type        = bool
  default     = false
}

variable "github_owner" {
  type    = string
  default = "garusocruz"
}

variable "cloudbuild_connection_id" {
  type    = string
  default = ""
}

variable "cloudbuild_repository_id" {
  description = "Gen2 repo resource id (…/repositories/garusocruz-fast_flow). Empty creates a new link named fast_flow."
  type        = string
  default     = ""
}

variable "create_feature_triggers" {
  description = "Must stay false — foundation lib_cicd owns PR triggers."
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
