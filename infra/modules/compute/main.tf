variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
}

variable "region" {
  type        = string
  description = "GCP region for serverless/container compute"
}

output "service_name" {
  value       = "rag-api-${var.environment}"
  description = "Cloud Run service name for RAG backend"
}
