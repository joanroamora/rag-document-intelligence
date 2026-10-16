output "documents_bucket_uri" {
  value       = module.storage.documents_bucket_URI_prefix
  description = "GCS bucket prefix for DEV documents"
}

output "api_service_name" {
  value       = module.compute.service_name
  description = "Cloud Run service name for DEV"
}
