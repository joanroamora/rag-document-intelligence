variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
}

resource "google_project_service" "iam" {
  project            = var.project_id
  service            = "iam.googleapis.com"
  disable_on_destroy = false
}

resource "google_service_account" "worker" {
  account_id   = "rag-worker-${var.environment}"
  display_name = "RAG Worker Service Account (${var.environment})"
  project      = var.project_id
  depends_on   = [google_project_service.iam]
}

output "worker_service_account_id" {
  value       = google_service_account.worker.id
  description = "Least-privilege service account identifier for RAG workers"
}

output "worker_service_account_email" {
  value       = google_service_account.worker.email
  description = "Email of the RAG worker service account"
}
