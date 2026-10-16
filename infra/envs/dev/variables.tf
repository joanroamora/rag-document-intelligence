variable "project_id" {
  type        = string
  description = "GCP Project ID for DEV environment"
  default     = "rag-platform-dev-placeholder"
}

variable "region" {
  type        = string
  description = "Default GCP region"
  default     = "us-central1"
}

variable "environment" {
  type        = string
  description = "Environment identifier"
  default     = "dev"
}
