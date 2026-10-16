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

output "documents_bucket_URI_prefix" {
  value       = "gs://${var.project_id}-rag-documents-${var.environment}"
  description = "Canonical GCS URI prefix for raw and normalized documents"
}
