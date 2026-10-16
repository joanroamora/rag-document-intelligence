variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
}

output "worker_service_account_id" {
  value       = "rag-worker-${var.environment}"
  description = "Least-privilege service account identifier for RAG workers"
}
