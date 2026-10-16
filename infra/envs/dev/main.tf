module "identity" {
  source      = "../../modules/identity"
  project_id  = var.project_id
  environment = var.environment
}

module "storage" {
  source      = "../../modules/storage"
  project_id  = var.project_id
  environment = var.environment
  region      = var.region
}

module "compute" {
  source      = "../../modules/compute"
  project_id  = var.project_id
  environment = var.environment
  region      = var.region
}
