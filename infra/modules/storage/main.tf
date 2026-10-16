variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "environment" {
  type        = string
  description = "Deployment environment (dev, test, stage, prod)"
}

variable "region" {
  type        = string
  description = "GCP region for storage resources"
}

variable "force_destroy" {
  type        = bool
  description = "When true, bucket can be deleted even if containing objects during terraform destroy"
  default     = true
}

resource "google_storage_bucket" "documents" {
  name                        = "${var.project_id}-rag-documents-${var.environment}"
  location                    = var.region
  force_destroy               = var.force_destroy
  uniform_bucket_level_access = true

  versioning {
    enabled = var.environment == "prod" ? true : false
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = var.environment == "dev" ? 30 : 365
    }
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    project     = "rag-platform"
  }
}

output "documents_bucket_name" {
  value       = google_storage_bucket.documents.name
  description = "Name of the GCS documents bucket"
}

output "documents_bucket_URI_prefix" {
  value       = "gs://${google_storage_bucket.documents.name}"
  description = "Canonical GCS URI prefix for raw and normalized documents"
}
